#!/usr/bin/env python3
"""Run multiple benchmark passes for variance estimation."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evolutor.swebench.harness import eval_agent_code_docker

PROJECT_ROOT = Path(__file__).parent.parent
TASKS_FILE = PROJECT_ROOT / "results" / "available_tasks.json"


def run_benchmark(agent_code, tasks, model, run_id, results_file):
    """Run one complete benchmark pass."""
    results = []
    passed_count = 0

    for i, task in enumerate(tasks):
        iid = task["instance_id"]
        print(f"\n[Run {run_id}][{i+1}/{len(tasks)}] {iid}...", flush=True)
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
            if result.passed:
                passed_count += 1
            results.append({
                "instance_id": iid,
                "passed": result.passed,
                "time_seconds": round(elapsed, 1),
                "error": (result.error or "")[:500],
            })
            status = "PASS" if result.passed else "FAIL"
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

        # Save after each task
        data = {
            "run_id": run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": model,
            "total_tasks": len(tasks),
            "completed": len(results),
            "passed": passed_count,
            "pass_rate": round(passed_count / max(len(results), 1), 4),
            "results": results,
        }
        with open(results_file, "w") as f:
            json.dump(data, f, indent=2)

    return passed_count


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, help="Path to agent code file")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument("--label", default="agent", help="Label for output files")
    args = parser.parse_args()

    tasks = json.load(open(TASKS_FILE))
    agent_code = open(args.agent).read()
    model = os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")

    print(f"Multi-benchmark: {args.runs} runs, {len(tasks)} tasks, model={model}")
    print(f"Agent: {args.agent} ({len(agent_code)} chars)")
    print("=" * 60)

    all_results = []
    for run_id in range(1, args.runs + 1):
        results_file = PROJECT_ROOT / "results" / f"{args.label}_run{run_id}.json"
        print(f"\n{'='*60}")
        print(f"Starting run {run_id}/{args.runs}")
        print(f"{'='*60}")
        start = time.time()
        passed = run_benchmark(agent_code, tasks, model, run_id, results_file)
        elapsed = time.time() - start
        all_results.append(passed)
        print(f"\nRun {run_id}: {passed}/{len(tasks)} = {passed/len(tasks)*100:.1f}% ({elapsed:.0f}s)")

    print(f"\n{'='*60}")
    print(f"SUMMARY: {all_results}")
    mean = sum(all_results) / len(all_results)
    print(f"Mean: {mean:.1f}/{len(tasks)} = {mean/len(tasks)*100:.1f}%")


if __name__ == "__main__":
    main()
