# Competitor Insights: Patterns, Algorithms, and Prompt Templates

Extracted from cloned repos on 2026-03-05. All file references are absolute paths under `/home/mekashirskiy/competitors/`.

---

## 1. DGM — Darwin Godel Machine

**Repo:** `/home/mekashirskiy/competitors/dgm/`
**Paper:** `/home/mekashirskiy/papers/dgm.pdf` (arXiv 2505.22954)

### 1.1 Parent Selection Algorithm

Source: `/home/mekashirskiy/competitors/dgm/DGM_outer.py`, lines 50–150

DGM maintains a flat archive of all agent variants. At each generation it picks parents using one of several strategies:

```python
# score_child_prop (default): score × 1/(1+children_count)
# Logistic-normalised score to avoid winner-take-all
scores = [1 / (1 + math.exp(-10*(score-0.5))) for score in scores]
children_counts = [1 / (1 + count) for count in children_counts]
probabilities = [score * count for score, count in zip(scores, children_counts)]
probabilities = [prob / sum(probabilities) for prob in probabilities]
parent_commits = random.choices(commits, probabilities, k=selfimprove_size)
```

Key insight: the **inverse-children penalty** prevents over-exploitation of high-scoring parents. A parent that has already spawned many children gets down-weighted.

### 1.2 Archive Management

Source: `/home/mekashirskiy/competitors/dgm/DGM_outer.py`, lines 174–219

Two archive update strategies:
- `keep_all`: admit every compiled child regardless of score (default)
- `keep_better`: only keep if `score >= original_score - noise_leeway` (default leeway = 0.1)

Full-eval threshold (line 192–219):

```python
def get_full_eval_threshold(output_dir, archive):
    # second-highest score in the archive — only run full eval if you beat the runner-up
    threshold = sorted(archive_scores, reverse=True)[1] if len(archive_scores) > 1 else archive_scores[0]
    threshold = max(threshold, 0.4)   # floor at 0.4
    return threshold
```

Two-stage evaluation: small subset first, then medium subset if score >= 0.4. Full suite only if score >= full_eval_threshold.

### 1.3 Entry Selection (what to improve)

Source: `/home/mekashirskiy/competitors/dgm/DGM_outer.py`, lines 112–148

Probabilistic routing at 25%/25%/25% for three meta-tasks:

```python
# 25% chance: fix empty patches (if >= 10% of tasks have empty patches)
if len(empty_ids) >= 0.1 * num_total_ids and random.random() < 0.25:
    entry = 'solve_empty_patches'

# 25% chance: handle stochasticity (retry/best-of-n)
elif random.random() < 0.25:
    entry = 'solve_stochasticity'

# 25% chance: fix context length exceeded
elif any_exceeding_context_length(...) and random.random() < 0.25:
    entry = 'solve_contextlength'

# Fallback: random unresolved task
else:
    entry = random.choice(unresolved_ids)
```

### 1.4 Self-Improvement Prompt Templates (verbatim)

Source: `/home/mekashirskiy/competitors/dgm/prompts/self_improvement_prompt.py`

**System message (diagnose_system_message), lines 64–72:**

```
Here is the implementation of the coding agent.

# Coding Agent Implementation
----- Coding Agent Implementation Start -----
{code}
----- Coding Agent Implementation End -----

Your task is to identify ONE detailed plan that would improve the agent's coding ability. The improvement should not be specific to any particular GitHub issue or repository.
```

**Diagnose prompt for SWE issues (lines 77–120):**

