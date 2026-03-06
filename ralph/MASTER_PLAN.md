# Evolutor Master Plan — From Current State to SOTA

> **UPDATED 2026-03-05**: Revised after deep research. See `ralph/REVISED_ARCHITECTURE.md`
> for the hybrid runtime+offline evolution design incorporating Live-SWE-agent findings.
> See `ralph/deep_research_findings.md` for all paper details.
> See `ralph/self-evolving-agent-loops/` for research outline and field definitions.

## Situation Assessment

### What We Have (Working)
- Evolution loop with SWE-bench Docker eval (loop.py, 474 lines)
- seed_agent.py with 4 tools + step-reflection (270 lines)
- MAP-Elites archive with CMP Thompson sampling (archive.py, 182 lines)
- Plateau detection with ruptures (plateau.py, 49 lines)
- Proxy server: Anthropic SDK → vLLM/Qwen3 (proxy_server.py, 249 lines)
- Docker SWE-bench harness with test_patch (harness.py, 317 lines)
- Benchmark runner (run_benchmark.py, 389 lines)

### What's Broken
- **seed_agent exits at step 0** on most tasks (LLM returns end_turn immediately)
- **Only 1/5 tasks "passed"** and that was a false positive (test passes at base commit)
- **0% real pass rate** — the agent never actually fixes anything
- **Overengineered seed** — 4 custom tools + THOUGHT/ACTION format confuses Qwen3

### Critical Insight from Competitors
mini-swe-agent achieves **74% on SWE-bench** with:
- 1 tool (bash)
- ~100 lines of code
- Linear message history
- Standard tool_call format

Our 270-line seed_agent with custom tool schemas is the #1 bottleneck.

---

## Architecture: What Evolutor Should Be

### The 3 Separable Concerns

```
┌─────────────────────────────────────────────────┐
│  EVOLUTION ENGINE (outer loop)                   │
│  HGM-style tree + OpenEvolve MAP-Elites         │
│  Selects parent → mutates → evaluates → archives │
├─────────────────────────────────────────────────┤
│  SEED AGENT (the thing being evolved)            │
│  mini-swe-agent style: bash tool + linear loop   │
│  This is what gets better over generations        │
├─────────────────────────────────────────────────┤
│  EVAL HARNESS (immutable)                        │
│  Docker containers, SWE-bench tasks, pytest      │
│  Cannot be modified by evolution                  │
└─────────────────────────────────────────────────┘
```

### Evolution Engine Design (Combining Best of All)

```
FROM HGM:  CMP Thompson sampling for parent selection
           Decoupled expansion/measurement budget
           Binary 0/1 utility per task

FROM OpenEvolve: MAP-Elites behavioral grid (complexity × novelty)
                 Cascading evaluation (syntax → smoke → full)
                 LLM ensemble (fast model 80%, strong model 20%)
                 Island model with ring migration

FROM DGM:  Problem diagnosis before mutation
           Entry categorization (empty patches, stochasticity, context length)
           Full archive tree (always append, never discard)

FROM SICA: Structured self-improvement reasoning
           Review committee for mutation quality
           Cost + time tracking in utility function

NOVEL:     Immutable kernel (SHA-verified eval harness)
           Plateau detection → diversification triggers
           Multi-objective Pareto (pass_rate × cost × time × robustness)
```

---

## Execution Plan — 10 Hours on 8×H100

### Constraints
- **Model**: Qwen3-Coder-30B BF16 on vLLM (port 8000, TP=8)
- **Proxy**: proxy_server.py on port 4000 (Anthropic SDK format)
- **No internet**: GitHub unreachable, all Docker images must be local
- **Docker images**: 9 flask/requests SWE-bench instances available

### Phase 0: Fix the Seed Agent (Hour 0-1) ★ HIGHEST PRIORITY
**Goal: Get from 0% to >0% real pass rate**

1. **Rewrite seed_agent.py** to mini-swe-agent pattern:
   - Single `bash` tool via standard tool_call format
   - Linear message history (no THOUGHT/ACTION parsing)
   - System prompt: "You are a helpful assistant that can interact with a computer shell to solve programming tasks."
   - Instance prompt: problem_statement + recommended workflow
   - Submission: `git diff` output as patch
   - Max 50 steps, 10min timeout

