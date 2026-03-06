# Evolutor v2 — Autonomous Build Agent

Working directory: `/home/mekashirskiy/evolutor`, branch `dev`.
You are transforming Evolutor from scaffolding into a working self-evolving coding agent.

## CRITICAL: Previous Execution Failed

Previous execution produced 74 "completed" stories — all non-functional stubs. Nothing works.

**YOU MUST:**
- Read `required_reading` files listed in each story BEFORE implementing
- Write real, functional code (no `pass`, `...`, `raise NotImplementedError`)
- Run ALL `verification` commands from the story and see PASS
- Use `os.environ.get()` for LLM config — never hardcode URLs/keys

**YOU MUST NOT:**
- Write stub functions that return hardcoded values
- Skip verification commands
- Mark a story done without ALL verifications passing
- Use mocks in production code
- Copy code without understanding it — read the referenced files first

---

## Available Skills (USE PROACTIVELY)

You have access to specialized skills via `/skill-name`. Use them when implementing stories:

| Skill | When to use | Stories |
|-------|-------------|---------|
| `/claude-api` | Any code using `anthropic.Anthropic()` client | US-201, US-202, US-209 |
| `/systematic-debugging` | Investigating root causes before fixing bugs | US-203 |
| `/investigate` | Understanding code flow and Docker execution | US-203, US-204 |
| `/code-review` | Reviewing code quality after implementation | All stories |
| `/simplify` | Post-implementation cleanup and deduplication | All stories |
| `/vllm` | vLLM serving config, prefix caching, metrics | US-205 |
| `/instructor` | Structured LLM output with Pydantic validation | US-208, US-209 |
| `/outlines` | Constrained generation (valid Python output) | US-209 |
| `/dspy` | Prompt optimization patterns | US-208 |
| `/mlflow` | Experiment tracking, model registry for evolved agents | US-216, US-217 |
| `/tensorboard` | Real-time fitness curves during evolution | US-216 |
| `/faiss` | Vector similarity for MAP-Elites archive | US-212 |
| `/sentence-transformers` | Behavior embeddings for archive dimensions | US-212 |
| `/constitutional-ai` | Self-critique loop for mutation acceptance | US-213 |
| `/ray-train` | Distributed parallel evaluation with Ray | US-216 |
| `/grpo-rl-training` | Composite reward functions, group ranking | US-210 |
| `/model-merging` | Agent crossover via task arithmetic | US-216 |
| `/ml-paper-writing` | Results documentation, paper structure | US-218 |

---

## Anthropic SDK Patterns

When writing code that calls the Anthropic API (seed_agent, mutator):

```python
client = anthropic.Anthropic()  # Reads ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY from env
response = client.messages.create(
    model=os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6"),
    max_tokens=4096,
    system="system prompt here",
    tools=[BASH_TOOL],  # Anthropic tool_use format
    messages=messages,
)
# response.content = list of ContentBlock
# Tool use: block.type == "tool_use", block.name, block.id, block.input (dict)
# Text: block.type == "text", block.text
# Tool result: {"type": "tool_result", "tool_use_id": block.id, "content": "output string"}
```

Environment: `no_proxy` must include `localhost,127.0.0.1` (system proxy intercepts HTTP otherwise).

---

## Anti-Patterns (8 from EXECUTION_PRD section 9 — MUST AVOID)

1. **Don't let evolution modify the eval harness** — DGM's agent disabled hallucination detection. Use SHA verification.
2. **Don't use accept-if-better hill climbing** — converges to local optima. Use HGM tree + archive diversity.
3. **Don't over-engineer the seed agent** — mini-swe-agent: 100 lines = 74%. Complexity DISCOVERED by evolution.
4. **Don't evaluate every mutation fully** — cascade: syntax → smoke → full saves 3-5x compute.
5. **Don't use random mutations** — DGM diagnosis identifies WHAT to fix. Use 5 targeted types.
6. **Don't ignore diversity** — MAP-Elites prevents progressive degradation (Digital Red Queen ablation).
7. **Don't hardcode LLM config** — env vars for API endpoints, keys, model names.
8. **Don't forget test_patch** — FAIL_TO_PASS tests don't exist until test_patch applied. False positives otherwise.

