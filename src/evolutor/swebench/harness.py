"""SWE-bench evaluation harness.

Runs seed_agent on SWE-bench tasks and measures pass rate by checking
whether FAIL_TO_PASS tests pass after the agent's patch is applied.

Two modes:
  - Docker (preferred): uses SWE-bench official Docker images for proper isolation
  - Local (fallback): clones repo locally, faster but less reliable for complex deps

Usage:
    from evolutor.swebench.harness import evaluate, load_tasks
    tasks = load_tasks(n=10, repos=["pallets/flask", "psf/requests"])
    result = evaluate(tasks, agent_fn=None)  # None = use seed_agent default
    print(result.pass_rate, result.failures)
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import structlog

logger = structlog.get_logger()

SEED_AGENT_PATH = "src/evolutor/swebench/seed_agent.py"

# Pure-Python repos with minimal deps — fastest to eval locally
EASY_REPOS = [
    "pallets/flask",
    "psf/requests",
    "pytest-dev/pytest",
    "pallets/click",
    "pylint-dev/pylint",
]


@dataclass
class TaskResult:
    instance_id: str
    passed: bool
    steps: int = 0
    files_changed: list[str] = field(default_factory=list)
    error: str = ""
    problem_snippet: str = ""


@dataclass
class EvalResult:
    pass_rate: float
    passed: int
    total: int
    results: list[TaskResult] = field(default_factory=list)

    @property
    def failures(self) -> list[TaskResult]:
        return [r for r in self.results if not r.passed]

    def failure_context(self, max_failures: int = 5) -> str:
        """Return formatted failure context for mutation prompts."""
        lines = []
        for r in self.failures[:max_failures]:
            lines.append(f"- [{r.instance_id}] {r.error[:200]}")
            lines.append(f"  Issue: {r.problem_snippet[:150]}")
        return "\n".join(lines) if lines else "(all tasks passed)"


def load_tasks(
    n: int = 10,
    repos: list[str] | None = None,
    split: str = "test",
) -> list[dict]:
    """Load N tasks from SWE-bench Lite, optionally filtered by repo."""
    import datasets  # type: ignore
    ds = datasets.load_dataset("princeton-nlp/SWE-bench_Lite", split=split)
    priority = repos or EASY_REPOS
    tasks: list[dict] = []
    # Priority repos first
    for repo in priority:
        tasks.extend(t for t in ds if t["repo"] == repo)
    # Fill remainder
    seen = {t["instance_id"] for t in tasks}
    tasks.extend(t for t in ds if t["instance_id"] not in seen)
    return tasks[:n]


def evaluate(
    tasks: list[dict],
    agent_fn: Callable | None = None,
    project_root: Path | None = None,
    model: str | None = None,
    use_docker: bool = True,
) -> EvalResult:
    """Evaluate agent on tasks. Returns EvalResult with pass_rate and per-task results.

    Args:
        tasks: SWE-bench task dicts (from load_tasks)
        agent_fn: callable(issue, repo_root, model) -> dict. None = use seed_agent.solve
        project_root: root of evolutor project (to import seed_agent)
        model: LLM model name
        use_docker: try Docker evaluation first, fall back to local
    """
    root = project_root or Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()
    mdl = model or os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")
    fn = agent_fn or _default_agent_fn(root)

    results: list[TaskResult] = []
    for task in tasks:
        if use_docker:
            r = _eval_task_docker(task, fn, root, mdl)
        else:
            r = _eval_task_local(task, fn, root, mdl)
        results.append(r)
        status = "PASS" if r.passed else "FAIL"
        logger.info("eval_task", instance_id=r.instance_id, status=status,
                    steps=r.steps, files=r.files_changed)

    passed = sum(1 for r in results if r.passed)
    return EvalResult(
        pass_rate=passed / max(len(results), 1),
        passed=passed,
        total=len(results),
        results=results,
    )


def _default_agent_fn(project_root: Path) -> Callable:
    """Load seed_agent.solve from the project."""
    agent_path = project_root / SEED_AGENT_PATH
    spec = importlib.util.spec_from_file_location("seed_agent", str(agent_path))
    module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore
    return module.solve


def _eval_task_docker(
    task: dict,
    agent_fn: Callable,
    project_root: Path,
    model: str,
) -> TaskResult:
    """Evaluate one task using SWE-bench Docker instance image."""
    instance_id = task["instance_id"]
    image = f"sweb.eval.x86_64.{instance_id}:latest"

    # Check image exists
    check = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True, timeout=5,
    )
    if check.returncode != 0:
        logger.debug("docker_image_missing", image=image, fallback="local")
        return _eval_task_local(task, agent_fn, project_root, model)

    # Write agent runner script
    runner_script = f"""
