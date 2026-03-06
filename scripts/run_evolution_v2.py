#!/usr/bin/env python3
"""Run the HGM evolution loop on SWE-bench tasks."""
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evolutor.evolution.loop import EvolutionConfig, run_evolution

PROJECT_ROOT = Path(__file__).parent.parent
TASKS_FILE = PROJECT_ROOT / "results" / "available_tasks.json"
SEED_AGENT_PATH = PROJECT_ROOT / "src" / "evolutor" / "swebench" / "seed_agent.py"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=50, help="Total eval budget")
    parser.add_argument("--cascade-stage", type=int, default=1, help="Max cascade stage (0=syntax, 1=smoke)")
    parser.add_argument("--tasks", type=int, default=0, help="Number of tasks (0=all)")
    parser.add_argument("--seed", type=str, default=None, help="Path to seed agent (default: seed_agent.py)")
    args = parser.parse_args()

    tasks = json.load(open(TASKS_FILE))
    if args.tasks > 0:
        tasks = tasks[:args.tasks]

    seed_path = args.seed or str(SEED_AGENT_PATH)
    seed_code = open(seed_path).read()

    config = EvolutionConfig(
        eval_budget=args.budget,
        expansion_alpha=0.6,
        task_timeout=300,
        cascade_max_stage=args.cascade_stage,
        plateau_window=20,
    )

    print(f"Evolution run: {len(tasks)} tasks, budget={config.eval_budget}")
    print(f"Cascade max stage: {config.cascade_max_stage}")
    print(f"Seed agent: {len(seed_code)} chars, {seed_code.count(chr(10))} lines")
    print("=" * 60)

    start = time.time()
    try:
        report = run_evolution(config, seed_code, tasks, str(PROJECT_ROOT))
    except KeyboardInterrupt:
        print("\nInterrupted! Saving partial state...")
        report = None
    except Exception as e:
        print(f"\nEvolution error: {e}")
        traceback.print_exc()
        report = None

    elapsed = time.time() - start
    print(f"\nEvolution completed in {elapsed:.0f}s ({elapsed/60:.1f}min)")

    if report:
        report_data = report.model_dump()
        report_data["elapsed_seconds"] = round(elapsed, 1)
        with open(PROJECT_ROOT / "results" / "evolution_report.json", "w") as f:
            json.dump(report_data, f, indent=2)
        print(f"\nReport:")
        print(f"  Evals: {report.evals_completed}")
        print(f"  Tree nodes: {report.tree_nodes}")
        print(f"  Best fitness: {report.best_fitness:.3f}")
        print(f"  Best agent: {report.best_agent_id}")
        print(f"  Mutations attempted: {report.mutations_attempted}")
        print(f"  Mutations accepted: {report.mutations_accepted}")
        print(f"  Cascade rejections: {report.cascade_rejections}")
        print(f"  Plateaus: {report.plateaus_detected}")
    else:
        print("No report (interrupted or error)")
        # Try to load partial state
        state_path = PROJECT_ROOT / "results" / "evolution_state.json"
        if state_path.exists():
            print(f"Partial state saved at {state_path}")


if __name__ == "__main__":
    main()