---

## Existing Code That WORKS (PRESERVE — do not rewrite)

- `src/evolutor/evolution/archive.py` lines 116-178: CMP Thompson sampling + clade lineage propagation
- `src/evolutor/evolution/mutator.py` lines 149-210: `===FILE:===...===END===` marker extraction logic
- `src/evolutor/evolution/plateau.py` lines 21-39: ruptures PELT detection with variance fallback
- `scripts/proxy_server.py`: Anthropic↔OpenAI proxy — fully functional, do NOT modify

---

## Execution Loop

Repeat until all stories pass:

### Step 1: Find next story

```bash
STORY_ID=$(jq -r '[.userStories[] | select(.passes == false)] | .[0].id' ralph/prd.json)
echo "Next: $STORY_ID"
```

If `null` → all done → output `<promise>COMPLETE</promise>` and stop.

### Step 2: Read story details from prd.json

```bash
jq '[.userStories[] | select(.passes == false)] | .[0]' ralph/prd.json
```

This gives you: `target_file`, `description`, `required_reading`, `skills`, `verification`.

### Step 3: Use skills + read required files

First, invoke any skills listed in the story's `skills` array — they provide specialized patterns.
Then read EVERY file in `required_reading`. Understand algorithms before writing code.

### Step 4: Implement

```bash
pip install -e /home/mekashirskiy/evolutor -q --no-deps 2>/dev/null
```

Write code according to `description`. Target file is `target_file`.

### Step 5: Verify

Run every command from `verification`. Each must print PASS. Fix and retry if any fails.

### Step 6: Mark done + commit + push

```bash
cd /home/mekashirskiy/evolutor
jq '(.userStories[] | select(.id == "US-XXX")).passes |= true' ralph/prd.json > /tmp/prd.tmp && mv /tmp/prd.tmp ralph/prd.json
echo "DONE: US-XXX: <title> ($(date '+%Y-%m-%d %H:%M'))" >> ralph/progress.txt
git add -A && git commit -m "feat: US-XXX: <title>" && git push -u origin HEAD
```

If push fails:
```bash
git remote set-url origin "https://$(printenv GH_PAT_CLASSIC)@github.com/mariklolik/evolutor.git"
git push -u origin HEAD
```

### Step 7: Go to Step 1

---

## Key References

| File | Contents |
|------|----------|
| `ralph/REVISED_ARCHITECTURE.md` | Seed agent code, HGM algorithm, mutation types |
| `ralph/EXECUTION_PRD.md` | Full spec with formulas, anti-patterns (section 9), success criteria (section 13) |
| `ralph/deep_research_findings.md` | HGM CMP, DGM diagnosis, SICA utility, Live-SWE-agent reflection |
| `ralph/competitor_analysis.md` | DGM/HGM/SICA/OpenEvolve exact code patterns |

Competitor codebases:

| Directory | Use for |
|-----------|---------|
| `/home/mekashirskiy/competitors/mini-swe-agent/` | Seed agent template (1 bash tool) |
| `/home/mekashirskiy/competitors/HGM/hgm.py` + `tree.py` | EXACT HGM: CMP, Thompson, expansion |
| `/home/mekashirskiy/competitors/dgm/DGM_outer.py` | DGM outer loop, diagnosis prompt |
| `/home/mekashirskiy/competitors/openevolve/` | MAP-Elites + cascade eval |

## Code Standards

- Python 3.11+, `src/evolutor/` package layout, hatchling build
- Pydantic v2 for data models, structlog for logging
- Keep seed_agent.py under 200 lines — complexity discovered by evolution
