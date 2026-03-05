"""Compare baseline and evolved agent results.

Loads results/baseline.json and results/evolution_state.json (if they exist),
prints comparison table, saves to results/comparison.json.
"""
import json
import os
from pathlib import Path

project_root = Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()
results_dir = project_root / "results"


def load_baseline() -> dict | None:
    path = results_dir / "baseline.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_evolution_state():
    path = results_dir / "evolution_state.json"
    if not path.exists():
        return None
    try:
        from evolutor.evolution.tree import EvolutionTree
        return EvolutionTree.load_state(str(path))
    except Exception as e:
        print(f"WARNING: could not load evolution state: {e}")
        return None


def load_evolution_report() -> dict | None:
    path = results_dir / "evolution_report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main():
    baseline = load_baseline()
    tree = load_evolution_state()
    evo_report = load_evolution_report()

    if baseline is None and tree is None:
        print("No results yet — run scripts/run_baseline.py and scripts/run_evolution.py first.")
        return

    print("=" * 60)
    print("EVOLUTOR RESULTS COMPARISON")
    print("=" * 60)

    # Baseline stats
    if baseline is not None:
        b_summary = baseline.get("summary", {})
        b_passed = b_summary.get("passed", 0)
        b_total = b_summary.get("total", 0)
        b_rate = b_summary.get("pass_rate", 0.0)
        print(f"\nBaseline (seed agent):")
        print(f"  Pass rate: {b_passed}/{b_total} ({b_rate:.1%})")
        if baseline.get("results"):
            for r in baseline["results"]:
                status = "PASS" if r["passed"] else "FAIL"
                print(f"  {r['instance_id']}: {status} ({r.get('time_seconds', '?')}s)")
    else:
        print("\nBaseline: No results (run scripts/run_baseline.py)")
        b_rate = 0.0
        b_total = 0

    # Evolution stats
    if tree is not None:
        best = tree.get_best_agent()
        print(f"\nEvolved agent (best: {best.id}):")
        print(f"  Mean utility: {best.mean_utility:.3f}")
        print(f"  Evaluations: {best.num_evals}")
        print(f"  Mutation type: {best.mutation_type}")
        print(f"  Description: {best.mutation_description[:100]}")
        print(f"\nTree stats:")
        print(f"  Total nodes: {tree.n_nodes}")
        print(f"  Total evals: {tree.n_evals}")
        best_rate = best.mean_utility
    else:
        print("\nEvolved: No state (run scripts/run_evolution.py)")
        best_rate = 0.0

    if evo_report is not None:
        print(f"\nEvolution summary:")
        print(f"  Mutations attempted: {evo_report.get('mutations_attempted', 0)}")
        print(f"  Mutations accepted:  {evo_report.get('mutations_accepted', 0)}")
        print(f"  Cascade rejections:  {evo_report.get('cascade_rejections', 0)}")
        print(f"  Plateaus detected:   {evo_report.get('plateaus_detected', 0)}")

    # Delta
    if baseline is not None and tree is not None:
        delta = best_rate - b_rate
        print(f"\nImprovement: {b_rate:.1%} → {best_rate:.1%} ({delta:+.1%})")

    # Save comparison
    comparison = {
        "baseline_pass_rate": b_rate,
        "baseline_total": b_total,
        "evolved_pass_rate": best_rate,
        "best_agent_id": best.id if tree else None,
        "tree_nodes": tree.n_nodes if tree else 0,
        "tree_evals": tree.n_evals if tree else 0,
    }
    out = results_dir / "comparison.json"
    out.write_text(json.dumps(comparison, indent=2))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