```
# Agent Running Log
----- Agent Running Log Start -----
{md_log}
----- Agent Running Log End -----

# GitHub Issue
The GitHub issue that the agent is trying to solve.
----- GitHub Issue Start -----
{github_issue}
----- GitHub Issue End -----

# Predicted Patch
The agent's predicted patch to solve the issue.
----- Predicted Patch Start -----
{predicted_patch}
----- Predicted Patch End -----

# Private Test Patch
SWE-bench's official private tests to detect whether the issue is solved. This is not available to the agent during evaluation. The agent should try to implement its own tests.
----- Private Test Patch Start -----
{test_patch}
----- Private Test Patch End -----

# Issue Test Results
The test results from SWE-bench using the above official private tests.
----- Issue Test Results Start -----
{eval_log}
----- Issue Test Results End -----

Respond precisely in the following format including the JSON start and end markers:

```json
<JSON>
```

In <JSON>, provide a JSON response with the following fields:
- "log_summarization": Analyze the above logs and summarize how the agent tried to solve the GitHub issue. Note which tools and how they are used, the agent's problem-solving approach, and any issues encountered.
- "potential_improvements": Identify potential improvements to the coding agent that could enhance its coding capabilities. Focus on the agent's general coding abilities (e.g., better or new tools usable across any repository) rather than issue-specific fixes (e.g., tools only usable in one framework). All necessary dependencies and environment setup have already been handled, so do not focus on these aspects.
- "improvement_proposal": Choose ONE high-impact improvement from the identified potential improvements and describe it in detail. This should be a focused and comprehensive plan to enhance the agent's overall coding ability.
- "implementation_suggestion": Referring to the coding agent's summary and implementation, think critically about what feature or tool could be added or improved to best implement the proposed improvement. If the proposed feature can be implemented by modifying the existing tools, describe the modifications needed, instead of suggesting a new tool.
- "problem_description": Phrase the improvement proposal and implementation suggestion as a GitHub issue description. It should clearly describe the feature so that a software engineer viewing the issue and the repository can implement it.

Your response will be automatically parsed, so ensure that the string response is precisely in the correct format. Do NOT include the `<JSON>` tag in your output.
```

**Stochasticity fix prompt (lines 138–152):**

```
Since the coding agent is stochastic, it may not produce the correct patch for the given problem statement on the first try. Take into account the agent's stochastic nature and provide a solution to handle such cases. For example, one solution could be to ask the agent to try multiple times and select the best patch. The file `utils/eval_utils.py` contains helper functions to evaluate the generated patches. Giving previous attempts as context to the agent may also help.

[JSON response fields: potential_improvements, improvement_proposal, implementation_suggestion, problem_description]
```

**Empty-patches fix prompt (lines 122–136):**

```
There are some empty patches when attempting to solve GitHub issues. Since the coding agent is stochastic, it may not always produce a patch. Handle cases where the coding agent fails to generate a patch or generates one that only modifies the test cases without editing the primary source code. For example, the simplest solution is to ask the agent to try again.

[JSON response fields: potential_improvements, improvement_proposal, implementation_suggestion, problem_description]
```

**Context-length fix prompt (lines 154–172):**

```
While the coding agent is attempting to solve GitHub issues, it encounters an error due to the input being too long for the requested model. [...] Handle context length only if the context window limit is reached and caught as an exception; otherwise, it is okay to leave it as is.

<error_message>
Error in get_response_withtools: Error code: 400 - {'message': 'Input is too long for requested model.'}
</error_message>
```

### 1.5 Coding Agent Summary (injected into every self-improvement prompt)

Source: `/home/mekashirskiy/competitors/dgm/prompts/self_improvement_prompt.py`, lines 6–27

```
# Coding Agent Summary

- **Main File**: `coding_agent.py`
  - Primary Class: `AgenticSystem`
  - The `forward()` function is the central entry point.
  - Prompts are located either within the `forward()` function or in the `prompts/` directory.
- **Tools**: `tools/`
  - Each tool must have a `tool_info()` function that returns a JSON object containing 'name', 'description', and 'input_schema'.
  - Each tool must have a `tool_function()` function that takes the arguments defined in input_schema, performs the tool's task, and returns a string.
- The agent is very good at automatically utilizing the right available tools at the right time. So do not have an agentic flow that explicitly forces a tool's usage.
- Tools should be designed to be as general as possible, ensuring they work across any GitHub repository.
- Do not use 'while True' loops in the agent's code.
- Do not install additional packages or dependencies directly. Update `requirements.txt` if new dependencies are required.
```

### 1.6 Tool Definitions (DGM)

Source: `/home/mekashirskiy/competitors/dgm/tools/bash.py` and `edit.py`

**bash tool schema:**
```json
{
  "name": "bash",
  "description": "Run commands in a bash shell\n* State is persistent across command calls...",
  "input_schema": {
    "type": "object",
    "properties": {
      "command": {"type": "string", "description": "The bash command to run."}
    },
    "required": ["command"]
  }
}
```

BashSession uses a sentinel pattern (`<<exit>>`) to detect command completion. Persistent across calls — a single asyncio subprocess is kept alive. Timeout: 120s.

