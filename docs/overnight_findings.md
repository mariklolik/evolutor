# Overnight Session Findings — 2026-03-05

## Summary

Fixed 4 critical non-functional stubs in the Evolutor codebase. All changes committed and pushed to `origin/dev`.

---

## Fix 1: `src/evolutor/evolution/mutator.py` — Real LLM Mutations

**Problem:** The `Mutator` class had `generate_mutation()` which only created a `Mutation` data object with metadata (type, description, prompt) but never actually called an LLM to produce any code changes. The mutation was effectively a no-op.

**Fix:** Added `apply_mutation()` async method and `_extract_json_files()` helper.

- `apply_mutation()` reads target files (up to 3, skipping files >40KB), constructs a DGM-style prompt with full file content + mutation goal, and calls the Anthropic API at `ANTHROPIC_BASE_URL` (defaults to `http://localhost:4000` — local vLLM).
- The LLM is instructed to return JSON `{filepath: new_content}`.
- `_extract_json_files()` robustly parses the LLM response, stripping markdown fences before JSON parsing, with a regex fallback to find embedded JSON objects.
- Also added `from pathlib import Path` import at module level.

**Commit:** `ca9fa18` — `fix(mutator): add apply_mutation() with real LLM calls — DGM-style diff generation`

---

## Fix 2: `src/evolutor/evolution/loop.py` — Real Cascade Evaluation

**Problem:** The `run()` method used a hardcoded placeholder fitness:
```python
fitness = FitnessVector(test_pass_rate=0.9 + (gen * 0.01), ...)
```
This meant no real evaluation ever happened — every generation trivially "improved" regardless of mutation quality. No LLM was called, no tests were run, no files were changed.

**Fix:** Replaced the entire loop body with a real cascade evaluation pipeline:

1. **LLM Mutation** — calls `mutator.apply_mutation()` for the target file (rotates through 4 evolvable files).
2. **Temp copy isolation** — `shutil.copytree()` to a tmpdir, applies mutations there.
3. **CASCADE STAGE 0** — `ruff check --select=E9,F` for fast syntax/import error rejection.
4. **CASCADE STAGE 1** — `pytest tests/unit/` with `PYTHONPATH` set, parses pass/fail counts, rejects if `pass_rate < 0.85` or `(failed > 0 and total > 5)`.
5. **ACCEPT** — only if tests pass: writes mutations to real codebase, calls `git commit`.
6. **Archive + CMP** — records fitness, calls `select_parent_by_cmp()` and `update_clade_stats()`.
7. **Plateau detection** — records real `pass_rate` (not a formula).

**Commit:** `1265092` — `fix(loop): replace placeholder fitness with real cascade eval (ruff+pytest) — no more fake 0.9+gen*0.01`

---

## Fix 3: `src/evolutor/evolution/plateau.py` — ruptures PELT Changepoint Detection

**Problem:** The `detect()` method used only simple variance analysis on a rolling window — a blunt instrument that can both false-positive (small variance in improving trend) and false-negative (variance is noisy).

**Fix:** Replaced with ruptures PELT (Pruned Exact Linear Time) changepoint detection using RBF kernel:

- If no changepoint is found in the window AND `std < 0.02`, it's a plateau.
- If a changepoint is found, evolution is actively progressing — not a plateau.
- Graceful fallback to the original variance method if `ruptures` is not installed or raises.

**Commit:** `694ab70` — `fix(plateau): add ruptures PELT changepoint detection with variance fallback`

---

## Fix 4: `src/evolutor/evolution/archive.py` — CMP Thompson Sampling

**Problem:** The archive had no parent selection mechanism and no lineage tracking. The evolution loop couldn't choose which existing solution to evolve from based on evolutionary productivity.

**Fix:** Added two methods implementing HGM (Hierarchical Generative Model) Clade-Metaproductivity:

- `select_parent_by_cmp()`: Thompson sampling with Beta distribution. Each solution's clade has `wins` and `losses` counts; we sample `Beta(1+wins, 1+losses)` and pick the highest sample. This naturally balances exploration (uncertain lineages) vs exploitation (proven lineages). Falls back to highest-fitness selection when using the ribs archive.
- `update_clade_stats()`: Propagates descendant outcomes up the full lineage tree. When a child succeeds/fails, all ancestors' win/loss counts are updated. This implements the CMP insight: a parent that consistently produces successful children has high evolutionary fertility.

Both methods lazily initialize `_clade` and `_lineage` dicts so they don't break the existing constructor.

**Commit:** `668c585` — `feat(archive): add CMP Thompson sampling parent selection — HGM §3.2 Algorithm 1`

---

## Environment Notes

- All LLM calls route through `ANTHROPIC_BASE_URL` (default: `http://localhost:4000`) — no paid API used.
- Model used: `EVOLUTOR_MODEL` env var (default: `claude-sonnet-4-6`).
- `ruptures` and `numpy` are optional dependencies with graceful fallbacks.
- `ruff` must be installed in the Python environment for cascade stage 0 to function (otherwise subprocess returns non-zero and all mutations are rejected at that stage).

## Commits Pushed (Session 1)

```
668c585 feat(archive): add CMP Thompson sampling parent selection — HGM §3.2 Algorithm 1
694ab70 fix(plateau): add ruptures PELT changepoint detection with variance fallback
1265092 fix(loop): replace placeholder fitness with real cascade eval (ruff+pytest) — no more fake 0.9+gen*0.01
ca9fa18 fix(mutator): add apply_mutation() with real LLM calls — DGM-style diff generation
```

---

# Session 2 — New Modules (2026-03-05)

