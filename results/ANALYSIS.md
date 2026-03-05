# Evolutor Results Analysis

## Baseline Performance

| Task | Status | Time (s) | Error |
|------|--------|----------|-------|
| _(run scripts/run_baseline.py to populate)_ | — | — | — |

**Baseline pass rate**: _/_ (_%)

---

## Evolution Run Summary

| Metric | Value |
|--------|-------|
| Eval budget | — |
| Evals completed | — |
| Tree nodes | — |
| Mutations attempted | — |
| Mutations accepted | — |
| Cascade rejections | — |
| Plateaus detected | — |

_(run scripts/run_evolution.py to populate)_

---

## Best Evolved Agent

- **Agent ID**: —
- **Fitness (mean utility)**: —
- **Mutation type**: —
- **Description**: —
- **Code delta**: _(git diff seed vs best will appear here)_

---

## Improvement Comparison

| System | Pass Rate | Delta |
|--------|-----------|-------|
| Seed agent (baseline) | — | — |
| Best evolved agent | — | — |
| Expected (HGM +8-15%) | — | — |

_(run scripts/compare_results.py to populate)_

---

## Mutation Type Success Rates

| Mutation Type | Attempted | Accepted | Rate |
|---------------|-----------|----------|------|
| improve_system_prompt | — | — | — |
| add_tool_template | — | — | — |
| improve_reflection | — | — | — |
| add_workflow_hint | — | — | — |
| optimize_parameters | — | — | — |

---

## Emergent Behaviors

_(To be filled after evolution run — examples from other systems:)_

- **Tool creation**: Agent writes Python scripts to `/tmp/` for complex search/edit operations
- **Error recovery**: Agent develops retry patterns when bash commands fail
- **Progressive exploration**: Agent learns to explore code structure before editing
- **Test-driven fixing**: Agent learns to run tests to verify fixes

---

## Ablation Notes

| Component | Expected Impact | Observed |
|-----------|----------------|----------|
| HGM Thompson sampling | Better parent selection | — |
| Cascade evaluation | 3-5x compute savings | — |
| MAP-Elites archive | Diversity preservation | — |
| Plateau detection | Escape local optima | — |
| DGM-style diagnosis | Targeted mutations | — |
| Kernel integrity check | Prevent reward hacking | — |

---

## How to Run

```bash
# 1. Start vLLM (takes ~100s)
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 python /tmp/launch_vllm2.py &

# 2. Start proxy
python3 scripts/proxy_server.py --port 4000 --backend http://127.0.0.1:8000/v1 --model qwen3-coder-30b &

# 3. Run baseline
no_proxy="localhost,127.0.0.1,0.0.0.0,::1" NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1" \
ANTHROPIC_BASE_URL="http://127.0.0.1:4000" ANTHROPIC_API_KEY="sk-local" \
EVOLUTOR_MODEL="claude-sonnet-4-6" EVOLUTOR_PROJECT_ROOT="/home/mekashirskiy/evolutor" \
python3 scripts/run_baseline.py

# 4. Run evolution (100 eval budget)
no_proxy="localhost,127.0.0.1,0.0.0.0,::1" NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1" \
ANTHROPIC_BASE_URL="http://127.0.0.1:4000" ANTHROPIC_API_KEY="sk-local" \
EVOLUTOR_MODEL="claude-sonnet-4-6" EVOLUTOR_PROJECT_ROOT="/home/mekashirskiy/evolutor" \
python3 scripts/run_evolution.py --budget 100

# 5. Compare
EVOLUTOR_PROJECT_ROOT="/home/mekashirskiy/evolutor" python3 scripts/compare_results.py
```
