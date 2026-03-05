"""
Run Evolutor seed_agent + mini-swe-agent on 5 SWE-bench tasks, compare results.
Runs evolutor evolve for 10 generations first, then benchmarks evolved vs baseline vs mini-swe-agent.
"""
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# Ensure no paid API, use local vLLM
os.environ.setdefault("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-local")
os.environ.setdefault("EVOLUTOR_MODEL", "claude-sonnet-4-6")
os.environ.setdefault("EVOLUTOR_PROJECT_ROOT", "/home/mekashirskiy/evolutor")
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0,::1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0,::1"

PROJECT_ROOT = Path(os.environ["EVOLUTOR_PROJECT_ROOT"])
MODEL = os.environ["EVOLUTOR_MODEL"]

sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, "/home/mekashirskiy/competitors/SWE-bench")
sys.path.insert(0, "/home/mekashirskiy/competitors/mini-swe-agent/src")


# ── 5 fixed tasks (flask + requests — small repos, fast local eval) ──────────
TASK_IDS = [
    "pallets__flask-4045",   # raise error when blueprint name contains dot
    "pallets__flask-4992",   # add file mode param to Config.from_file()
    "pallets__flask-5063",   # routes show subdomain info
    "psf__requests-2317",    # iter_content decode_unicode
    "psf__requests-863",     # requests PreparedRequest body
]


def load_tasks() -> list[dict]:
    import datasets
    ds = datasets.load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    by_id = {t["instance_id"]: t for t in ds}
    return [by_id[tid] for tid in TASK_IDS if tid in by_id]


# ── Local evaluation: clone repo, run agent, check FAIL_TO_PASS tests ────────

@dataclass
class TaskResult:
    instance_id: str
    passed: bool
    elapsed: float = 0.0
    steps: int = 0
    files_changed: list = field(default_factory=list)
    error: str = ""


MINI_SWE_AGENT_PATH = "/home/mekashirskiy/competitors/mini-swe-agent"


def eval_task_docker(task: dict, agent_name: str, agent_runner_script: str, max_steps: int = 25) -> TaskResult:
    """Run agent in SWE-bench Docker image, check FAIL_TO_PASS tests in same container."""
    instance_id = task["instance_id"]
    image = f"sweb.eval.x86_64.{instance_id}:latest"
    t0 = time.time()

    # FAIL_TO_PASS is a JSON string in HuggingFace dataset
    fail_tests_raw = task["FAIL_TO_PASS"]
    if isinstance(fail_tests_raw, str):
        import json as _json
        fail_tests = _json.loads(fail_tests_raw)
    else:
        fail_tests = fail_tests_raw

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(agent_runner_script)
        runner_path = f.name

    # Write test_patch so FAIL_TO_PASS tests exist in the container
    test_patch = task.get("test_patch", "")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as pf:
        pf.write(test_patch)
        patch_path = pf.name

    try:
        # Single docker run: apply test_patch → run agent → run FAIL_TO_PASS tests
        fail_tests_str = " ".join(fail_tests)
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{PROJECT_ROOT}:/evolutor:ro",
            "-v", f"{runner_path}:/agent_runner.py:ro",
            "-v", f"{patch_path}:/test.patch:ro",
        ]
        if agent_name == "mini-swe-agent":
            docker_cmd += ["-v", f"{MINI_SWE_AGENT_PATH}:/mini-swe-agent:ro"]
        docker_cmd += [
            "-e", f"ANTHROPIC_BASE_URL={os.environ.get('ANTHROPIC_BASE_URL', 'http://127.0.0.1:4000')}",
            "-e", f"ANTHROPIC_API_KEY={os.environ.get('ANTHROPIC_API_KEY', 'sk-local')}",
            "-e", f"EVOLUTOR_MODEL={MODEL}",
            "-e", "OPENAI_BASE_URL=http://127.0.0.1:8000/v1",
            "-e", "OPENAI_API_KEY=sk-local",
            "--network", "host",
            image,
            "bash", "-c",
            "source /opt/miniconda3/bin/activate testbed 2>/dev/null || true; "
            "git apply /test.patch 2>/dev/null || true; "  # add FAIL_TO_PASS tests
            "pip install anthropic structlog pydantic -q 2>/dev/null; "
            "pip install -e /evolutor -q --no-deps 2>/dev/null; "
            "python3 /agent_runner.py; "
            f"python3 -m pytest {fail_tests_str} -x -q --tb=short 2>&1 | tail -20; "
            f"python3 -m pytest {fail_tests_str} -q --tb=no 2>&1 | grep -E '(passed|failed|error)' | tail -3",
        ]
        result = subprocess.run(
            docker_cmd,
            capture_output=True, text=True, timeout=360,
        )
        os.unlink(runner_path)
        os.unlink(patch_path)

        output = result.stdout + result.stderr
        # Check if tests passed
        import re as _re
        passed_match = _re.search(r"(\d+) passed", output)
        failed_match = _re.search(r"(\d+) failed", output)
        n_passed = int(passed_match.group(1)) if passed_match else 0
        n_failed = int(failed_match.group(1)) if failed_match else 0

        # Also check for AGENT_RESULT
        agent_steps = 0
        agent_files: list = []
        for line in output.splitlines():
            if line.startswith("AGENT_RESULT:"):
                try:
                    ar = json.loads(line[len("AGENT_RESULT:"):])
                    agent_steps = ar.get("steps", 0)
                    agent_files = ar.get("files_changed", [])
                except Exception:
                    pass

        passed = n_failed == 0 and n_passed > 0
        error = "" if passed else output[-400:]
        return TaskResult(
            instance_id=instance_id,
            passed=passed,
            elapsed=time.time() - t0,
            steps=agent_steps,
            files_changed=agent_files,
            error=error,
        )
    except subprocess.TimeoutExpired:
        try:
            os.unlink(runner_path)
            os.unlink(patch_path)
        except Exception:
            pass
        return TaskResult(instance_id=instance_id, passed=False,
                          elapsed=time.time() - t0, error="timeout")
    except Exception as e:
        try:
            os.unlink(runner_path)
            os.unlink(patch_path)
        except Exception:
            pass
        return TaskResult(instance_id=instance_id, passed=False,
                          elapsed=time.time() - t0, error=str(e)[:200])