## Session Start
- Date: 2026-03-05
- Models: Qwen3-Coder-30B-FP8 (primary), Qwen3-8B (secondary)

## Infrastructure Status
- [ ] vLLM primary (port 8000): pending
- [ ] vLLM secondary (port 8001): pending
- [ ] litellm proxy (port 4000): pending

## New Modules Created

### Module 1: `src/evolutor/swebench/__init__.py`
Empty package init for the new `swebench` module namespace.
- **Commit:** `209c217` — `feat(swebench): add swebench package __init__.py`

### Module 2: `src/evolutor/swebench/seed_agent.py`
The SEED AGENT — minimal coding agent the evolution loop will improve over generations.
- **Design:** mini-SWE-agent radical simplicity (~270 lines total) + Live-SWE-agent §3.2 step-reflection.
- **4 tools:** `bash`, `view_file`, `edit_file`, `search_code` (ripgrep-backed).
- **Format:** THOUGHT/ACTION pattern, better than XML/JSON for LLM reasoning about code.
- **Step-reflection:** `STEP_REFLECT_SUFFIX` appended to every tool result, prompting the agent to self-assess progress after each action.
- **LLM routing:** Uses `ANTHROPIC_BASE_URL` (default `http://localhost:4000`) + `EVOLUTOR_MODEL` env vars.
- **Returns:** `{"success": bool, "summary": str, "steps": int, "files_changed": list}`
- **Commit:** `8460461` — `feat(swebench): add seed_agent.py — mini-SWE-agent scaffold + Live-SWE-agent step-reflection`

### Module 3: `src/evolutor/evolution/cascade.py`
4-stage cascading evaluator — AlphaEvolve/OpenEvolve ~10x throughput pattern.
- **Stage 0:** `ruff check --select=E9,F401,F811,F821,F841` + `ast.parse()` (<100ms, rejects syntax errors)
- **Stage 1:** `pytest tests/unit/ -x --timeout=20`, reject if `pass_rate < 0.85`
- **Stage 2:** `pytest tests/scenario/` or `tests/integration/`, reject if `pass_rate < 0.70`
- **Stage 3:** Full eval passed — returns `CascadeResult(passed=True, stage_reached="stage3_full")`
- **LLM feedback:** `format_artifacts_for_llm()` returns structured error context for mutation self-repair.
- **Key class:** `CascadeResult` dataclass with `passed`, `stage_reached`, `pass_rate`, `artifacts`, `reason`.
- **Commit:** `c3f99c9` — `feat(evolution): add cascade.py — 4-stage cascading evaluator for ~10x throughput`

### Module 4: `src/evolutor/tools/__init__.py`
Already existed as empty file — package was already initialized. No action required.

### Module 5: `src/evolutor/tools/synthesizer.py`
`RuntimeToolSynthesizer` — Live-SWE-agent §3.2 step-reflection + safety kernel.
- **Reflection trigger:** Every 3 steps OR after any "error"/"not found" tool result.
- **Synthesis protocol:** Agent emits `<tool_synthesis>name/description/code</tool_synthesis>` blocks.
- **Safety kernel:** 6 dangerous pattern checks (`rm -rf`, `os.system`, `eval(`, `exec(`, etc.) + `ast.parse()` validation before any tool is registered.
- **Cross-session persistence:** Registered tools forwarded to `PersistentPlaybookStore.add_tool_pattern()`.
- **Execution:** `exec()` in isolated namespace, called with `**inputs` from agent loop.
- **Commit:** `d1cb635` — `feat(tools): add synthesizer.py — RuntimeToolSynthesizer with safety kernel validation`

### Module 6: `src/evolutor/memory/persistent_playbooks.py`
`PersistentPlaybookStore` — ACE-pattern cross-session learning store.
- **ACE pattern:** Accumulate (record outcomes) → Compress (top-50 helpful, recent-30 harmful) → Emit (LLM prompt context).
- **Dual-mode input:** Receives outcomes from both offline evolution (`add_helpful`/`add_harmful`) and runtime tool synthesis (`add_tool_pattern`).
- **Storage:** JSON at `playbooks/persistent_store.json` (path configurable).
- **`get_context_for_mutation(top_n=5)`:** Emits formatted markdown block injected into next-generation mutation prompts — this is how historical knowledge propagates forward.
- **Commit:** `a5753d0` — `feat(memory): add persistent_playbooks.py — ACE-pattern cross-session strategy store`

## Benchmark Results
(to be filled as experiments run)

## Key Insights from Papers Applied
- **mini-SWE-agent:** Radical simplicity beats feature-rich agents on SWE-bench (seed_agent.py)
- **Live-SWE-agent §3.2:** Step-reflection after every tool result improves agent trajectory (seed_agent.py + synthesizer.py)
- **AlphaEvolve/OpenEvolve:** Cascade evaluation ~10x throughput by rejecting bad mutations early (cascade.py)
- **DGM:** Safety kernel prevents reward-hacking during tool synthesis (synthesizer.py validate_tool)
- **ACE pattern:** Persistent cross-session memory enables compounding improvement (persistent_playbooks.py)

## Commits (Session 2)

```
a5753d0 feat(memory): add persistent_playbooks.py — ACE-pattern cross-session strategy store
d1cb635 feat(tools): add synthesizer.py — RuntimeToolSynthesizer with safety kernel validation
c3f99c9 feat(evolution): add cascade.py — 4-stage cascading evaluator for ~10x throughput
8460461 feat(swebench): add seed_agent.py — mini-SWE-agent scaffold + Live-SWE-agent step-reflection
209c217 feat(swebench): add swebench package __init__.py — new evolution target module
```