2. **Test manually** on 1 task before evolution:
   ```bash
   # Start vLLM + proxy, then:
   python -c "from evolutor.swebench.seed_agent import solve_task; ..."
   ```

3. **Verify**: agent actually runs bash commands, reads files, edits code

### Phase 1: Fix Evolution Loop (Hour 1-3)
**Goal: Evolution loop that actually produces improvements**

1. **Simplify loop.py** — remove cruft, implement clean HGM algorithm:
   ```
   Tree = {Node(id, commit_id, utility_measures=[], children=[], parent_id)}

   for eval_budget in range(MAX_EVALS):
     if should_expand():  # n_evals^0.6 >= n_nodes
       parent = thompson_sample(tree)  # CMP over descendant evals
       child = mutate(parent)          # LLM generates code changes
       tree.add(child, parent_id=parent.id)
     else:
       node = thompson_sample(tree)    # which node to evaluate
       task = select_task(node)        # which SWE-bench task
       result = eval_in_docker(node, task)  # 0 or 1
       node.utility_measures.append(result)
   ```

2. **Implement mutation** following DGM pattern:
   - Diagnose: send agent code + failed task logs to LLM
   - LLM outputs: what to change and why
   - Apply changes to seed_agent.py copy
   - Verify syntax (cascade stage 1)

3. **Implement cascading evaluation** (from OpenEvolve):
   - Stage 0: `python -c "import seed_agent"` (syntax check, <1s)
   - Stage 1: Run on 1 easy task (smoke test, <60s)
   - Stage 2: Run on 3 tasks (medium eval, <5min)
   - Stage 3: Run on all available tasks (full eval, <15min)

### Phase 2: Baseline Benchmark (Hour 3-4)
**Goal: Establish pass rate of seed agent v0**

1. Run seed_agent on all 9 available Docker instances
2. Record per-task results: pass/fail, time, tokens, steps
3. This is generation 0 — the baseline for evolution

### Phase 3: Evolution Run (Hour 4-8)
**Goal: Run 10-20 evolution generations**

1. Start evolution loop with:
   - `max_evals = 100` (budget: 100 task evaluations)
   - `expansion_alpha = 0.6` (HGM default)
   - Cascade thresholds: syntax→1task→3tasks→all

2. Monitor:
   - Best pass rate per generation
   - Number of unique agents in archive
   - Mutation types that succeed
   - Time per evaluation

