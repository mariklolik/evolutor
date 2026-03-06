#!/usr/bin/env python3
"""Run best evolved agent on all tasks for fair comparison with baseline."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evolutor.swebench.harness import eval_agent_code_docker

PROJECT_ROOT = Path(__file__).parent.parent
TASKS_FILE = PROJECT_ROOT / "results" / "available_tasks.json"
BEST_AGENT_FILE = PROJECT_ROOT / "results" / "best_evolved_agent.py"
RESULTS_FILE = PROJECT_ROOT / "results" / "evolved_benchmark.json"


def main():
    tasks = json.load(open(TASKS_FILE))
    agent_code = open(BEST_AGENT_FILE).read()
    model = os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")

    print(f"Evolved agent benchmark: {len(tasks)} tasks, model={model}")
    print(f"Agent code: {len(agent_code)} chars")
    print("=" * 60)

    results = []
    passed_count = 0

    for i, task in enumerate(tasks):
        iid = task["instance_id"]
        print(f"\n[{i+1}/{len(tasks)}] {iid}...", flush=True)
        start = time.time()

        try:
            result = eval_agent_code_docker(
                agent_code=agent_code,
                task=task,
                project_root=PROJECT_ROOT,
                model=model,
                timeout=300,
            )
            elapsed = time.time() - start
            status = "PASS" if result.passed else "FAIL"
            if result.passed:
                passed_count += 1

            entry = {
                "instance_id": iid,
                "passed": result.passed,
                "time_seconds": round(elapsed, 1),
                "error": (result.error or "")[:500],
            }
            results.append(entry)
            print(f"  {status} ({elapsed:.1f}s)", flush=True)

        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "instance_id": iid,
                "passed": False,
                "time_seconds": round(elapsed, 1),
                "error": str(e)[:500],
            })
            print(f"  ERROR: {e}", flush=True)

        # Save intermediate results
        benchmark = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": model,
            "agent": "best_evolved_51339c21",
            "total_tasks": len(tasks),
            "completed": len(results),
            "passed": passed_count,
            "pass_rate": round(passed_count / max(len(results), 1), 4),
            "results": results,
        }
        with open(RESULTS_FILE, "w") as f:
            json.dump(benchmark, f, indent=2)

    print("\n" + "=" * 60)
    print(f"EVOLVED AGENT RESULT: {passed_count}/{len(tasks)} ({100*passed_count/len(tasks):.1f}%)")
    print(f"Results saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