**editor tool schema:**
```json
{
  "name": "editor",
  "description": "Custom editing tool for viewing, creating, and editing files\n* The `edit` command overwrites the entire file...",
  "input_schema": {
    "type": "object",
    "properties": {
      "command": {"type": "string", "enum": ["view", "create", "edit"]},
      "path":    {"type": "string", "description": "Absolute path to file or directory"},
      "file_text": {"type": "string", "description": "Content for create/edit"}
    },
    "required": ["command", "path"]
  }
}
```

Entire-file overwrite model — no line-range edits. Files up to 10 000 chars before truncation with `<response clipped>`.

**Tool-use prompt format (non-native tool-calling models):**
Source: `/home/mekashirskiy/competitors/dgm/prompts/tooluse_prompt.py`

```
Here are the available tools:
<tool source code for each .py in tools/>

Use the available tools in this format:
```
<tool_use>
{
    'tool_name': ...,
    'tool_input': ...
}
</tool_use>
```
```

---

## 2. HGM — Hierarchical Godel Machine

**Repo:** `/home/mekashirskiy/competitors/HGM/`
**Paper:** `/home/mekashirskiy/papers/hgm.pdf` (arXiv 2510.21614)

### 2.1 Thompson Sampling Parent Selection (CMP Algorithm)

Source: `/home/mekashirskiy/competitors/HGM/hgm.py`, lines 360–450

HGM builds an explicit tree (not a flat archive). Parent selection uses Thompson sampling over Beta distributions, one per node:

```python
def TS_sample(evals):
    # evals: list of lists; each inner list is a binary sequence (1=resolved, 0=unresolved)
    alphas = [1 + np.sum(de) for de in evals]           # successes + 1 (Beta prior)
    betas  = [1 + len(de) - np.sum(de) for de in evals] # failures  + 1
    if opt_cfg.cool_down:
        # Temperature cooling: scale alpha/beta by budget^beta / remaining^beta
        alphas = np.array(alphas) * (
            10000
            if exec_cfg.max_task_evals == hgm_utils.n_task_evals
            else exec_cfg.max_task_evals**opt_cfg.beta
                 / (exec_cfg.max_task_evals - hgm_utils.n_task_evals) ** opt_cfg.beta
        )
        betas = np.array(betas) * (same scaling factor)
    thetas = np.random.beta(alphas, betas)   # sample success probability
    return np.argmax(thetas)                 # pick node with highest sample
```

Key parameters:
- `alpha`: controls expand-vs-evaluate ratio (`n_task_evals^alpha >= n_nodes`)
- `beta`: cooling exponent (default in config.yaml)
- `n_pseudo_descendant_evals`: virtual evaluations added to descendants

**Expand vs. Evaluate decision (lines 406–460):**

```python
if n_task_evals**opt_cfg.alpha >= len(nodes) - 1 + n_pending_expands:
    # Expand: generate a new child via self-improvement
    expand()
else:
    # Evaluate: run an existing node on one more task
    evaluate()
```

