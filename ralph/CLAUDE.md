# Evolutor v2 — Build a WORKING Self-Evolving Coding Agent

You are transforming the Evolutor project from scaffolding into a working, benchmarked, SOTA self-evolving coding agent system. Working directory: `/home/mekashirskiy/evolutor`, branch `dev`.

## CRITICAL WARNING — Lessons from Previous Execution

The previous PRD execution produced 74 "completed" stories in 3 hours — all stubs and mocks. The code DOES NOT WORK:
- `seed_agent.py` exits at step 0 on most tasks (0% real pass rate)
- `loop.py` uses wrong algorithm (generational, not HGM tree)
- `mutator.py` has 6 generic types instead of 5 targeted
- `cascade.py` checks unit tests instead of SWE-bench stages
- `harness.py` runs 2 separate Docker containers so edits are lost

**YOU MUST NOT:**
- Write stub functions that return hardcoded values
- Skip verification commands
- Mark a story done without running ALL verification commands and seeing them PASS
- Use mocks where real implementations are required
- Write `pass` or `...` or `raise NotImplementedError` in any function body
- Copy code without understanding it — READ the competitor codebases first

**YOU MUST:**
- Read the referenced research files BEFORE implementing
- Run every verification command and confirm PASS before marking done
- Write real, functional code that actually works
- Test with real data structures, not just imports

---

## LLM Access (environment variables — NEVER hardcode)

- `ANTHROPIC_BASE_URL` — proxy endpoint (set in environment or ralph/.env)
- `ANTHROPIC_API_KEY` — API key (set in environment or ralph/.env)
- `EVOLUTOR_MODEL` — model name mapped by proxy (default: `claude-sonnet-4-6`)
- `no_proxy` / `NO_PROXY` — must include `localhost,127.0.0.1,0.0.0.0,::1`

When writing code that calls LLMs, ALWAYS use `os.environ.get(...)`. Never hardcode URLs or keys.

---

## MANDATORY READING — Before Your First Story

Before implementing ANY story, read these files IN ORDER. They contain exact algorithms, formulas, and design decisions:

1. **`ralph/REVISED_ARCHITECTURE.md`** — Hybrid runtime+offline architecture, seed agent code, HGM+MAP-Elites algorithm, mutation types, comparison table
2. **`ralph/RESEARCH_REPORT.md`** — 32-system synthesis, tiered implementation plan
3. **`ralph/deep_research_findings.md`** — Paper-by-paper algorithms: DGM score_child_prop, HGM CMP, SICA utility, ACE deltas, 4/δ bound
4. **`ralph/competitor_analysis.md`** — DGM/HGM/SICA/OpenEvolve/mini-swe-agent exact code patterns
5. **`ralph/implementation_phases.md`** — Ready-to-use data structures and pseudocode
6. **`ralph/EXECUTION_PRD.md`** — Complete specification with all algorithms

Also read these competitor codebases for exact implementation patterns:
- `/home/mekashirskiy/competitors/mini-swe-agent/` — Our seed agent template (1 bash tool, ~100 lines)
- `/home/mekashirskiy/competitors/HGM/hgm.py` + `tree.py` — EXACT HGM algorithm we're implementing
- `/home/mekashirskiy/competitors/dgm/DGM_outer.py` — DGM's outer loop with diagnosis
- `/home/mekashirskiy/competitors/openevolve/` — MAP-Elites + cascade eval patterns

---

## MANDATORY LOOP — follow these steps in order, every single iteration

### STEP 1 — Find your next story

```bash
jq -r '[.userStories[] | select(.passes == false)] | .[0] | "\(.id): \(.title)"' ralph/prd.json
```

If it prints `null` — all stories done. Output `<promise>COMPLETE</promise>` and stop.

### STEP 2 — Read the required files for this story

Each story below lists files you MUST read before implementing. Read them. Understand the patterns. Then implement.

### STEP 3 — Implement the story

Satisfy EVERY acceptance criterion. Run EVERY verification command. Each must PASS.

### STEP 4 — Mark DONE + commit + push

```bash
# Replace US-XXX with actual story ID
jq '(.userStories[] | select(.id == "US-XXX")).passes |= true' ralph/prd.json > ralph/prd.json.tmp && mv ralph/prd.json.tmp ralph/prd.json
echo "DONE: US-XXX: <title> ($(date '+%Y-%m-%d %H:%M'))" >> ralph/progress.txt
cd /home/mekashirskiy/evolutor && git add -A && git commit -m "feat: US-XXX: <title>" && git push -u origin HEAD
```

If push fails:
```bash
git remote set-url origin "https://$(printenv GH_PAT_CLASSIC)@github.com/mariklolik/evolutor.git"
git push -u origin HEAD
```

### STEP 5 — Go to STEP 1

Keep going until all stories are done or you run out of context.

### STEP 6 — When ALL stories are DONE

Output: `<promise>COMPLETE</promise>`

---

## Story Reference — Acceptance Criteria + Verification

---

### Phase 0 — Seed Agent + Infrastructure

---

#### US-101: Rewrite seed_agent.py — mini-swe-agent + Live-SWE-agent pattern

**Required reading before implementing:**
- `/home/mekashirskiy/competitors/mini-swe-agent/src/minisweagent/agents/default.py` — the exact pattern to follow
- `ralph/REVISED_ARCHITECTURE.md` section "Revised Seed Agent" — evolvable sections design
- `ralph/deep_research_findings.md` section "Live-SWE-agent" — reflection pattern + ablation results
- `ralph/EXECUTION_PRD.md` section 4 — "What Gets Evolved"

**What to build:**

COMPLETE REWRITE of `src/evolutor/swebench/seed_agent.py`. The new agent must:

1. Have exactly ONE tool: `bash` (via standard Anthropic `tool_use` format)
   - Tool name: `"bash"`, parameter name: `"command"` (NOT `"cmd"`)
   - `input_schema` with `{"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}`

2. Have 6 clearly marked EVOLVABLE SECTIONS with `# ===== EVOLVABLE SECTION: <name> =====` markers:
   - `SYSTEM_PROMPT` — guidance for the agent (include tool creation guidance from REVISED_ARCHITECTURE)
   - `REFLECTION_PROMPT` — injected every 5 steps (Live-SWE-agent pattern: "Are you making progress? Would creating a custom tool help?")
   - `TOOL_TEMPLATES` — starts as empty string, grows through evolution
   - `WORKFLOW_HINTS` — starts as empty string, grows through evolution
   - `MAX_STEPS = 50` — step limit
   - `STEP_TIMEOUT = 30` — per-command timeout

3. Have an `INSTANCE_TEMPLATE` with `{repo_dir}`, `{problem_statement}`, `{workflow_hints}` placeholders

4. Have `BASH_TOOL` dict (Anthropic format, NOT OpenAI function format)

5. Have `execute_bash(command, cwd, timeout)` function:
   - Uses `subprocess.run(["bash", "-lc", command], ...)`
   - Captures stdout+stderr, truncates to 10000 chars
   - Returns exit code + output

