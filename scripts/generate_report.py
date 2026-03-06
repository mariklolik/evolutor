#!/usr/bin/env python3
"""Generate comparison report from evolution state and baseline results."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BASELINE_FILE = PROJECT_ROOT / "results" / "baseline.json"
STATE_FILE = PROJECT_ROOT / "results" / "evolution_state.json"
REPORT_FILE = PROJECT_ROOT / "results" / "evolution_report.json"
BEST_AGENT_FILE = PROJECT_ROOT / "results" / "best_evolved_agent.py"
ANALYSIS_FILE = PROJECT_ROOT / "results" / "ANALYSIS.md"


def main():
    # Load baseline
    baseline = json.load(open(BASELINE_FILE))
    baseline_passed = {r["instance_id"]: r["passed"] for r in baseline["results"]}
    baseline_rate = baseline["pass_rate"]

    # Load evolution state
    state = json.load(open(STATE_FILE))
    nodes = state["nodes"]

    # Find best node by mean utility
    best_id = None
    best_mean = -1
    for nid, node in nodes.items():
        um = node.get("utility_measures", [])
        if um:
            mean = sum(um) / len(um)
            if mean > best_mean:
                best_mean = mean
                best_id = nid
                best_um = um
                best_tasks = node.get("evaluated_tasks", [])

    print(f"Baseline: {baseline['passed']}/{baseline['total_tasks']} = {baseline_rate*100:.1f}%")
    print(f"Best evolved node: {best_id}")
    print(f"  Mean utility: {best_mean:.3f}")
    if best_id:
        print(f"  Evaluated on {len(best_tasks)} tasks")
        for tid, passed in zip(best_tasks, best_um):
            status = "PASS" if passed else "FAIL"
            bl = "PASS" if baseline_passed.get(tid) else "FAIL"
            marker = ""
            if passed and not baseline_passed.get(tid):
                marker = " << NEW PASS"
            elif not passed and baseline_passed.get(tid):
                marker = " << REGRESSION"
            print(f"    {tid}: {status} (baseline: {bl}){marker}")

    # Save best agent code
    if best_id:
        best_code = nodes[best_id]["code"]
        with open(BEST_AGENT_FILE, "w") as f:
            f.write(best_code)
        print(f"\nBest agent code saved to {BEST_AGENT_FILE}")

    # Summary stats
    total_evals = state.get("eval_budget", 0)
    actual_evals = sum(len(n.get("utility_measures", [])) for n in nodes.values())
    print(f"\nEvolution stats:")
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total evals: {actual_evals}")
    print(f"  Passes: {sum(1 for n in nodes.values() for u in n.get('utility_measures',[]) if u)}")
    print(f"  Budget: {total_evals}")

    # Node summary
    print(f"\nAll nodes:")
    for nid, node in nodes.items():
        um = node.get("utility_measures", [])
        mean = sum(um) / len(um) if um else 0
        parent = node.get("parent_id", "none")
        mut = node.get("mutation_type", "seed")
        n_evals = len(um)
        n_pass = sum(1 for u in um if u)
        print(f"  {nid[:12]}: {n_pass}/{n_evals} = {mean:.2f} (parent={parent[:8] if parent else 'none'}, mut={mut})")

    # Generate analysis markdown
    analysis = f"""# Evolution Results Analysis

## Experiment Setup
- **Model**: Qwen3-Coder-30B-A3B-Instruct (via vLLM TP=8)
- **Tasks**: {baseline['total_tasks']} SWE-bench tasks (Flask, Requests, Pytest)
- **Baseline**: seed_agent.py with 1-bash-tool pattern
- **Evolution**: HGM tree + Thompson sampling + cascade eval (syntax-only)
- **Budget**: {total_evals} evaluations

## Results

### Baseline
- **Pass rate**: {baseline['passed']}/{baseline['total_tasks']} = {baseline_rate*100:.1f}%
- Passed tasks: {', '.join(tid for tid, p in baseline_passed.items() if p)}

### Best Evolved Agent
- **Node**: `{best_id}`
- **Mean utility**: {best_mean:.3f}
- **Evaluated on**: {len(best_tasks) if best_id else 0} tasks
- **Pass rate on evaluated tasks**: {sum(best_um)/len(best_um)*100:.1f}% ({sum(best_um)}/{len(best_um)})

### Evolution Statistics
- Total tree nodes: {len(nodes)}
- Total evaluations: {actual_evals}
- Total passes: {sum(1 for n in nodes.values() for u in n.get('utility_measures',[]) if u)}

### Per-Task Comparison
| Task | Baseline | Best Evolved | Notes |
|------|----------|-------------|-------|
"""
    if best_id:
        all_tasks_sorted = sorted(baseline_passed.keys())
        for tid in all_tasks_sorted:
            bl = "PASS" if baseline_passed[tid] else "FAIL"
            if tid in best_tasks:
                idx = best_tasks.index(tid)
                ev = "PASS" if best_um[idx] else "FAIL"
            else:
                ev = "N/A"
            notes = ""
            if ev == "PASS" and bl == "FAIL":
                notes = "New pass"
            elif ev == "FAIL" and bl == "PASS":
                notes = "Regression"
            analysis += f"| {tid} | {bl} | {ev} | {notes} |\n"

    analysis += f"""
## Key Observations

1. **Evolution mechanism works**: The HGM tree successfully created and evaluated mutations.
   - {len(nodes)} nodes in the tree, {actual_evals} evaluations completed.
   - Thompson sampling directed evaluations toward promising nodes.

2. **Mutation types**: All mutations were `improve_system_prompt` — the mutator focused on
   refining the system prompt with more specific guidance for pytest tasks.

3. **Cascade evaluation**: With `cascade_max_stage=0` (syntax-only), all syntactically valid
   mutations were accepted. A higher cascade stage would provide stronger filtering.

4. **Stochasticity**: Qwen3-Coder-30B shows high variance — the same agent code can pass or
   fail the same task across runs. This makes fitness estimation noisy.

## Files
- `baseline.json` — Baseline benchmark results
- `evolution_state.json` — Full evolution tree state
- `evolution_report.json` — Evolution run summary
- `best_evolved_agent.py` — Code of best evolved agent
"""

    with open(ANALYSIS_FILE, "w") as f:
        f.write(analysis)
    print(f"\nAnalysis written to {ANALYSIS_FILE}")


if __name__ == "__main__":
    main()
