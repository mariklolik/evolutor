"""Run seed agent baseline on all available SWE-bench Docker instances.

Discovers Docker images dynamically, loads corresponding SWE-bench task data,
evaluates seed_agent.py on each task, and saves results to results/baseline.json.

NOTE: vLLM should be running with --enable-prefix-caching for 2-3x speedup
on repeated system prompts across agent evaluations.
"""
import json
import os
import subprocess
import time
from pathlib import Path

project_root = Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()


def discover_docker_tasks() -> list[str]:
    """Discover available SWE-bench Docker images and return instance_ids."""
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, timeout=10,
        )
        images = [
            line.strip()
            for line in result.stdout.splitlines()
            if "sweb.eval.x86_64." in line
        ]
        instance_ids = []
        for img in images:
            # Format: sweb.eval.x86_64.{instance_id}:latest
            repo = img.split(":")[0]
            prefix = "sweb.eval.x86_64."
            if prefix in repo:
                instance_id = repo[repo.index(prefix) + len(prefix):]
                if instance_id:
                    instance_ids.append(instance_id)
        return sorted(set(instance_ids))
    except Exception as e:
        print(f"WARNING: docker discovery failed: {e}")
        return []


def load_task_by_instance_id(instance_id: str, ds) -> dict | None:
    """Find task in HuggingFace dataset by instance_id."""
    for task in ds:
        if task["instance_id"] == instance_id:
            return dict(task)
    return None


def main():
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)

    # Discover available Docker tasks
    instance_ids = discover_docker_tasks()
    print(f"Found {len(instance_ids)} Docker images: {instance_ids}")

    # Save available tasks list
    available_path = results_dir / "available_tasks.json"
    available_path.write_text(json.dumps(instance_ids, indent=2))
    print(f"Saved to {available_path}")

    if not instance_ids:
        print("No Docker images found. Exiting.")
        return

    # Load SWE-bench dataset
    try:
        import datasets  # type: ignore
        ds = datasets.load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        print(f"Loaded {len(ds)} SWE-bench Lite tasks")
    except Exception as e:
        print(f"WARNING: Could not load HuggingFace dataset: {e}")
        ds = []

    # Load seed agent code
    seed_agent_path = project_root / "src/evolutor/swebench/seed_agent.py"
    agent_code = seed_agent_path.read_text()
    print(f"Loaded seed agent: {len(agent_code)} chars")

    # Import eval function
    from evolutor.swebench.harness import eval_agent_code_docker

    model = os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")
    results = []

    for instance_id in instance_ids:
        print(f"\n--- {instance_id} ---")

        # Find task data
        task = load_task_by_instance_id(instance_id, ds) if ds else None
        if task is None:
            print(f"  SKIP: task data not found in dataset")
            results.append({
                "instance_id": instance_id,
                "passed": False,
                "time_seconds": 0,
                "steps": 0,
                "error": "task not found in dataset",
            })
            continue

        start = time.time()
        try:
            result = eval_agent_code_docker(
                agent_code=agent_code,
                task=task,
                project_root=project_root,
                model=model,
                timeout=600,
            )
            elapsed = time.time() - start
            status = "PASS" if result.passed else "FAIL"
            print(f"  {status} ({elapsed:.0f}s) error={result.error}")
            results.append({
                "instance_id": instance_id,
                "passed": result.passed,
                "time_seconds": round(elapsed, 1),
                "steps": result.steps,
                "error": result.error,
            })
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ERROR ({elapsed:.0f}s): {e}")
            results.append({
                "instance_id": instance_id,
                "passed": False,
                "time_seconds": round(elapsed, 1),
                "steps": 0,
                "error": str(e),
            })

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    pct = 100 * passed / total if total else 0
    print(f"\nBaseline: {passed}/{total} ({pct:.0f}%)")

    baseline_path = results_dir / "baseline.json"
    baseline_path.write_text(json.dumps({
        "summary": {"passed": passed, "total": total, "pass_rate": round(pct / 100, 3)},
        "model": model,
        "results": results,
    }, indent=2))
    print(f"Saved baseline results to {baseline_path}")


if __name__ == "__main__":
    main()