6. Have `solve_task(problem_statement, repo_dir, model)` function:
   - Creates `anthropic.Anthropic()` client (reads from env vars)
   - Builds messages with INSTANCE_TEMPLATE
   - Loops up to MAX_STEPS, calling tool_use API
   - Injects REFLECTION_PROMPT every 5 steps (step > 0 and step % 5 == 0)
   - Appends TOOL_TEMPLATES to system prompt if non-empty
   - On `end_turn` or no tool_uses → break
   - Extracts and returns `git diff` patch
   - NO THOUGHT/ACTION text parsing
   - NO step-reflect suffix appended to tool results
   - Linear message history (assistant content → tool results)

7. Have `solve(issue, repo_root, model, max_steps)` backward-compatible wrapper:
   - Calls `solve_task()` internally
   - Returns `{"success": bool, "summary": str, "steps": int, "files_changed": list, "patch": str}`

8. Be under 200 lines total (mini-swe-agent proves simplicity wins)

**Verification (run ALL, each must PASS):**

```bash
# V1: Syntax check
python3 -c "import ast; ast.parse(open('src/evolutor/swebench/seed_agent.py').read()); print('V1 PASS: syntax OK')"

# V2: All required exports exist
python3 -c "
from evolutor.swebench.seed_agent import (
    solve_task, solve, execute_bash,
    SYSTEM_PROMPT, REFLECTION_PROMPT, TOOL_TEMPLATES, WORKFLOW_HINTS,
    MAX_STEPS, STEP_TIMEOUT, BASH_TOOL, INSTANCE_TEMPLATE
)
print('V2 PASS: all exports exist')
"

# V3: BASH_TOOL schema correct
python3 -c "
from evolutor.swebench.seed_agent import BASH_TOOL
assert BASH_TOOL['name'] == 'bash', f'Expected bash, got {BASH_TOOL[\"name\"]}'
assert 'command' in BASH_TOOL['input_schema']['properties'], 'Missing command property'
assert BASH_TOOL['input_schema']['properties']['command']['type'] == 'string'
assert 'required' in BASH_TOOL['input_schema']
assert 'command' in BASH_TOOL['input_schema']['required']
print('V3 PASS: BASH_TOOL schema correct')
"

# V4: Evolvable section markers (need ≥ 5)
python3 -c "
code = open('src/evolutor/swebench/seed_agent.py').read()
count = code.count('EVOLVABLE SECTION')
assert count >= 5, f'Need ≥5 EVOLVABLE SECTION markers, found {count}'
print(f'V4 PASS: {count} EVOLVABLE SECTION markers found')
"

# V5: No legacy patterns
python3 -c "
code = open('src/evolutor/swebench/seed_agent.py').read()
assert 'THOUGHT' not in code and 'ACTION' not in code, 'Remove THOUGHT/ACTION format'
assert 'STEP_REFLECT_SUFFIX' not in code, 'Remove step-reflect suffix'
assert 'view_file' not in code, 'Remove view_file tool — use bash only'
assert 'edit_file' not in code, 'Remove edit_file tool — use bash only'
assert 'search_code' not in code, 'Remove search_code tool — use bash only'
assert '\"cmd\"' not in code, 'Use command not cmd as parameter name'
print('V5 PASS: no legacy patterns')
"

# V6: Line count reasonable
python3 -c "
lines = len(open('src/evolutor/swebench/seed_agent.py').readlines())
assert lines < 200, f'Too many lines: {lines}. Keep it simple (mini-swe-agent is ~100 lines)'
print(f'V6 PASS: {lines} lines (< 200)')
"

# V7: Parameters correct
python3 -c "
from evolutor.swebench.seed_agent import MAX_STEPS, STEP_TIMEOUT
assert MAX_STEPS == 50, f'MAX_STEPS should be 50, got {MAX_STEPS}'
assert STEP_TIMEOUT == 30, f'STEP_TIMEOUT should be 30, got {STEP_TIMEOUT}'
print('V7 PASS: parameters correct')
"

# V8: execute_bash works locally
python3 -c "
from evolutor.swebench.seed_agent import execute_bash
result = execute_bash('echo hello world', cwd='/tmp')
assert 'hello world' in result, f'execute_bash failed: {result}'
assert 'Exit code: 0' in result, f'Expected exit code 0: {result}'
print('V8 PASS: execute_bash works')
"

# V9: Reflection prompt exists and is non-empty
python3 -c "
from evolutor.swebench.seed_agent import REFLECTION_PROMPT
assert len(REFLECTION_PROMPT) > 50, 'REFLECTION_PROMPT too short'
assert 'progress' in REFLECTION_PROMPT.lower() or 'reflect' in REFLECTION_PROMPT.lower(), 'REFLECTION_PROMPT should mention progress/reflection'
print('V9 PASS: REFLECTION_PROMPT OK')
"
```

---

#### US-102: Fix harness.py — single-container Docker eval with test_patch

**Required reading:**
- `ralph/EXECUTION_PRD.md` section 9 anti-pattern #8 — test_patch is essential
- Current `src/evolutor/swebench/harness.py` — understand the double-container bug
- `ralph/EXECUTION_PRD.md` section "Eval Harness" — immutable kernel design

**What to fix:**

The current `harness.py` has a critical bug at lines 211-238: it runs the agent in one Docker container, then runs tests in a SEPARATE `docker run` call. Since Docker containers are ephemeral, the agent's file edits are LOST between the two runs. Tests always see the original code.