3. **Expected emergent behaviors** (from DGM paper):
   - Patch validation (test before submit)
   - Better file exploration (smarter grep/find)
   - Error memory (don't repeat failed approaches)
   - Multi-attempt generation (try multiple patches)

### Phase 4: Compare & Iterate (Hour 8-10)
**Goal: Measure improvement, diagnose gaps, fix**

1. Take best evolved agent
2. Run on all 9 tasks
3. Compare: seed v0 vs best evolved
4. If improved → document, commit
5. If not → analyze failure logs, fix mutation prompts, re-run

---

## Implementation Priority Queue

### P0 — Must Do (blocks everything)
| Task | File | Description |
|------|------|-------------|
| Rewrite seed_agent | swebench/seed_agent.py | mini-swe-agent pattern: 1 bash tool |
| Fix agent-exits-step-0 | swebench/seed_agent.py | Ensure tool_call format works with Qwen3 |
| Manual test 1 task | scripts/ | Verify agent runs, reads, edits, submits |

### P1 — Core Evolution
| Task | File | Description |
|------|------|-------------|
| HGM tree structure | evolution/loop.py | Node class + Thompson sampling + expansion control |
| Mutation engine | evolution/mutator.py | DGM-style diagnosis + LLM code modification |
| Cascade evaluator | evolution/cascade.py | 4-stage: syntax → smoke → medium → full |
| Run baseline | scripts/run_benchmark.py | All 9 tasks, record generation 0 |

### P2 — Enhancements (if time permits)
| Task | File | Description |
|------|------|-------------|
| MAP-Elites grid | evolution/archive.py | Behavioral diversity (complexity × novelty) |
| Island model | evolution/archive.py | 2-3 islands with ring migration |
| LLM ensemble | evolution/mutator.py | Fast model 80% / strong model 20% |
| Plateau detection | evolution/plateau.py | Already implemented, wire into loop |
| Artifact feedback | evolution/mutator.py | Feed failed eval errors back into mutation prompt |

### P3 — Paper Contributions (later)
| Task | File | Description |
|------|------|-------------|
| Multi-objective Pareto | evolution/fitness.py | NSGA-III with 4 objectives |
| Immutable kernel | kernel/ | SHA verification of eval harness |
| Cross-model transfer | scripts/ | Optimize with Qwen3, test with Claude |
| Ablation experiments | scripts/ | Remove each component, measure impact |

---

## Key Design Decisions

### 1. seed_agent.py Architecture
```python
# BEFORE (broken):
tools = [bash_tool, view_file_tool, edit_file_tool, search_code_tool]
# Custom THOUGHT/ACTION format that Qwen3 doesn't understand

# AFTER (mini-swe-agent style):
tools = [{"type": "function", "function": {"name": "bash", "parameters": {"command": str}}}]
# Standard tool_call format, model does everything via bash
```

### 2. Evolution Loop Architecture
```python
# BEFORE (hardcoded SWE-bench eval):
for gen in range(10):
    mutant = mutate(current_best)
    score = eval_all_tasks(mutant)
    if score >= baseline: accept

# AFTER (HGM tree with budget):
tree = Tree(root=seed_agent)
for _ in range(eval_budget):
    if should_expand():
        parent = thompson_sample_cmp(tree)
        child = diagnose_and_mutate(parent)
        tree.add_child(parent, child)
    else:
        node = thompson_sample_cmp(tree)
        task = next_unevaluated_task(node)
        result = cascade_eval(node, task)
        node.record(result)
```

### 3. Mutation Strategy
```python
# DGM-proven approach:
def mutate(parent_agent, failed_task_logs):
    diagnosis = llm.generate(
        system="Analyze this coding agent and suggest ONE improvement.",
        user=f"""
Agent code:
{parent_agent.code}

Failed task logs:
{failed_task_logs}

Output JSON: {{
  "failure_analysis": "...",
  "improvement_plan": "...",
  "implementation": "..."  # Actual code changes
}}
"""
    )
    return apply_changes(parent_agent, diagnosis.implementation)
```

### 4. What Gets Evolved
- `seed_agent.py` — the entire file
- This includes: system prompt, tool definitions, loop logic, error handling
- Evolution can add new tools, change the loop, modify prompts
- Evolution CANNOT modify: eval harness, Docker setup, evolution loop itself

---

## Success Criteria

### Minimum Viable (end of 10h session)
- [ ] seed_agent v0 solves ≥1/9 tasks (real, not false positive)
- [ ] Evolution loop runs ≥5 generations without crashing
- [ ] Best evolved agent solves ≥ seed_agent v0

### Target
- [ ] seed_agent v0 solves ≥2/9 tasks
- [ ] Evolution produces agent solving ≥4/9 tasks
- [ ] Documented comparison table: baseline vs evolved

### Stretch
- [ ] Evolved agent beats all competitors on same 9 tasks
- [ ] Evolution discovers emergent behaviors (patch validation, error memory)
- [ ] Paper-ready results with ablation data

---

## File Map (What Goes Where)

```
src/evolutor/
├── swebench/
│   ├── seed_agent.py      ← REWRITE (mini-swe-agent style, P0)
│   └── harness.py         ← KEEP (Docker eval, working)
├── evolution/
│   ├── loop.py            ← REWRITE (HGM tree algorithm, P1)
│   ├── mutator.py         ← REWRITE (DGM diagnosis + mutation, P1)
│   ├── cascade.py         ← FIX (4-stage cascade, P1)
│   ├── archive.py         ← ENHANCE (add MAP-Elites grid, P2)
│   └── plateau.py         ← KEEP (working, wire into loop)
├── kernel/
│   ├── evaluator.py       ← KEEP (invariant checks)
│   └── invariants.py      ← KEEP (safety checks)
└── sandbox/
    └── docker.py          ← KEEP (Docker lifecycle)

scripts/
├── proxy_server.py        ← KEEP (Anthropic→OpenAI, working)
└── run_benchmark.py       ← SIMPLIFY (just eval, P1)
```
