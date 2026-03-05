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


def eval_task_local(task: dict, agent_fn, max_steps: int = 25) -> TaskResult:
    """Clone repo at base commit, run agent, check FAIL_TO_PASS tests."""
    instance_id = task["instance_id"]
    repo_url = f"https://github.com/{task['repo']}.git"

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "repo"
        t0 = time.time()
        try:
            subprocess.run(
                ["git", "clone", "--depth=200", repo_url, str(repo_root)],
                capture_output=True, check=True, timeout=90,
            )
            subprocess.run(
                ["git", "checkout", task["base_commit"]],
                capture_output=True, check=True, cwd=repo_root, timeout=30,
            )
            # Apply test patch (adds the FAIL_TO_PASS test cases)
            subprocess.run(
                ["git", "apply", "-"],
                input=task["test_patch"], text=True,
                capture_output=True, cwd=repo_root, timeout=10,
            )
            subprocess.run(
                ["pip", "install", "-e", ".", "-q"],
                capture_output=True, cwd=repo_root, timeout=120,
            )

            # Run agent
            result = agent_fn(
                issue=task["problem_statement"],
                repo_root=repo_root,
                model=MODEL,
                max_steps=max_steps,
            )

            # Evaluate
            fail_tests = task["FAIL_TO_PASS"]
            test_out = subprocess.run(
                ["python3", "-m", "pytest"] + fail_tests + ["-x", "-q", "--tb=short"],
                capture_output=True, text=True, cwd=repo_root, timeout=60,
            )
            passed = test_out.returncode == 0
            return TaskResult(
                instance_id=instance_id,
                passed=passed,
                elapsed=time.time() - t0,
                steps=result.get("steps", 0),
                files_changed=result.get("files_changed", []),
                error="" if passed else test_out.stdout[-300:],
            )
        except Exception as e:
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


def run_benchmarks(tasks: list[dict], evolved_agent_path: Path | None = None):
    print("\n" + "="*60)
    print("PHASE 2: Benchmark on 5 SWE-bench tasks")
    print("="*60)

    agents = {
        "evolutor-seed (pre-evolution)": load_evolutor_agent(
            PROJECT_ROOT / "src/evolutor/swebench/seed_agent.py"
        ),
        "mini-swe-agent": make_mini_swe_agent_fn(),
    }
    if evolved_agent_path and evolved_agent_path.exists():
        agents["evolutor-evolved"] = load_evolutor_agent(evolved_agent_path)

    results = {}
    for name, agent_fn in agents.items():
        print(f"\n--- {name} ---")
        agent_results = []
        for task in tasks:
            print(f"  [{task['instance_id']}] running...", flush=True)
            r = eval_task_local(task, agent_fn, max_steps=25)
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