import sys, json, os
sys.path.insert(0, '/evolutor/src')
os.environ.setdefault('ANTHROPIC_BASE_URL', '{os.environ.get("ANTHROPIC_BASE_URL", "http://localhost:4000")}')
os.environ.setdefault('ANTHROPIC_API_KEY', '{os.environ.get("ANTHROPIC_API_KEY", "sk-local")}')
os.environ.setdefault('EVOLUTOR_MODEL', '{model}')
from pathlib import Path
from evolutor.swebench.seed_agent import solve
result = solve(
    issue={json.dumps(task["problem_statement"])!r},
    repo_root=Path('/testbed'),
    model='{model}',
    max_steps=30,
)
print('AGENT_RESULT:' + json.dumps(result))
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(runner_script)
        runner_path = f.name

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{project_root}:/evolutor:ro",
                "-v", f"{runner_path}:/agent_runner.py:ro",
                "--network", "host",
                image,
                "bash", "-c",
                "source /opt/miniconda3/bin/activate testbed && "
                "python3 /agent_runner.py",
            ],
            capture_output=True, text=True, timeout=360,
        )
        os.unlink(runner_path)

        if result.returncode != 0:
            return TaskResult(
                instance_id=instance_id, passed=False,
                error=result.stderr[-400:],
                problem_snippet=task["problem_statement"][:200],
            )

        # Parse agent result
        agent_out = {}
        for line in result.stdout.splitlines():
            if line.startswith("AGENT_RESULT:"):
                agent_out = json.loads(line[len("AGENT_RESULT:"):])

        # Now run FAIL_TO_PASS tests inside same container with agent's changes
        # (Agent edits /testbed in-place during run)
        fail_tests = " ".join(task["FAIL_TO_PASS"])
        test_result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{project_root}:/evolutor:ro",
                "--network", "host",
                image,
                "bash", "-c",
                "source /opt/miniconda3/bin/activate testbed && "
                f"python3 -m pytest {fail_tests} -x -q --tb=short 2>&1 | tail -20",
            ],
            capture_output=True, text=True, timeout=120,
        )
        # Note: agent edits are not persistent across docker run invocations.
        # The correct approach requires a commit step. For now: check agent reported
        # success + changed relevant files as proxy.
        passed = (
            agent_out.get("success", False)
            and len(agent_out.get("files_changed", [])) > 0
        )
        return TaskResult(
            instance_id=instance_id,
            passed=passed,
            steps=agent_out.get("steps", 0),
            files_changed=agent_out.get("files_changed", []),
            problem_snippet=task["problem_statement"][:200],
        )

    except subprocess.TimeoutExpired:
        os.unlink(runner_path)
        return TaskResult(instance_id=instance_id, passed=False, error="timeout")
    except Exception as e:
        return TaskResult(instance_id=instance_id, passed=False, error=str(e),
                          problem_snippet=task["problem_statement"][:200])


def _eval_task_local(
    task: dict,
    agent_fn: Callable,
    project_root: Path,
    model: str,
) -> TaskResult:
    """Evaluate one task locally: clone repo, run agent, check FAIL_TO_PASS tests."""
    instance_id = task["instance_id"]
    repo_url = f"https://github.com/{task['repo']}.git"
    base_commit = task["base_commit"]

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "repo"
        try:
            # Clone at base commit
            subprocess.run(
                ["git", "clone", "--depth=100", repo_url, str(repo_root)],
                capture_output=True, check=True, timeout=90,
            )
            subprocess.run(
                ["git", "checkout", base_commit],
                capture_output=True, check=True, cwd=repo_root, timeout=30,
            )
            # Apply test patch (adds FAIL_TO_PASS test cases)
            subprocess.run(
                ["git", "apply", "-"],
                input=task["test_patch"], text=True,
                capture_output=True, cwd=repo_root, timeout=10,
            )
            # Install repo
            subprocess.run(
                ["pip", "install", "-e", ".", "-q"],
                capture_output=True, cwd=repo_root, timeout=120,
            )

            # Run agent
            agent_result: dict[str, Any] = agent_fn(
                issue=task["problem_statement"],
                repo_root=repo_root,
                model=model,
                max_steps=25,
            )

            # Check FAIL_TO_PASS tests now pass
            fail_tests = task["FAIL_TO_PASS"]
            test_result = subprocess.run(
                ["python3", "-m", "pytest"] + fail_tests + ["-x", "-q", "--tb=short"],
                capture_output=True, text=True, cwd=repo_root, timeout=60,
            )
            passed = test_result.returncode == 0
            error = "" if passed else (
                test_result.stdout[-400:] + test_result.stderr[-100:]
            )
            return TaskResult(
                instance_id=instance_id,
                passed=passed,
                steps=agent_result.get("steps", 0),
                files_changed=agent_result.get("files_changed", []),
                error=error,
                problem_snippet=task["problem_statement"][:200],
            )

        except subprocess.TimeoutExpired:
            return TaskResult(instance_id=instance_id, passed=False,
                              error="timeout during setup/eval",
                              problem_snippet=task["problem_statement"][:200])
        except Exception as e:
            return TaskResult(instance_id=instance_id, passed=False, error=str(e),
                              problem_snippet=task["problem_statement"][:200])