Fix `_eval_task_docker()` to use a SINGLE `docker run` that:
1. Activates the testbed conda environment
2. Applies `test_patch` via `git apply` (so FAIL_TO_PASS tests exist)
3. Installs anthropic, structlog, pydantic, and evolutor
4. Runs the seed agent (which edits files in /testbed)
5. Runs FAIL_TO_PASS tests in the SAME container (sees agent's edits)
6. Outputs structured result: `AGENT_STEPS:N`, `AGENT_PATCH:...`, `TESTS_PASSED:True/False`

Also fix:
- `FAIL_TO_PASS` field handling: it's a JSON string in HuggingFace → must `json.loads()` it
- Agent function: use `solve_task(problem_statement, repo_dir, model)` not `solve()` — since US-101 creates `solve_task` that returns a patch string
- The runner script must handle the new `solve_task` API (returns git diff string, not dict)

**Also add:**
- `eval_agent_code_docker(agent_code, task, project_root, model, timeout)` function that:
  - Writes agent_code to a temp file
  - Mounts it into Docker container
  - Runs evaluation using that code (not the installed seed_agent)
  - This is what the evolution loop uses to test mutated agents

**Verification:**

```bash
# V1: Syntax check
python3 -c "import ast; ast.parse(open('src/evolutor/swebench/harness.py').read()); print('V1 PASS')"

# V2: Required functions exist
python3 -c "
from evolutor.swebench.harness import (
    evaluate, load_tasks, eval_agent_code_docker,
    TaskResult, EvalResult, _eval_task_docker
)
print('V2 PASS: all functions exist')
"

# V3: No double-container bug (single docker run for agent+tests)
python3 -c "
import inspect
from evolutor.swebench.harness import _eval_task_docker
source = inspect.getsource(_eval_task_docker)
# Count 'docker.*run' calls — should be exactly 1
import re
docker_runs = re.findall(r'docker.*run', source)
assert len(docker_runs) <= 2, f'Expected 1-2 docker run references, found {len(docker_runs)} — fix double-container bug'
# Must apply test_patch
assert 'test_patch' in source, 'Must apply test_patch in Docker'
assert 'git apply' in source or 'git.*apply' in source, 'Must use git apply for test_patch'
print('V3 PASS: single-container pattern')
"

# V4: eval_agent_code_docker accepts agent_code parameter
python3 -c "
import inspect
from evolutor.swebench.harness import eval_agent_code_docker
sig = inspect.signature(eval_agent_code_docker)
params = list(sig.parameters.keys())
assert 'agent_code' in params, f'Missing agent_code param. Has: {params}'
assert 'task' in params, f'Missing task param. Has: {params}'
print('V4 PASS: eval_agent_code_docker signature correct')
"

# V5: FAIL_TO_PASS handled as JSON string
python3 -c "
source = open('src/evolutor/swebench/harness.py').read()
assert 'json.loads' in source, 'Must json.loads FAIL_TO_PASS (it is a JSON string in HuggingFace)'
print('V5 PASS: json.loads for FAIL_TO_PASS')
"
```

---

#### US-103: Build SWE-bench Docker images and create run_baseline.py

**Required reading:**
- `ralph/EXECUTION_PRD.md` section 12 — Runtime Checklist
- `/home/mekashirskiy/competitors/SWE-bench/swebench/harness/` — how to build images
- `ralph/EXECUTION_PRD.md` section "Phase 2: Baseline Benchmark"

**What to build:**

1. **Build SWE-bench Docker images** (if not already available):
   - Check which `sweb.eval.x86_64.*` images already exist
   - If none exist, build them using the SWE-bench harness from `/home/mekashirskiy/competitors/SWE-bench/`
   - Target: flask and requests repos (easiest to build, pure Python)
   - Save list of available instance_ids to `results/available_tasks.json`

2. **Create `scripts/run_baseline.py`**:
   - Enumerate available Docker images (not hardcoded — discover at runtime)
   - Load corresponding SWE-bench tasks from HuggingFace dataset
   - Run seed_agent on each task via `eval_agent_code_docker()` from harness.py
   - Record per-task results: instance_id, passed, time_seconds, steps, error
   - Save to `results/baseline.json`
   - Print summary table with pass rate

3. **Create `results/` directory** if it doesn't exist

**Verification:**

```bash
# V1: run_baseline.py exists and is valid Python
python3 -c "import ast; ast.parse(open('scripts/run_baseline.py').read()); print('V1 PASS')"

# V2: results directory exists
test -d results && echo "V2 PASS: results/ exists" || echo "V2 FAIL"

# V3: available_tasks.json exists (may be empty if no images built yet)
test -f results/available_tasks.json && echo "V3 PASS" || echo "V3 FAIL: create results/available_tasks.json"

# V4: run_baseline.py discovers Docker images dynamically
python3 -c "
source = open('scripts/run_baseline.py').read()
assert 'docker' in source.lower(), 'Must discover Docker images'
assert 'hardcoded' not in source.lower(), 'Must not hardcode task list'
print('V4 PASS: dynamic Docker discovery')
"

# V5: Check what Docker images are available
python3 -c "
import subprocess, json
result = subprocess.run(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
                       capture_output=True, text=True, timeout=10)
sweb_images = [img for img in result.stdout.strip().split('\n') if 'sweb.eval' in img]
print(f'Available SWE-bench images: {len(sweb_images)}')
for img in sweb_images[:10]:
    print(f'  {img}')
with open('results/available_tasks.json', 'w') as f:
    json.dump(sweb_images, f, indent=2)
print('V5 PASS: task discovery complete')
"
```

---

### Phase 1 — Evolution Engine Core

---

#### US-104: EvolutionNode + EvolutionTree + CMP Thompson sampling + expansion rule

**Required reading (MANDATORY — these contain the EXACT algorithms):**
- `/home/mekashirskiy/competitors/HGM/hgm.py` — the actual HGM implementation
- `/home/mekashirskiy/competitors/HGM/tree.py` — tree data structure
- `ralph/EXECUTION_PRD.md` section 3.1 — HGM Tree with CMP Thompson Sampling (exact formulas)
- `ralph/REVISED_ARCHITECTURE.md` section "Key Formulas Reference" — CMP, Thompson, expansion
- `ralph/deep_research_findings.md` section "HGM" — num_pseudo, tau=B/b, expansion rule N^0.6

**What to build:**

Create a NEW file `src/evolutor/evolution/tree.py` with:

1. **`EvolutionNode` dataclass:**
   ```python
   @dataclass
   class EvolutionNode:
       id: str
       code: str                    # Full seed_agent.py content
       parent_id: str | None
       children: list[str]          # Child node IDs
       utility_measures: list[int]  # Binary 0/1 per task evaluation
       evaluated_tasks: list[str]   # Instance IDs already evaluated
       mutation_type: str           # Which of 5 types was used
       mutation_description: str    # What was changed
       created_at: float
   ```
   - Properties: `num_evals`, `mean_utility` (returns 0.5 if no evals, not inf)
   - Method: `to_dict()` and `from_dict()` for JSON serialization

2. **`EvolutionTree` class:**
   - `__init__(seed_code, tasks, eval_budget)` — creates root node
   - `get_descendant_evals(node_id, num_pseudo=100)` — HGM CMP: recursively collect all descendant utility measures. If node has fewer evals than num_pseudo, pad with mean_utility replicated num_pseudo times (see HGM paper and `/competitors/HGM/hgm.py`)
   - `thompson_sample(for_expansion=True)` — Thompson sampling with `tau = eval_budget / max(1, eval_budget - n_evals)`:
     - For each node: `alpha = tau * (1 + sum(evals))`, `beta = tau * (1 + len(evals) - sum(evals))`
     - Sample `theta ~ Beta(max(alpha, 0.01), max(beta, 0.01))`
     - Return argmax(theta)
     - When `for_expansion=False` (measurement), use node's OWN evals, not descendant evals
   - `should_expand(alpha=0.6)` — HGM: `n_evals ** alpha >= len(nodes) - 1 + pending_expansions`
   - `add_child(parent_id, child_code, mutation_type, mutation_description)` — returns new node ID
   - `select_unevaluated_task(node_id)` — pick task this node hasn't been evaluated on
   - `record_eval(node_id, task_id, passed)` — append to utility_measures
   - `get_best_agent()` — return node with highest mean_utility (≥3 evals minimum)
   - `save_state(path)` / `load_state(path)` — JSON persistence for crash recovery
   - Properties: `n_evals`, `n_nodes`, `nodes`

**Implementation constraints:**
- Use `numpy.random.beta` for Thompson sampling (import numpy)
- Use `time.time()` for created_at
- Use `uuid.uuid4().hex[:8]` for node IDs
- Tasks list stored in tree, not passed to every method

**Verification:**

```bash
# V1: File exists and is valid
python3 -c "import ast; ast.parse(open('src/evolutor/evolution/tree.py').read()); print('V1 PASS')"

# V2: All classes and methods exist
python3 -c "
from evolutor.evolution.tree import EvolutionNode, EvolutionTree
import inspect
# Check EvolutionNode fields
node = EvolutionNode(id='test', code='x=1', parent_id=None, children=[],
                     utility_measures=[], evaluated_tasks=[],
                     mutation_type='seed', mutation_description='initial',
                     created_at=0.0)
assert hasattr(node, 'num_evals')
assert hasattr(node, 'mean_utility')
assert node.num_evals == 0
assert node.mean_utility == 0.5, f'Empty node mean_utility should be 0.5, got {node.mean_utility}'

# Check EvolutionTree methods
tree_methods = ['get_descendant_evals', 'thompson_sample', 'should_expand',
                'add_child', 'select_unevaluated_task', 'record_eval',
                'get_best_agent', 'save_state', 'load_state']
for method in tree_methods:
    assert hasattr(EvolutionTree, method), f'Missing method: {method}'
print('V2 PASS: all classes and methods exist')
"

# V3: CMP Thompson sampling works correctly
python3 -c "
from evolutor.evolution.tree import EvolutionTree
import numpy as np

# Create tree with known tasks
tasks = [{'instance_id': f'task-{i}'} for i in range(5)]
tree = EvolutionTree(seed_code='# seed', tasks=tasks, eval_budget=100)

# Record some evals for root
tree.record_eval('root', 'task-0', True)
tree.record_eval('root', 'task-1', False)
tree.record_eval('root', 'task-2', True)

# Thompson sample should return a valid node ID
np.random.seed(42)
selected = tree.thompson_sample()
assert selected in tree.nodes, f'thompson_sample returned invalid node: {selected}'

# Descendant evals should include root's evals
evals = tree.get_descendant_evals('root')
assert len(evals) > 0, 'get_descendant_evals returned empty'
print(f'V3 PASS: Thompson sampling works (selected: {selected}, evals: {len(evals)})')
"

# V4: Expansion rule works
python3 -c "
from evolutor.evolution.tree import EvolutionTree
tasks = [{'instance_id': f'task-{i}'} for i in range(5)]
tree = EvolutionTree(seed_code='# seed', tasks=tasks, eval_budget=100)

# With 0 evals, should not expand (0^0.6 = 0 < 0 nodes = false... actually 0 nodes excluded)
# With few evals, should expand
for i in range(5):
    tree.record_eval('root', f'task-{i}', True)
# 5 evals, 0 non-root nodes: 5^0.6 ≈ 2.63 >= 0 → should expand
assert tree.should_expand(), 'Should expand with 5 evals and 0 children'

# Add a child
tree.add_child('root', '# child code', 'improve_system_prompt', 'test mutation')
# Now 1 non-root node: 5^0.6 ≈ 2.63 >= 1 → should still expand
assert tree.should_expand(), 'Should still expand with 5 evals and 1 child'

print('V4 PASS: expansion rule correct')
"

# V5: JSON persistence works
python3 -c "
import tempfile, os
from evolutor.evolution.tree import EvolutionTree
tasks = [{'instance_id': 'task-0'}]
tree = EvolutionTree(seed_code='# seed code', tasks=tasks, eval_budget=50)
tree.record_eval('root', 'task-0', True)
tree.add_child('root', '# child', 'improve_system_prompt', 'test')

# Save
path = tempfile.mktemp(suffix='.json')
tree.save_state(path)
assert os.path.exists(path), 'save_state did not create file'

# Load
tree2 = EvolutionTree.load_state(path)
assert len(tree2.nodes) == len(tree.nodes), 'Loaded tree has wrong number of nodes'
assert tree2.n_evals == tree.n_evals, 'Loaded tree has wrong n_evals'
os.unlink(path)
print('V5 PASS: JSON persistence works')
"

# V6: tau increases over time (exploitation)
python3 -c "
from evolutor.evolution.tree import EvolutionTree
tasks = [{'instance_id': f't-{i}'} for i in range(10)]
tree = EvolutionTree(seed_code='x', tasks=tasks, eval_budget=100)
# tau = B / max(1, B - n_evals)
# At 0 evals: tau = 100/100 = 1
# At 50 evals: tau = 100/50 = 2
# At 90 evals: tau = 100/10 = 10
# Verify tau logic is in the code
source = open('src/evolutor/evolution/tree.py').read()
assert 'eval_budget' in source, 'Must use eval_budget for tau'
assert 'tau' in source, 'Must compute tau for Thompson sampling'
print('V6 PASS: tau logic present')
"
```

---

#### US-105: DGM diagnosis mutator with 5 targeted mutation types

**Required reading (MANDATORY):**
- `/home/mekashirskiy/competitors/dgm/DGM_outer.py` — DGM's diagnosis + mutation pattern
- `ralph/EXECUTION_PRD.md` section 3.2 — DGM-Style Diagnosis prompt
- `ralph/EXECUTION_PRD.md` section 4.3 — 5 Targeted Mutation Types with triggers
- `ralph/REVISED_ARCHITECTURE.md` section "Mutation Types" — triggers and prompts
- `ralph/competitor_analysis.md` section "DGM" — score_child_prop, entry categorization

**What to build:**

REWRITE `src/evolutor/evolution/mutator.py` with:

1. **`MutationType` enum** with exactly 5 types:
   - `improve_system_prompt` — agent doesn't attempt / exits early
   - `add_tool_template` — agent struggles with repetitive operations
   - `improve_reflection` — agent loops without progress
   - `add_workflow_hint` — agent uses wrong approach for task type
   - `optimize_parameters` — agent times out or wastes steps

2. **`DIAGNOSIS_PROMPT`** template that includes:
   - Full agent code (the parent's seed_agent.py content)
   - Failed task logs (truncated to 50K chars)
   - Instructions to analyze failures and choose ONE mutation type
   - Output format: `MUTATION_TYPE:`, `ANALYSIS:`, `PLAN:`, `CODE:` sections
   - The CODE section must contain the COMPLETE modified seed_agent.py

3. **`Mutator` class** with:
   - `diagnose_and_mutate(parent_code, failed_task_logs)` → returns `(child_code, mutation_type, description)`
     - Calls LLM with DIAGNOSIS_PROMPT
     - Parses response to extract mutation_type and code
     - Validates extracted code with `ast.parse()`
     - Returns complete modified agent code (NOT a diff)
   - `select_mutation_type(failure_analysis)` → heuristic type selection as fallback
   - `extract_code_from_response(text)` → robust code extraction:
     - Try `===FILE:...===...===END===` marker format first
     - Then try markdown code blocks (```python...```)
     - Then try raw Python detection (starts with import/def/class)
     - NEVER return empty string — return parent_code unchanged as last resort

4. **Do NOT keep** the old 6 generic types (refactor, optimize, harden, simplify, extend, test_improve)
5. **Do NOT keep** the old `generate_mutation()`, `crossover()` methods
6. **Keep** the `===FILE:===...===END===` extraction logic (it works)

**Verification:**

```bash
# V1: Syntax
python3 -c "import ast; ast.parse(open('src/evolutor/evolution/mutator.py').read()); print('V1 PASS')"

# V2: Exactly 5 mutation types
python3 -c "
from evolutor.evolution.mutator import MutationType
types = list(MutationType)
expected = {'improve_system_prompt', 'add_tool_template', 'improve_reflection', 'add_workflow_hint', 'optimize_parameters'}
actual = {t.value for t in types}
assert actual == expected, f'Wrong types. Expected {expected}, got {actual}'
print(f'V2 PASS: {len(types)} mutation types: {actual}')
"

# V3: Mutator has required methods
python3 -c "
from evolutor.evolution.mutator import Mutator
m = Mutator()
assert hasattr(m, 'diagnose_and_mutate'), 'Missing diagnose_and_mutate'
assert hasattr(m, 'extract_code_from_response'), 'Missing extract_code_from_response'
print('V3 PASS: required methods exist')
"

# V4: Code extraction works with marker format
python3 -c "
from evolutor.evolution.mutator import Mutator
m = Mutator()
test_response = '''ANALYSIS: The agent exits early.
MUTATION_TYPE: improve_system_prompt
PLAN: Improve the system prompt.
CODE:
===FILE: src/evolutor/swebench/seed_agent.py===
import os
SYSTEM_PROMPT = \"\"\"Better prompt\"\"\"
def solve_task(problem, repo, model='x'):
    return 'diff'
===END===
'''
result = m.extract_code_from_response(test_response)
assert result is not None and len(result) > 10, f'extract_code_from_response failed: {result!r}'
assert 'Better prompt' in result, f'Did not extract correct code: {result[:100]}'
print('V4 PASS: marker extraction works')
"

# V5: Code extraction works with markdown code blocks
python3 -c "
from evolutor.evolution.mutator import Mutator
m = Mutator()
test_response = '''Here is the improved code:

\`\`\`python
import os
SYSTEM_PROMPT = \"\"\"Improved\"\"\"
def solve_task(p, r, m='x'):
    return 'diff'
\`\`\`
'''
result = m.extract_code_from_response(test_response)
assert result is not None and 'Improved' in result, f'Markdown extraction failed: {result!r}'
print('V5 PASS: markdown extraction works')
"

# V6: No legacy mutation types
python3 -c "
code = open('src/evolutor/evolution/mutator.py').read()
legacy = ['refactor', 'optimize', 'harden', 'simplify', 'extend', 'test_improve']
for lt in legacy:
    # Allow the word in comments/strings but not as enum values
    assert f'= \"{lt}\"' not in code, f'Remove legacy mutation type: {lt}'
print('V6 PASS: no legacy mutation types')
"

# V7: DIAGNOSIS_PROMPT exists and has required sections
python3 -c "
from evolutor.evolution.mutator import DIAGNOSIS_PROMPT
assert '{agent_code}' in DIAGNOSIS_PROMPT or '{parent_code}' in DIAGNOSIS_PROMPT, 'DIAGNOSIS_PROMPT must include agent code placeholder'
assert 'MUTATION_TYPE' in DIAGNOSIS_PROMPT, 'Must ask for MUTATION_TYPE in output'
assert 'ANALYSIS' in DIAGNOSIS_PROMPT, 'Must ask for ANALYSIS'
assert 'CODE' in DIAGNOSIS_PROMPT, 'Must ask for CODE output'
print('V7 PASS: DIAGNOSIS_PROMPT structure correct')
"
```

---

#### US-106: SWE-bench cascade evaluator — syntax → smoke → medium → full

**Required reading:**
- `ralph/EXECUTION_PRD.md` section 3.3 — Cascading Evaluation (4 stages)
- `/home/mekashirskiy/competitors/openevolve/openevolve/evaluator.py` — cascade pattern
- `ralph/competitor_analysis.md` section "OpenEvolve" — stage thresholds

**What to build:**

REWRITE `src/evolutor/evolution/cascade.py` to implement SWE-bench-specific cascading:

1. **Stage 0: Syntax check** (~1 second)
   - `python3 -c "import ast; ast.parse(code)"`
   - Reject ~30% of mutations (syntax errors, incomplete code)

2. **Stage 1: Smoke test** (~60-120 seconds)
   - Run agent on 1 easy task in Docker
   - Check: agent makes ≥1 bash call AND produces non-empty output
   - Reject: agent crashes, exits immediately, or produces no patch

3. **Stage 2: Medium eval** (~5-10 minutes)
   - Run agent on 3 tasks in Docker
   - Accept if passes ≥1/3 tasks
   - Only for candidates that passed smoke test

4. **Stage 3: Full eval** (~15-30 minutes)
   - Run agent on all available tasks
   - Only for the best candidate or final evaluation

**`CascadeResult` dataclass:**
- `passed: bool`
- `stage_reached: str` (stage0_syntax, stage1_smoke, stage2_medium, stage3_full)
- `pass_rate: float`
- `tasks_passed: int`
- `tasks_total: int`
- `rejection_reason: str`
- `agent_logs: str` (truncated to 2000 chars for mutation feedback)

**`CascadingEvaluator` class:**
- `__init__(tasks, project_root, model)` — tasks = all available SWE-bench tasks
- `evaluate(agent_code, max_stage=3)` → `CascadeResult`
  - Runs stages 0 through max_stage, stopping on first failure
  - Uses `eval_agent_code_docker()` from harness.py for stages 1-3
- `_stage0_syntax(agent_code)` → bool
- `_stage1_smoke(agent_code)` → `CascadeResult`
- `_stage2_medium(agent_code)` → `CascadeResult`
- `_stage3_full(agent_code)` → `CascadeResult`

**Remove** the old pytest-based stages (unit tests, integration tests — those are NOT what we're evaluating).

**Verification:**

```bash
# V1: Syntax
python3 -c "import ast; ast.parse(open('src/evolutor/evolution/cascade.py').read()); print('V1 PASS')"

# V2: Required classes and methods
python3 -c "
from evolutor.evolution.cascade import CascadingEvaluator, CascadeResult
import inspect
sig = inspect.signature(CascadingEvaluator.evaluate)
params = list(sig.parameters.keys())
assert 'agent_code' in params, f'evaluate must take agent_code. Has: {params}'
assert hasattr(CascadingEvaluator, '_stage0_syntax'), 'Missing _stage0_syntax'
assert hasattr(CascadingEvaluator, '_stage1_smoke'), 'Missing _stage1_smoke'
print('V2 PASS: required classes and methods exist')
"

# V3: Stage 0 catches syntax errors
python3 -c "
from evolutor.evolution.cascade import CascadingEvaluator
evaluator = CascadingEvaluator.__new__(CascadingEvaluator)
# Test with invalid Python
assert not evaluator._stage0_syntax('def foo( invalid syntax'), 'Should reject invalid syntax'
# Test with valid Python
assert evaluator._stage0_syntax('def foo(): return 42'), 'Should accept valid syntax'
print('V3 PASS: syntax check works')
"

# V4: CascadeResult has required fields
python3 -c "
from evolutor.evolution.cascade import CascadeResult
r = CascadeResult(passed=False, stage_reached='stage0_syntax', pass_rate=0.0,
                  tasks_passed=0, tasks_total=0, rejection_reason='syntax error',
                  agent_logs='')
assert hasattr(r, 'passed')
assert hasattr(r, 'stage_reached')
assert hasattr(r, 'rejection_reason')
assert hasattr(r, 'agent_logs')
print('V4 PASS: CascadeResult fields correct')
"

# V5: No legacy pytest-based stages
python3 -c "
code = open('src/evolutor/evolution/cascade.py').read()
assert 'tests/unit' not in code, 'Remove legacy unit test stage'
assert 'tests/integration' not in code, 'Remove legacy integration test stage'
assert 'tests/scenario' not in code, 'Remove legacy scenario test stage'
print('V5 PASS: no legacy pytest stages')
"
```

---

#### US-107: Unit tests for EvolutionTree, Thompson sampling, mutator, cascade

**What to build:**

Create/update `tests/unit/test_evolution.py` with comprehensive tests:

1. **Tree tests:**
   - `test_tree_creation` — root node exists, n_nodes=1
   - `test_add_child` — child added, parent.children updated
   - `test_record_eval` — utility_measures updated, n_evals incremented
   - `test_descendant_evals_recursive` — with 3-level tree, verify CMP collects from all descendants
   - `test_thompson_sample_explores_uncertain` — node with no evals should sometimes be selected
   - `test_expansion_rule_sublinear` — verify N^0.6 formula at key points (5 evals → 2.63, 100 → 15.85)
   - `test_json_persistence_roundtrip` — save + load preserves all data
   - `test_get_best_agent_requires_min_evals` — node with <3 evals not selected as best

2. **Mutator tests:**
   - `test_mutation_types_exactly_five`
   - `test_extract_code_marker_format`
   - `test_extract_code_markdown_format`
   - `test_extract_code_raw_python_fallback`
   - `test_diagnosis_prompt_has_placeholders`

3. **Cascade tests:**
   - `test_stage0_rejects_syntax_errors`
   - `test_stage0_accepts_valid_python`
   - `test_cascade_result_fields`

**Verification:**

```bash
# V1: Tests exist
python3 -c "import ast; ast.parse(open('tests/unit/test_evolution.py').read()); print('V1 PASS')"

# V2: Tests actually pass
cd /home/mekashirskiy/evolutor && python3 -m pytest tests/unit/test_evolution.py -v --tb=short 2>&1 | tail -30

# V3: At least 10 test functions
python3 -c "
code = open('tests/unit/test_evolution.py').read()
import re
test_fns = re.findall(r'def (test_\w+)', code)
assert len(test_fns) >= 10, f'Need ≥10 test functions, found {len(test_fns)}: {test_fns}'
print(f'V3 PASS: {len(test_fns)} test functions')
"
```

---

### Phase 2 — Evolution Integration

---

#### US-108: MAP-Elites archive with complexity × tool_diversity dimensions

**Required reading:**
- `ralph/EXECUTION_PRD.md` section 3.4 — MAP-Elites Archive
- `ralph/deep_research_findings.md` section "Digital Red Queen" — MAP-Elites is essential
- `/home/mekashirskiy/competitors/openevolve/openevolve/database.py` — MAP-Elites implementation

**What to build:**

UPDATE `src/evolutor/evolution/archive.py`:

1. **Behavioral dimensions for SWE-bench agents:**
   - Dimension 1: `complexity` — lines of code in seed_agent.py, normalized 0-1 (min=50, max=500)
   - Dimension 2: `tool_diversity` — number of unique tool templates in TOOL_TEMPLATES section, normalized 0-1 (min=0, max=10)

2. **`compute_behavior(agent_code)` function:**
   - Count lines of code → normalize to [0, 1]
   - Count tool templates (search for `def ` in TOOL_TEMPLATES section) → normalize to [0, 1]
   - Returns `[complexity, tool_diversity]`

3. **Update `EvolutionArchive`:**
   - Grid: 10×10 = 100 cells
   - `add_with_behavior(node_id, fitness, agent_code)` — computes behavior, adds to grid
   - `get_underexplored_cells()` — returns cells with 0 entries (for diversification)
   - `sample_from_cell(cell_index)` — returns best agent from specific cell
   - Keep existing CMP methods but connect them to the tree

**Verification:**

```bash
# V1: Syntax
python3 -c "import ast; ast.parse(open('src/evolutor/evolution/archive.py').read()); print('V1 PASS')"

# V2: compute_behavior works
python3 -c "
from evolutor.evolution.archive import compute_behavior
# Simple agent — low complexity, no tools
simple = 'import os\ndef solve_task(p, r, m): return \"\"'
b = compute_behavior(simple)
assert len(b) == 2, f'behavior must have 2 dims, got {len(b)}'
assert 0 <= b[0] <= 1 and 0 <= b[1] <= 1, f'behavior out of range: {b}'
print(f'V2 PASS: compute_behavior works: {b}')
"

# V3: Archive has new methods
python3 -c "
from evolutor.evolution.archive import EvolutionArchive
a = EvolutionArchive()
assert hasattr(a, 'add_with_behavior'), 'Missing add_with_behavior'
assert hasattr(a, 'get_underexplored_cells'), 'Missing get_underexplored_cells'
print('V3 PASS: new archive methods exist')
"
```

---

#### US-109: Immutable kernel SHA verification for eval harness files

**Required reading:**
- `ralph/EXECUTION_PRD.md` section 3.7 — Immutable Kernel (SHA Verification)
- `ralph/deep_research_findings.md` section "DGM Reward Hacking" — why this is essential

**What to build:**

Add to `src/evolutor/kernel/invariants.py`:

1. **`IMMUTABLE_FILES`** list:
   ```python
   IMMUTABLE_FILES = [
       "src/evolutor/swebench/harness.py",
       "src/evolutor/kernel/evaluator.py",
       "src/evolutor/kernel/invariants.py",
       "scripts/proxy_server.py",
   ]
   ```

2. **`compute_file_hashes(project_root)` → `dict[str, str]`** — SHA256 of each immutable file

3. **`verify_kernel_integrity(project_root, expected_hashes)` → `(bool, list[str])`** — returns (ok, list_of_violations)

4. **`KernelIntegrityChecker` class:**
   - `__init__(project_root)` — compute and store baseline hashes
   - `check()` → raises `KernelTamperError` if any file modified
   - `get_baseline_hashes()` → dict for persistence

**Verification:**

```bash
# V1: Syntax
python3 -c "import ast; ast.parse(open('src/evolutor/kernel/invariants.py').read()); print('V1 PASS')"

# V2: SHA verification works
python3 -c "
from evolutor.kernel.invariants import compute_file_hashes, verify_kernel_integrity, IMMUTABLE_FILES
from pathlib import Path
root = Path('/home/mekashirskiy/evolutor')
hashes = compute_file_hashes(root)
assert len(hashes) > 0, 'No hashes computed'
ok, violations = verify_kernel_integrity(root, hashes)
assert ok, f'Integrity check failed on unchanged files: {violations}'
print(f'V2 PASS: SHA verification works ({len(hashes)} files)')
"

# V3: Tampering detection works
python3 -c "
from evolutor.kernel.invariants import verify_kernel_integrity
from pathlib import Path
root = Path('/home/mekashirskiy/evolutor')
# Use wrong hash
fake_hashes = {'src/evolutor/swebench/harness.py': 'deadbeef'}
ok, violations = verify_kernel_integrity(root, fake_hashes)
assert not ok, 'Should detect tampering'
assert len(violations) > 0, 'Should report violations'
print(f'V3 PASS: tampering detected: {violations}')
"
```

---

#### US-110: Plateau detection wiring + diversification strategy

**Required reading:**
- `ralph/EXECUTION_PRD.md` section 3.5 — Plateau Detection → Diversification
- Current `src/evolutor/evolution/plateau.py` — already has ruptures PELT

**What to build:**

UPDATE `src/evolutor/evolution/plateau.py`:

1. **`PlateauDetector`** — keep existing ruptures PELT but add:
   - `record_batch(fitness_values)` — record multiple values at once
   - `should_diversify(window=40)` → bool — True if no change point in last 40 evals

2. **`DiversificationStrategy` class:**
   - `__init__(archive, tree)` — takes MAP-Elites archive and evolution tree
   - `select_diverse_parent()` → node_id — select from UNDER-EXPLORED MAP-Elites cells (not the best cell)
   - `get_wider_mutation_params()` → dict — increase temperature, force different mutation type
   - `apply(tree, archive)` → node_id — execute diversification, return selected parent

**Verification:**

```bash
# V1: Syntax
python3 -c "import ast; ast.parse(open('src/evolutor/evolution/plateau.py').read()); print('V1 PASS')"

# V2: PlateauDetector works
python3 -c "
from evolutor.evolution.plateau import PlateauDetector
pd = PlateauDetector(window_size=10)
# Record flat fitness — should detect plateau
for _ in range(20):
    pd.record(0.5)
assert pd.detect(), 'Should detect plateau with flat fitness'
pd.reset()
# Record increasing fitness — should NOT detect plateau
for i in range(20):
    pd.record(i * 0.1)
assert not pd.detect(), 'Should NOT detect plateau with increasing fitness'
print('V2 PASS: plateau detection works')
"

# V3: DiversificationStrategy exists
python3 -c "
from evolutor.evolution.plateau import DiversificationStrategy
assert hasattr(DiversificationStrategy, 'select_diverse_parent')
assert hasattr(DiversificationStrategy, 'apply')
print('V3 PASS: DiversificationStrategy exists')
"
```

---

#### US-111: Main HGM evolution loop — budget-based with all components wired

**Required reading (MANDATORY — read the actual HGM code):**
- `/home/mekashirskiy/competitors/HGM/hgm.py` — the EXACT algorithm to implement
- `ralph/EXECUTION_PRD.md` section 3 + section 5 — all algorithms and phases
- `ralph/REVISED_ARCHITECTURE.md` section "Algorithm: HGM Tree + Cascading + MAP-Elites"
- `ralph/implementation_phases.md` — main loop pseudocode

**What to build:**

REWRITE `src/evolutor/evolution/loop.py` as the main HGM evolution loop:

1. **`EvolutionConfig` dataclass:**
   ```python
   eval_budget: int = 100        # Total task evaluations
   expansion_alpha: float = 0.6  # HGM sublinear growth
   max_steps_per_task: int = 50  # Agent step limit
   task_timeout: int = 600       # 10 min per task in Docker
   mutation_timeout: int = 120   # 2 min for LLM mutation
   plateau_window: int = 40      # Evals before plateau check
   cascade_max_stage: int = 1    # Quick reject stages (0=syntax, 1=smoke)
   ```

2. **`EvolutionReport` model** (Pydantic):
   - `evals_completed`, `tree_nodes`, `best_fitness`, `best_agent_id`
   - `archive_coverage`, `plateaus_detected`, `cascade_rejections`
   - `mutations_attempted`, `mutations_accepted`
   - `eval_log: list[dict]` — per-eval records

3. **`run_evolution(config, seed_code, tasks, project_root)` → `EvolutionReport`:**
   Main loop (from EXECUTION_PRD):
   ```
   tree = EvolutionTree(seed_code, tasks, config.eval_budget)
   archive = EvolutionArchive()
   mutator = Mutator()
   cascade = CascadingEvaluator(tasks, project_root)
   plateau = PlateauDetector()
   kernel = KernelIntegrityChecker(project_root)

   while tree.n_evals < config.eval_budget:
       kernel.check()  # Verify no tampering

       if tree.should_expand(config.expansion_alpha):
           # EXPAND: mutate to create new child
           parent_id = tree.thompson_sample(for_expansion=True)
           parent = tree.nodes[parent_id]
           failed_logs = get_failure_logs(parent)
           child_code, mtype, desc = mutator.diagnose_and_mutate(parent.code, failed_logs)
           cascade_result = cascade.evaluate(child_code, max_stage=config.cascade_max_stage)
           if cascade_result.passed:
               child_id = tree.add_child(parent_id, child_code, mtype, desc)
               archive.add_with_behavior(child_id, 0.0, child_code)
           else:
               record cascade rejection
       else:
           # MEASURE: evaluate existing node on new task
           node_id = tree.thompson_sample(for_expansion=False)
           task = tree.select_unevaluated_task(node_id)
           if task is None: continue
           result = eval_agent_code_docker(tree.nodes[node_id].code, task, ...)
           tree.record_eval(node_id, task['instance_id'], result.passed)
           archive.update fitness

       # Plateau check every N evals
       if tree.n_evals % 20 == 0:
           if plateau.detect(): diversify(tree, archive)

       # Persist state for crash recovery
       tree.save_state('results/evolution_state.json')
   ```

4. **`get_failure_logs(node)` helper** — format failed tasks as context string

5. **Wire to `eval_agent_code_docker()`** from harness.py for task evaluation

6. **Remove** all old generational loop code, old `_evaluate_agent`, `_evaluate_agent_local`, `_load_swebench_tasks`, `_run_agent_on_task`, `_format_failures`

**Verification:**

```bash
# V1: Syntax
python3 -c "import ast; ast.parse(open('src/evolutor/evolution/loop.py').read()); print('V1 PASS')"

# V2: Required exports
python3 -c "
from evolutor.evolution.loop import run_evolution, EvolutionConfig, EvolutionReport
print('V2 PASS: required exports exist')
"

# V3: EvolutionConfig has correct defaults
python3 -c "
from evolutor.evolution.loop import EvolutionConfig
c = EvolutionConfig()
assert c.eval_budget == 100, f'eval_budget should be 100, got {c.eval_budget}'
assert c.expansion_alpha == 0.6, f'expansion_alpha should be 0.6, got {c.expansion_alpha}'
assert c.plateau_window == 40
print('V3 PASS: config defaults correct')
"

# V4: EvolutionReport has required fields
python3 -c "
from evolutor.evolution.loop import EvolutionReport
r = EvolutionReport(evals_completed=0, tree_nodes=1, best_fitness=0.0,
                    best_agent_id='root', archive_coverage=0.0,
                    plateaus_detected=0, cascade_rejections=0,
                    mutations_attempted=0, mutations_accepted=0, eval_log=[])
print('V4 PASS: EvolutionReport fields correct')
"

# V5: No old generational code
python3 -c "
code = open('src/evolutor/evolution/loop.py').read()
assert '_evaluate_agent_local' not in code, 'Remove old _evaluate_agent_local'
assert 'datasets.load_dataset' not in code, 'Remove old HuggingFace dataset loading from loop'
assert 'for gen in range' not in code, 'Remove old generational loop — use budget-based'
print('V5 PASS: no legacy code')
"

# V6: Uses HGM components
python3 -c "
code = open('src/evolutor/evolution/loop.py').read()
assert 'EvolutionTree' in code, 'Must use EvolutionTree'
assert 'thompson_sample' in code, 'Must use thompson_sample'
assert 'should_expand' in code, 'Must use should_expand'
assert 'CascadingEvaluator' in code or 'cascade' in code.lower(), 'Must use cascade'
assert 'eval_agent_code_docker' in code, 'Must use eval_agent_code_docker from harness'
print('V6 PASS: uses HGM components')
"

# V7: Kernel integrity check is called in loop
python3 -c "
code = open('src/evolutor/evolution/loop.py').read()
assert 'kernel' in code.lower() and ('check' in code or 'verify' in code), 'Must call kernel integrity check in main loop'
print('V7 PASS: kernel check in loop')
"
```

---

### Phase 3 — Run + Results

---

#### US-112: Start infrastructure + run baseline benchmark

**What to do:**

1. **Check/start infrastructure:**
   - Check if vLLM is running on port 8000 (`curl http://127.0.0.1:8000/health`)
   - If not, start it (see `ralph/EXECUTION_PRD.md` section 12 for exact command)
   - Check if proxy is running on port 4000 (`curl http://127.0.0.1:4000/health`)
   - If not, start it: `python3 scripts/proxy_server.py --port 4000 --backend http://127.0.0.1:8000/v1 --model qwen3-coder-30b &`
   - Set environment variables: `no_proxy`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, `EVOLUTOR_MODEL`
   - Verify LLM responds: make a test API call

2. **Build SWE-bench Docker images** if none exist:
   - Use `/home/mekashirskiy/competitors/SWE-bench/` to build images
   - Target: flask and requests repos
   - If building fails (network issues), document what's available

3. **Run baseline benchmark:**
   - Execute `scripts/run_baseline.py`
   - Results saved to `results/baseline.json`
   - Print pass rate

**Verification:**

```bash
# V1: Baseline results exist
test -f results/baseline.json && echo "V1 PASS" || echo "V1 FAIL: no baseline results"

# V2: Baseline has correct structure
python3 -c "
import json
with open('results/baseline.json') as f:
    data = json.load(f)
assert isinstance(data, list) or isinstance(data, dict), 'baseline.json must be list or dict'
print(f'V2 PASS: baseline has {len(data)} entries' if isinstance(data, list) else f'V2 PASS: baseline loaded')
"
```

---

#### US-113: Run evolution with eval budget

**What to do:**

1. **Create `scripts/run_evolution.py`:**
   - Loads seed agent code from `src/evolutor/swebench/seed_agent.py`
   - Loads available tasks from Docker images
   - Calls `run_evolution(config, seed_code, tasks, project_root)`
   - Saves results to `results/evolution_report.json`
   - Saves tree state to `results/evolution_state.json`
   - Prints progress summary

2. **Run evolution:**
   - Start with eval_budget=30 (conservative, ~45-60 min)
   - If successful, increase budget if time permits
   - Log progress to stdout

3. **Handle errors gracefully:**
   - If Docker fails, log and skip that evaluation
   - If LLM fails, retry once then skip mutation
   - Save state after each evaluation for crash recovery

**Verification:**

```bash
# V1: Evolution script exists
python3 -c "import ast; ast.parse(open('scripts/run_evolution.py').read()); print('V1 PASS')"

# V2: Evolution results exist (after running)
test -f results/evolution_report.json && echo "V2 PASS" || echo "V2 NOTE: run evolution first"

# V3: Tree state saved
test -f results/evolution_state.json && echo "V3 PASS" || echo "V3 NOTE: run evolution first"
```

---

#### US-114: Extract best agent + comparison benchmark

**What to do:**

1. **Extract best agent:**
   - Load tree state from `results/evolution_state.json`
   - Find node with highest mean_utility (≥3 evaluations minimum)
   - Save best agent code to `results/best_agent.py`
   - If no evolved agent is better than root, document that

2. **Run full comparison:**
   - Run best evolved agent on ALL available tasks
   - Run baseline (root) agent on same tasks (if not already in baseline.json)
   - Save comparison to `results/comparison.json`:
     ```json
     {
       "baseline": {"pass_rate": 0.22, "tasks_passed": 2, "tasks_total": 9},
       "evolved": {"pass_rate": 0.44, "tasks_passed": 4, "tasks_total": 9, "agent_id": "node-a3f2"},
       "improvement": {"absolute": 0.22, "relative": 1.0},
       "per_task": [...]
     }
     ```

3. **Create `scripts/compare_results.py`:**
   - Takes baseline.json and evolution results
   - Prints formatted comparison table

**Verification:**

```bash
# V1: Best agent extracted
test -f results/best_agent.py && echo "V1 PASS" || echo "V1 NOTE: extract best agent first"

# V2: Comparison script exists
python3 -c "import ast; ast.parse(open('scripts/compare_results.py').read()); print('V2 PASS')"

# V3: Comparison results exist
test -f results/comparison.json && echo "V3 PASS" || echo "V3 NOTE: run comparison first"
```

---

#### US-115: Results documentation + evolution analysis

**What to do:**

1. **Create `results/ANALYSIS.md`** documenting:
   - Baseline performance (pass rate, per-task results)
   - Evolution run summary (evals, tree size, mutations)
   - Best evolved agent performance
   - Improvement delta (baseline vs evolved)
   - Mutation type success rates
   - Emergent behaviors discovered (if any)
   - Architecture diagram of the evolution system

2. **Commit all results:**
   ```bash
   git add results/ && git commit -m "results: evolution run complete"
   ```

3. **Generate tree visualization data** in `results/tree.json`:
   - Node hierarchy with fitness values
   - Mutation types used
   - Per-node evaluation counts

**Verification:**

```bash
# V1: Analysis document exists
test -f results/ANALYSIS.md && echo "V1 PASS" || echo "V1 FAIL"

# V2: Analysis has required sections
python3 -c "
content = open('results/ANALYSIS.md').read()
required = ['Baseline', 'Evolution', 'Comparison', 'Mutation']
for section in required:
    assert section.lower() in content.lower(), f'Missing section: {section}'
print('V2 PASS: all sections present')
"

# V3: Results committed
git log --oneline -5 | head -5
```

---

## Rules

- Python 3.11+; `src/evolutor/` layout; hatchling build
- Pydantic v2 for models; structlog for logging
- **NO STUBS** — every function must have a real implementation
- **NO MOCKS** in production code — mocks only in tests
- Run ALL verification commands before marking done
- EVERY commit must be pushed
- Progress tracking is MANDATORY
- Read competitor code BEFORE implementing — don't reinvent what already works
- Use environment variables for ALL LLM configuration — never hardcode
- Keep seed_agent.py SIMPLE — complexity is discovered by evolution, not designed in
