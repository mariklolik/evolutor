"""Run Evolutor HGM evolution loop on available SWE-bench Docker tasks.

Loads seed agent, discovers tasks, runs evolution with budget, saves report.

Usage:
    python3 scripts/run_evolution.py [--budget N]

NOTE: vLLM + proxy must be running. See MEMORY.md for startup commands.
NOTE: For MLflow experiment tracking, set MLFLOW_TRACKING_URI env var.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

project_root = Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()
results_dir = project_root / "results"
results_dir.mkdir(exist_ok=True)


def discover_tasks() -> list[dict]:
    """Load tasks from available_tasks.json or discover via Docker."""
    available_path = results_dir / "available_tasks.json"

    if available_path.exists():
        instance_ids = json.loads(available_path.read_text())
    else:
        try:
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True, text=True, timeout=10,
            )
            instance_ids = []
            for line in result.stdout.splitlines():
                if "sweb.eval.x86_64." in line:
                    repo = line.split(":")[0]
                    prefix = "sweb.eval.x86_64."
                    if prefix in repo:
                        instance_ids.append(repo[repo.index(prefix) + len(prefix):])
            instance_ids = sorted(set(instance_ids))
        except Exception as e:
            print(f"WARNING: docker discovery failed: {e}")
            instance_ids = []

    if not instance_ids:
        print("No Docker images found — no tasks to evolve on.")
        return []

    # Load SWE-bench task data
    try:
        import datasets  # type: ignore
        ds = datasets.load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        id_set = set(instance_ids)
        tasks = [dict(t) for t in ds if t["instance_id"] in id_set]
        print(f"Loaded {len(tasks)} matching SWE-bench tasks")
        return tasks
    except Exception as e:
        print(f"WARNING: dataset load failed: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Run Evolutor HGM evolution")
    parser.add_argument("--budget", type=int, default=100,
                        help="Total eval budget (default: 100)")
    parser.add_argument("--cascade-stage", type=int, default=1,
                        help="Max cascade stage 0-3 (default: 1)")
    args = parser.parse_args()

    # Load seed agent
    seed_agent_path = project_root / "src/evolutor/swebench/seed_agent.py"
    seed_code = seed_agent_path.read_text()
    print(f"Loaded seed agent: {len(seed_code)} chars")

    # Discover tasks
    tasks = discover_tasks()
    if not tasks:
        print("No tasks available. Exiting.")
        return

    # Build config
    from evolutor.evolution.loop import EvolutionConfig, run_evolution
    config = EvolutionConfig(
        eval_budget=args.budget,
        cascade_max_stage=args.cascade_stage,
    )
    print(f"Evolution config: budget={config.eval_budget}, cascade_stage={config.cascade_max_stage}")
    print(f"Tasks: {[t['instance_id'] for t in tasks]}")

    # Run evolution
    try:
        report = run_evolution(config, seed_code, tasks, str(project_root))
    except Exception as e:
        print(f"ERROR: run_evolution failed: {e}")
        import traceback
        traceback.print_exc()
        # Try to load partial state
        state_path = results_dir / "evolution_state.json"
        if state_path.exists():
            from evolutor.evolution.tree import EvolutionTree
            tree = EvolutionTree.load_state(str(state_path))
            best = tree.get_best_agent()
            print(f"Partial state: {tree.n_evals} evals, {tree.n_nodes} nodes, "
                  f"best={best.id} ({best.mean_utility:.2f})")
        return

    # Save report
    report_path = results_dir / "evolution_report.json"
    report_path.write_text(json.dumps(report.model_dump(), indent=2))
    print(f"\nEvolution complete:")
    print(f"  Evals: {report.evals_completed}/{config.eval_budget}")
    print(f"  Nodes: {report.tree_nodes}")
    print(f"  Best agent: {report.best_agent_id} (fitness={report.best_fitness:.3f})")
    print(f"  Mutations: {report.mutations_attempted} attempted, "
          f"{report.mutations_accepted} accepted")
    print(f"  Cascade rejections: {report.cascade_rejections}")
    print(f"  Plateaus: {report.plateaus_detected}")
    print(f"Saved report to {report_path}")


if __name__ == "__main__":
    main()