**Node selection for expansion:** TS on descendant eval history (not just the node's own).

**Node selection for evaluation:** TS on the node's own utility_measures.

### 2.2 Entry Selection (HGM)

Source: `/home/mekashirskiy/competitors/HGM/hgm_utils.py`, lines 88–151

Identical stochastic routing to DGM (same 25%/25%/25% logic), but HGM also checks context-length errors using regex patterns for multiple providers:

```python
error_strs = [
    r"Error in get_response_withtools: Error code: 400 - {'message': 'Input is too long for requested model.'}",
    r"Error in get_response_withtools: Error code: 400 - {'object': 'error', 'message': \"This model's maximum context length is \d+ tokens. ...",
    r"Error in get_response_withtools: Error code: 400 - {'error': {'message': 'Your input exceeds the context window...",
]
```

---

## 3. mini-SWE-agent

**Repo:** `/home/mekashirskiy/competitors/mini-swe-agent/`

### 3.1 Minimal Agent Scaffold

Source: `/home/mekashirskiy/competitors/mini-swe-agent/src/minisweagent/agents/default.py`

Full agent in ~155 lines. Key design principles:

```python
class DefaultAgent:
    def run(self, task: str = "", **kwargs) -> dict:
        """Bootstrap: add system + instance messages, then loop step() until exit."""
        self.messages = []
        self.add_messages(
            self.model.format_message(role="system",   content=self._render_template(self.config.system_template)),
            self.model.format_message(role="user",     content=self._render_template(self.config.instance_template)),
        )
        while True:
            try:
                self.step()
            except InterruptAgentFlow as e:
                self.add_messages(*e.messages)
            except Exception as e:
                self.handle_uncaught_exception(e)
                raise
            finally:
                self.save(self.config.output_path)
            if self.messages[-1].get("role") == "exit":
                break
        return self.messages[-1].get("extra", {})

    def step(self) -> list[dict]:
        return self.execute_actions(self.query())

    def query(self) -> dict:
        """Check limits, call model, track cost."""
        if 0 < self.config.step_limit <= self.n_calls or 0 < self.config.cost_limit <= self.cost:
            raise LimitsExceeded(...)
        self.n_calls += 1
        message = self.model.query(self.messages)
        self.cost += message.get("extra", {}).get("cost", 0.0)
        return message

    def execute_actions(self, message: dict) -> list[dict]:
        outputs = [self.env.execute(action) for action in message.get("extra", {}).get("actions", [])]
        return self.add_messages(*self.model.format_observation_messages(message, outputs, ...))
```

Cost and step limits enforced per-call. Trajectory serialized after every step (never lose progress). Actions extracted from `message["extra"]["actions"]` — model parses its own output into structured actions.

### 3.2 SWE-agent Default System Prompt Template

Source: `/home/mekashirskiy/competitors/SWE-agent/config/default.yaml`

```yaml
agent:
  templates:
    system_template: |-
      You are a helpful assistant that can interact with a computer to solve tasks.

    instance_template: |-
      <uploaded_files>
      {{working_dir}}
      </uploaded_files>
      I've uploaded a python code repository in the directory {{working_dir}}. Consider the following PR description:

      <pr_description>
      {{problem_statement}}
      </pr_description>

      Can you help me implement the necessary changes to the repository so that the requirements specified in the <pr_description> are met?
      I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!
      Your task is to make the minimal changes to non-tests files in the {{working_dir}} directory to ensure the <pr_description> is satisfied.
      Follow these steps to resolve the issue:
      1. As a first step, it might be a good idea to find and read code relevant to the <pr_description>
      2. Create a script to reproduce the error and execute it with `python <filename.py>` using the bash tool, to confirm the error
      3. Edit the sourcecode of the repo to resolve the issue
      4. Rerun your reproduce script and confirm that the error is fixed!
      5. Think about edgecases and make sure your fix handles them as well
      Your thinking should be thorough and so it's fine if it's very long.

    next_step_template: |-
      OBSERVATION:
      {{observation}}

    next_step_no_output_template: |-
      Your command ran successfully and did not produce any output.

  tools:
    bundles:
      - path: tools/registry
      - path: tools/edit_anthropic
      - path: tools/review_on_submit_m
    enable_bash_tool: true
    parse_function:
      type: function_calling

  history_processors:
    - type: cache_control
      last_n_messages: 2
```

Key: `cache_control` on last 2 messages dramatically reduces API cost for long trajectories.

---

## 4. OpenEvolve

**Repo:** `/home/mekashirskiy/competitors/openevolve/`

### 4.1 Cascade Evaluation Structure

Source: `/home/mekashirskiy/competitors/openevolve/openevolve/evaluator.py`, lines 360–536

Three-stage cascade. Default thresholds from `/home/mekashirskiy/competitors/openevolve/configs/default_config.yaml`:

```yaml
cascade_evaluation: true
cascade_thresholds:
  - 0.5    # Stage 1 → Stage 2 gate
  - 0.75   # Stage 2 → Stage 3 gate
  - 0.9    # (used as final quality bar in some examples)
```

Algorithm:
1. Run `evaluate_stage1(program_path)` — fast, cheap tests (unit tests, syntax checks)
2. If `combined_score >= 0.5`: run `evaluate_stage2` — medium difficulty
3. If `combined_score >= 0.75`: run `evaluate_stage3` — expensive full evaluation
4. If any stage times out: return partial results from previous stages, mark `timeout=True`
5. Merge metrics across stages (float-cast all values, later stages overwrite earlier)

Threshold check logic (`_passes_threshold`, lines 668–707):
- Uses `combined_score` key if present
- Falls back to mean of all numeric metrics except `error`

### 4.2 LLM Ensemble

Source: `/home/mekashirskiy/competitors/openevolve/openevolve/llm/ensemble.py`

Weighted random sampling over a fleet of models:

```python
class LLMEnsemble:
    def __init__(self, models_cfg):
        self.weights = [model.weight for model in models_cfg]
        total = sum(self.weights)
        self.weights = [w / total for w in self.weights]      # normalize

    def _sample_model(self):
        index = self.random_state.choices(range(len(self.models)), weights=self.weights, k=1)[0]
        return self.models[index]

    async def generate_with_context(self, system_message, messages, **kwargs):
        model = self._sample_model()
        return await model.generate_with_context(system_message, messages, **kwargs)

    async def generate_all_with_context(self, system_message, messages, **kwargs):
        """For LLM evaluation: query ALL models, weight-average their metrics."""
        responses = []
        for model in self.models:
            responses.append(await model.generate_with_context(system_message, messages, **kwargs))
        return responses
```

Key distinction: `generate` samples one model; `generate_all_with_context` queries all and averages. The latter is used for LLM-as-evaluator scoring where you want consensus.

LLM feedback weight in scoring (evaluator.py line ~213):

```python
# 70% task score + 30% LLM quality
eval_result.metrics["combined_score"] = accuracy * 0.7 + llm_average * 0.3
```

### 4.3 Parallel Evaluation

Source: `/home/mekashirskiy/competitors/openevolve/openevolve/evaluator.py`, lines 709–727

```python
async def evaluate_multiple(self, programs):
    tasks = [
        self.task_pool.create_task(self.evaluate_program, program_code, program_id)
        for program_code, program_id in programs
    ]
    return await asyncio.gather(*tasks)
```

`TaskPool` caps concurrency at `config.parallel_evaluations` (default 4). Uses `asyncio.gather` so all run truly in parallel.

---

## 5. Cross-Cutting Best Practices

### 5.1 Docker Isolation for Eval
DGM and HGM both run each self-improvement attempt inside a fresh Docker container:
- Apply all ancestor patches with `patch -p1 < parent_patch.txt`
- Run `git add --all && git commit` to capture a clean baseline hash
- Copy outputs back to host before container removal
- 30-minute timeout per self-improvement attempt (`timeout 1800 python coding_agent.py`)

### 5.2 Two-phase Evaluation (small → medium subset)
Both DGM and HGM:
- Use a "small" subset (~20–30 tasks) for fast fitness signal
- Only advance to "medium" subset if score >= 0.4 threshold
- Only advance to full benchmark if score beats the current runner-up

### 5.3 Retry + Validation Loop
DGM `self_improve_step.py` wraps every LLM call in `max_attempts=3` retry with recursion. Always validate:
1. Patch file exists
2. Patch file is non-empty
3. Code compiles (import test)

### 5.4 Structured JSON Response Pattern
Every prompt in DGM/HGM asks the LLM for a JSON block delimited by triple-backtick fences:

```
Respond precisely in the following format including the JSON start and end markers:

```json
<JSON>
```

Do NOT include the `<JSON>` tag in your output.
```

Parsed with `extract_json_between_markers()`. If JSON extraction fails, the entire attempt retries (up to 3 times).

### 5.5 Diagnose → Improve Two-Step
DGM/HGM use a two-call pattern per self-improvement:
1. **Diagnose** (o1 / frontier model): analyze failure logs → produce `problem_description` JSON
2. **Implement** (claude / coding agent): given the problem_description, modify the agent's own code

The diagnose model is deliberately different from (and typically more capable than) the implementing model.

### 5.6 Cost Control in mini-SWE-agent
- Hard cost limit (default $3.00 per trajectory)
- Hard step limit (configurable)
- Anthropic prompt caching on last 2 messages (`cache_control: last_n_messages: 2`)
- Serialize trajectory to disk after every step

---

## 6. Papers Downloaded

| File | arXiv ID | Description |
|------|----------|-------------|
| `/home/mekashirskiy/papers/dgm.pdf` | 2505.22954 | Darwin Godel Machine |
| `/home/mekashirskiy/papers/sica.pdf` | 2504.15228 | Self-Improving Coding Agent |
| `/home/mekashirskiy/papers/hgm.pdf` | 2510.21614 | Hierarchical Godel Machine |
| `/home/mekashirskiy/papers/live_swe_agent.pdf` | 2511.13646 | Live SWE-agent |
| `/home/mekashirskiy/papers/opensage.pdf` | 2602.16891 | OpenSAGE |
| `/home/mekashirskiy/papers/sage_abstraction.pdf` | 2511.05931 | SAGE Abstraction |