# ── mini-swe-agent adapter ───────────────────────────────────────────────────

def make_mini_swe_agent_fn():
    """Wrap mini-swe-agent to match our agent_fn(issue, repo_root, model, max_steps) API."""
    try:
        from minisweagent.agents.default import DefaultAgent
        from minisweagent.environments.local import LocalEnvironment
        from minisweagent.models.litellm_model import LiteLLMModel

        def agent_fn(issue, repo_root, model, max_steps=25):
            t0 = time.time()
            env = LocalEnvironment(repo_path=str(repo_root))
            lm = LiteLLMModel(
                model="openai/qwen3-coder-30b",
                base_url="http://127.0.0.1:8000/v1",
                api_key="sk-local",
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            agent = DefaultAgent(env=env, model=lm, max_steps=max_steps)
            result = agent.run(issue)
            files = env.get_changed_files() if hasattr(env, "get_changed_files") else []
            return {"success": True, "steps": max_steps, "files_changed": files,
                    "summary": str(result)[:200]}
        return agent_fn
    except Exception as e:
        print(f"[mini-swe-agent] import failed: {e} — using bash-only subprocess fallback")
        return _mini_swe_agent_subprocess


def _mini_swe_agent_subprocess(issue, repo_root, model, max_steps=25):
    """Run mini-swe-agent as subprocess using its CLI."""
    mini_path = "/home/mekashirskiy/competitors/mini-swe-agent"
    result = subprocess.run(
        [
            sys.executable, "-m", "minisweagent.run.hello_world",
            "--issue", issue[:2000],
            "--repo", str(repo_root),
            "--model", "openai/qwen3-coder-30b",
            "--max-steps", str(max_steps),
        ],
        capture_output=True, text=True, timeout=300,
        cwd=mini_path,
        env={
            **os.environ,
            "OPENAI_BASE_URL": "http://127.0.0.1:8000/v1",
            "OPENAI_API_KEY": "sk-local",
        },
    )
    files = []
    # Parse changed files from git diff
    diff = subprocess.run(
        ["git", "diff", "--name-only"], capture_output=True, text=True, cwd=repo_root
    )
    files = diff.stdout.strip().splitlines()
    return {"success": result.returncode == 0, "steps": max_steps,
            "files_changed": files, "summary": result.stdout[-200:]}


# ── Evolutor seed_agent loader ───────────────────────────────────────────────

def load_evolutor_agent(agent_path: Path | None = None):
    path = agent_path or (PROJECT_ROOT / "src/evolutor/swebench/seed_agent.py")
    spec = importlib.util.spec_from_file_location("seed_agent", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.solve


# ── Main: evolve then benchmark ──────────────────────────────────────────────

async def run_evolution():
    print("\n" + "="*60)
    print("PHASE 1: Evolution (10 generations, fitness = SWE-bench)")
    print("="*60)
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from evolutor.evolution.loop import EvolutionLoop
    loop = EvolutionLoop()
    report = await loop.run(generations=10)
    print(f"\nEvolution complete:")
    print(f"  Generations completed : {report.generations_completed}")
    print(f"  Best SWE-bench fitness: {report.best_fitness:.3f}")
    print(f"  Plateaus detected     : {report.plateaus_detected}")
    return report


SEED_AGENT_RUNNER = '''
import sys, json, os
sys.path.insert(0, '/evolutor/src')
os.environ.setdefault('no_proxy', 'localhost,127.0.0.1,0.0.0.0,::1')
os.environ.setdefault('NO_PROXY', 'localhost,127.0.0.1,0.0.0.0,::1')
from pathlib import Path
from evolutor.swebench.seed_agent import solve
result = solve(
    issue={issue!r},
    repo_root=Path('/testbed'),
    model={model!r},
    max_steps=30,
)
print('AGENT_RESULT:' + json.dumps(result))
'''

MINI_SWE_RUNNER = '''
import sys, json, os, subprocess
sys.path.insert(0, '/mini-swe-agent/src')
os.environ['no_proxy'] = 'localhost,127.0.0.1,0.0.0.0,::1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,0.0.0.0,::1'
os.environ['OPENAI_BASE_URL'] = 'http://127.0.0.1:8000/v1'
os.environ['OPENAI_API_KEY'] = 'sk-local'
try:
    import litellm
    litellm.suppress_debug_info = True
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.local import LocalEnvironment
    from minisweagent.models.litellm_model import LitellmModel
    env = LocalEnvironment(cwd='/testbed')
    model = LitellmModel(model_name='openai/qwen3-coder-30b')
    agent = DefaultAgent(model=model, env=env, max_steps=30)
    agent.run({issue!r})
except Exception as e:
    print(f'mini-swe-agent error: {{e}}', file=sys.stderr)
diff = subprocess.run(['git', 'diff', '--name-only'], capture_output=True, text=True, cwd='/testbed')
files = diff.stdout.strip().splitlines()
print('AGENT_RESULT:' + json.dumps({{"success": len(files) > 0, "steps": 30, "files_changed": files}}))
'''


def run_benchmarks(tasks: list[dict], evolved_agent_path: Path | None = None):
    print("\n" + "="*60)
    print("PHASE 2: Benchmark on 5 SWE-bench tasks (Docker eval)")
    print("="*60)

    # agent_name → runner_script_template
    agents = {
        "evolutor-seed": SEED_AGENT_RUNNER,
        "mini-swe-agent": MINI_SWE_RUNNER,
    }
    if evolved_agent_path and evolved_agent_path.exists():
        agents["evolutor-evolved"] = SEED_AGENT_RUNNER  # same runner, evolved code mounted

    results = {}
    for name, runner_template in agents.items():
        print(f"\n--- {name} ---")
        agent_results = []
        for task in tasks:
            print(f"  [{task['instance_id']}] running...", flush=True)
            issue = task["problem_statement"]
            runner = runner_template.format(issue=issue, model=MODEL)
            r = eval_task_docker(task, name, runner, max_steps=30)
            status = "PASS ✓" if r.passed else "FAIL ✗"
            print(f"  [{task['instance_id']}] {status}  {r.elapsed:.0f}s  steps={r.steps}")
            agent_results.append(r)
        results[name] = agent_results

    return results


def print_comparison(results: dict):
    print("\n" + "="*60)
    print("RESULTS: Qwen3-Coder-30B (local, all 8 GPUs)")
    print("="*60)

    task_ids = [r.instance_id for r in next(iter(results.values()))]
    header = f"{'Task':<35}" + "".join(f"{'  '+n[:18]:<22}" for n in results)
    print(header)
    print("-" * len(header))

    for i, tid in enumerate(task_ids):
        row = f"{tid:<35}"
        for name, res in results.items():
            r = res[i]
            cell = "PASS" if r.passed else "FAIL"
            row += f"  {cell:<20}"
        print(row)

    print("-" * len(header))
    summary = f"{'Pass rate':<35}"
    for name, res in results.items():
        passed = sum(1 for r in res if r.passed)
        total = len(res)
        avg_t = sum(r.elapsed for r in res) / max(total, 1)
        summary += f"  {passed}/{total} ({passed/total*100:.0f}%)  {avg_t:.0f}s avg{'':<4}"
    print(summary)
    print("="*60)


async def main():
    tasks = load_tasks()
    print(f"Loaded {len(tasks)} tasks: {[t['instance_id'] for t in tasks]}")

    # Phase 1: Evolution
    try:
        evo_report = await run_evolution()
    except Exception as e:
        print(f"Evolution failed: {e} — running benchmark only")

    # Phase 2: Benchmark
    results = run_benchmarks(tasks)
    print_comparison(results)

    # Save results
    out = {name: [{"instance_id": r.instance_id, "passed": r.passed,
                   "elapsed": r.elapsed, "steps": r.steps} for r in res]
           for name, res in results.items()}
    out_path = PROJECT_ROOT / "results" / "benchmark_swebench.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nResults saved to {out_path}")

    # Phase 3: Free resources
    print("\n" + "="*60)
    print("PHASE 3: Freeing GPU resources")
    print("="*60)
    subprocess.run(["pkill", "-f", "vllm"], capture_output=True)
    subprocess.run(["pkill", "-f", "proxy_server"], capture_output=True)
    print("vLLM and proxy killed. GPUs free.")


if __name__ == "__main__":
    asyncio.run(main())
