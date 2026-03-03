# PRD: Evolutor — Self-Driving, Self-Improving Codebase Framework

## Introduction

Evolutor is a recursive, self-improving software development framework. It combines a multi-agent LLM orchestrator (planner/worker/critic hierarchy via LangGraph) with a MAP-Elites quality-diversity evolutionary engine (pyribs + pymoo NSGA-III), operating on isolated git worktrees inside Docker sandboxes. An immutable kernel enforces safety invariants and gates every change before it can be merged. The result: a framework that autonomously implements tasks, tests them, evolves better solutions, and improves its own playbooks over time.

**Repository:** `/home/mekashirskiy/evolutor` (git-initialized, remote: https://github.com/mariklolik/evolutor.git)
**Language:** Python ≥3.11
**Entry point after build:** `evolutor` CLI

---

## Goals

- Build the entire framework from scratch in a single repo (`src/evolutor/` layout)
- Every phase must end with `pytest` passing and `ruff check src/` clean
- All cross-module data uses Pydantic v2 models
- All I/O-bound code is async-first; CPU-bound work uses `asyncio.to_thread`
- Structured logging via `structlog` with bound context throughout
- The framework must be capable of running `evolutor evolve` on its own codebase by Phase 7

---

## User Stories

### Phase 0 — Project Scaffolding + Foundation Types

---

### US-001: Create pyproject.toml
**Description:** As a developer, I want a PEP 621 project file so that the package installs correctly and all dependencies are declared.

**Acceptance Criteria:**
- [ ] `pyproject.toml` exists at repo root with `[project]` metadata: name=evolutor, version=0.1.0, requires-python=">=3.11"
- [ ] All dependency groups present: core (pydantic, structlog, httpx, typer, rich), git (pygit2, dulwich, githubkit), memory (mem0ai, chromadb, networkx, tree-sitter, tree-sitter-languages), evolution (pyribs, pymoo, ruptures), verification (hypothesis, ruff, mypy, bandit, radon, coverage, pytest-benchmark), sandbox (docker), orchestration (langgraph, redis)
- [ ] `[project.optional-dependencies]` dev group: pytest, pytest-asyncio, pytest-cov, ruff, mypy, pre-commit
- [ ] Entry point: `evolutor = "evolutor.cli.app:main"`
- [ ] `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` sections present
- [ ] Build backend: hatchling
- [ ] `pip install -e ".[dev]"` succeeds

---

### US-002: Create package skeleton
**Description:** As a developer, I want all package directories with `__init__.py` files so that Python can import every module.

**Acceptance Criteria:**
- [ ] All directories created under `src/evolutor/`: cli/, kernel/, orchestrator/, memory/, evolution/, verification/, git/, sandbox/, tools/builtin/, tools/mcp/, tools/forge/, types/
- [ ] Every directory has `__init__.py` (may be empty)
- [ ] Test directories created: tests/unit/, tests/integration/, tests/benchmarks/
- [ ] Support directories created: configs/, playbooks/, prompts/, scripts/, docs/
- [ ] `pytest tests/` collects 0 tests, 0 failures (no errors)

---

### US-003: Package entry points
**Description:** As a developer, I want `python -m evolutor` to work and the package to export its version.

**Acceptance Criteria:**
- [ ] `src/evolutor/__init__.py` exports `__version__ = "0.1.0"` and configures structlog
- [ ] `src/evolutor/__main__.py` contains `from evolutor.cli.app import main; main()`
- [ ] `python -m evolutor` runs without ImportError

---

### US-004: Config types (`types/config.py`)
**Description:** As a developer, I want a root Pydantic v2 config model so that all subsystems share a consistent configuration schema.

**Acceptance Criteria:**
- [ ] `src/evolutor/types/config.py` defines: `SandboxConfig`, `GitConfig`, `MemoryConfig`, `EvolutionConfig`, `OrchestratorConfig`, `EvolutorConfig`
- [ ] All fields have sensible defaults (no required fields)
- [ ] `python -c "from evolutor.types.config import EvolutorConfig; EvolutorConfig()"` succeeds
- [ ] `mypy src/evolutor/types/config.py` passes

---

### US-005: Task types (`types/task.py`)
**Description:** As a developer, I want Task/TaskResult/TaskStatus models so that every layer speaks the same task language.

**Acceptance Criteria:**
- [ ] `src/evolutor/types/task.py` defines: `TaskStatus` enum (pending/planning/in_progress/verifying/completed/failed/rolled_back), `TaskPriority` enum (critical/high/medium/low), `Task` model, `TaskResult` model
- [ ] `Task` has: id (uuid default), parent_id, title, description, status, priority, timestamps, assigned_to, worktree_path, branch_name, subtasks, dependencies, metadata
- [ ] `TaskResult` has: task_id, success, files_changed, commit_sha, metrics, error, duration_seconds
- [ ] `python -c "from evolutor.types.task import Task; print(Task(title='t', description='d').model_dump_json())"` prints valid JSON

---

### US-006: Agent types (`types/agent.py`)
**Description:** As a developer, I want agent role models so that agents can communicate with typed messages.

**Acceptance Criteria:**
- [ ] `src/evolutor/types/agent.py` defines: `AgentRole` enum (planner/worker/critic/meta_improver), `AgentState` model, `AgentMessage` model
- [ ] `AgentMessage` has: sender, receiver (both `AgentRole`), content, task_id, timestamp, message_type (instruction/result/feedback/escalation)
- [ ] `mypy src/evolutor/types/agent.py` passes

---

### US-007: Metrics types (`types/metrics.py`)
**Description:** As a developer, I want metrics and fitness models so that verification and evolution share a common data contract.

**Acceptance Criteria:**
- [ ] `src/evolutor/types/metrics.py` defines: `CodeMetrics`, `FitnessVector`, `BehaviorDescriptor`
- [ ] `FitnessVector.to_minimize()` returns `list[float]` negating all objectives (pymoo minimizes)
- [ ] `BehaviorDescriptor` has `complexity: float` and `novelty: float` (both 0..1)
- [ ] `mypy src/evolutor/types/metrics.py` passes

---

### US-008: Memory types (`types/memory.py`)
**Description:** As a developer, I want memory layer models so that all memory tiers exchange typed data.

**Acceptance Criteria:**
- [ ] `src/evolutor/types/memory.py` defines: `MemoryEntry`, `KnowledgeNode`, `Playbook`
- [ ] `Playbook` has `helpful_count: int` and `harmful_count: int` for ACE-pattern scoring
- [ ] `KnowledgeNode` has: id, kind (module/class/function/variable/import), name, file_path, start_line, end_line, signature, docstring, children, edges
- [ ] `mypy src/evolutor/types/memory.py` passes

---

### US-009: Config files and boilerplate
**Description:** As a developer, I want TOML config files and project documentation so that the project is ready for contributors and deployment.

**Acceptance Criteria:**
- [ ] `configs/default.toml` contains TOML representation of `EvolutorConfig` defaults
- [ ] `configs/models.toml` maps agent roles to model names/temperatures
- [ ] `configs/sandbox.toml` contains Docker image config and resource limits
- [ ] `README.md` contains project description, installation, and quickstart
- [ ] `LICENSE` contains MIT license text
- [ ] `AGENTS.md` contains instructions for AI agents working in this codebase
- [ ] `EVOLUTOR.md` contains architecture overview

---

### Phase 1 — Git Layer + Kernel Core

---

### US-010: Core git operations (`git/ops.py`)
**Description:** As a developer, I want low-level git operations via pygit2 so that all git interactions are programmatic and testable.

**Acceptance Criteria:**
- [ ] `src/evolutor/git/ops.py` defines `GitOps` class with methods: `current_branch()`, `create_branch()`, `checkout()`, `stage_files()`, `commit()`, `get_diff()`, `get_log()`, `get_file_at_ref()`, `merge()`, `cherry_pick()`
- [ ] All methods use pygit2 (not subprocess)
- [ ] `ruff check src/evolutor/git/ops.py` passes

---

### US-011: Worktree manager (`git/worktree.py`)
**Description:** As a developer, I want worktree lifecycle management so that worker agents operate in fully isolated copies of the repo.

**Acceptance Criteria:**
- [ ] `src/evolutor/git/worktree.py` defines `WorktreeManager` with: `create()`, `remove()`, `list_active()`, `get_worktree_repo()`, `cleanup_stale()`
- [ ] `WorktreeInfo` Pydantic model: name, path, branch, is_locked
- [ ] Worktrees created under path from `GitConfig.worktree_base`

---

### US-012: Branch strategy (`git/branching.py`)
**Description:** As a developer, I want branch naming conventions so that evolution and task branches are discoverable and consistent.

**Acceptance Criteria:**
- [ ] `src/evolutor/git/branching.py` defines `BranchStrategy` with: `generate_branch_name(task)`, `parse_branch_name(name)`, `get_evolution_branches(repo)`, `get_merge_candidates(repo, target)`
- [ ] Prefix map: feature→feat/, fix→fix/, evolution→evo/, experiment→exp/
- [ ] `BranchMetadata` Pydantic model returned by `parse_branch_name`

---

### US-013: Conflict resolution (`git/conflict.py`)
**Description:** As a developer, I want merge conflict detection and resolution utilities so that the orchestrator can handle merge conflicts programmatically.

**Acceptance Criteria:**
- [ ] `src/evolutor/git/conflict.py` defines `ConflictResolver` with: `detect_conflicts()`, `auto_resolve()`, `generate_resolution_prompt()`
- [ ] `auto_resolve` supports "ours", "theirs" strategies
- [ ] `ConflictInfo` and `Resolution` Pydantic models defined

---

### US-014: Audit trail (`git/audit.py`)
**Description:** As a developer, I want a git-notes-based audit log so that every agent action is traceable without altering commit history.

**Acceptance Criteria:**
- [ ] `src/evolutor/git/audit.py` defines `AuditLog` using `refs/notes/evolutor`
- [ ] Methods: `record_action(repo, action, metadata)`, `get_history(repo, n)`, `get_actions_for_commit(repo, sha)`
- [ ] Metadata stored as structured JSON in git notes
- [ ] `AuditEntry` Pydantic model defined

---

### US-015: Invariant registry (`kernel/invariants.py`)
**Description:** As a developer, I want an invariant registry so that safety constraints can be registered and checked against any context.

**Acceptance Criteria:**
- [ ] `src/evolutor/kernel/invariants.py` defines `Invariant`, `InvariantRegistry`, `InvariantReport`, `InvariantViolation`
- [ ] Built-in invariants registered: tests_must_pass, no_security_regressions, kernel_immutable, config_valid
- [ ] `InvariantRegistry.check_all(context)` returns `InvariantReport`
- [ ] Critical violations cause immediate rejection

---

### US-016: Kernel evaluator (`kernel/evaluator.py`)
**Description:** As a developer, I want a central evaluator that gates all code changes so that no unsafe change can be accepted without passing invariants and metrics checks.

**Acceptance Criteria:**
- [ ] `src/evolutor/kernel/evaluator.py` defines `Evaluator` with async `evaluate()` method
- [ ] `EvaluationResult` model: accepted (bool), reason (str), invariant_report, metrics_delta, confidence
- [ ] `compute_delta(before, after)` returns `MetricsDelta`
- [ ] `should_accept(evaluation)` returns bool

---

### US-017: Rollback manager (`kernel/rollback.py`)
**Description:** As a developer, I want git-based rollback so that any failed evolution or task can be safely undone.

**Acceptance Criteria:**
- [ ] `src/evolutor/kernel/rollback.py` defines `RollbackManager` with: `create_savepoint(label)`, `rollback_to(sha)`, `rollback_branch(branch)`, `list_savepoints()`
- [ ] `Savepoint` Pydantic model defined
- [ ] `create_savepoint` returns commit SHA string
- [ ] `rollback_to` uses `GitOps` and `AuditLog`

---

### US-018: Safety boundary (`kernel/safety.py`)
**Description:** As a developer, I want a safety boundary checker so that agents cannot modify protected files or run dangerous commands.

**Acceptance Criteria:**
- [ ] `src/evolutor/kernel/safety.py` defines `SafetyBoundary` with: `check_file_access()`, `check_command()`, `validate_diff()`, `get_risk_level()`
- [ ] `PROTECTED_PATHS` includes: `src/evolutor/kernel/`, `pyproject.toml`, `.git/`
- [ ] `RiskLevel` enum: safe/moderate/high/critical
- [ ] `CommandSafety` and `DiffSafety` Pydantic models defined

---

### US-019: Trust scorer (`kernel/trust.py`)
**Description:** As a developer, I want graduated trust scoring for agents so that high-trust agents can operate with fewer gates and low-trust agents require review.

**Acceptance Criteria:**
- [ ] `src/evolutor/kernel/trust.py` defines `TrustScorer` with: `compute_trust()`, `should_require_review()`, `update_trust()`
- [ ] Trust levels L1-L5 defined
- [ ] Trust score computed from agent's task result history (success rate, risk level of past changes)

---

### US-020: Git + Kernel unit tests
**Description:** As a developer, I want unit tests for git ops and kernel so that I can verify correctness without manual testing.

**Acceptance Criteria:**
- [ ] `tests/unit/test_git_ops.py`: creates temp git repo fixture, tests branch create/checkout/commit/diff/merge, worktree create/remove/list, branch naming, audit log write/read
- [ ] `tests/unit/test_kernel.py`: tests invariant registration/checking, evaluator accept/reject logic, rollback create/restore, safety boundary path checking, trust score computation
- [ ] `pytest tests/unit/test_git_ops.py tests/unit/test_kernel.py -v` passes

---

### Phase 2 — Sandbox + Verification Layers

---

### US-021: Docker sandbox manager (`sandbox/docker.py`)
**Description:** As a developer, I want Docker container lifecycle management so that all code execution happens in isolated, resource-limited environments.

**Acceptance Criteria:**
- [ ] `src/evolutor/sandbox/docker.py` defines `SandboxManager` with async methods: `create()`, `execute()`, `destroy()`, `list_active()`, `cleanup_all()`
- [ ] `SandboxInstance` model: container_id, name, worktree_path, created_at, status
- [ ] `ExecutionResult` model: exit_code, stdout, stderr, duration_seconds, resource_usage
- [ ] All methods are async

---

### US-022: Resource limiter (`sandbox/resource.py`)
**Description:** As a developer, I want resource limit enforcement so that sandboxed containers cannot exhaust system resources.

**Acceptance Criteria:**
- [ ] `src/evolutor/sandbox/resource.py` defines `ResourceLimiter` with: `get_container_config()`, `check_usage()`
- [ ] Container config includes: mem_limit, cpu_period/quota, pids_limit=256, storage_opt size=1G
- [ ] `ResourceUsage` model: memory_mb, cpu_percent, disk_mb, pid_count

---

### US-023: Network policy (`sandbox/network.py`)
**Description:** As a developer, I want network isolation for containers so that sandboxed code cannot make unauthorized network calls.

**Acceptance Criteria:**
- [ ] `src/evolutor/sandbox/network.py` defines `NetworkPolicy` with: `create_isolated_network()`, `apply_policy()`, `block_all()`, `cleanup_networks()`
- [ ] Default policy blocks all outbound traffic
- [ ] Allowlist mechanism for package manager access

---

### US-024: Snapshot manager (`sandbox/snapshot.py`)
**Description:** As a developer, I want container filesystem snapshots so that I can restore a sandbox to a known state after a failed execution.

**Acceptance Criteria:**
- [ ] `src/evolutor/sandbox/snapshot.py` defines `SnapshotManager` with: `create_snapshot()`, `restore_snapshot()`, `list_snapshots()`, `prune_old()`
- [ ] `SnapshotInfo` model defined
- [ ] `prune_old(max_age_hours=24)` removes old snapshots

---

### US-025: Static analysis pipeline (`verification/static.py`)
**Description:** As a developer, I want an automated static analysis pipeline so that every code change is evaluated for lint errors, type errors, security issues, and complexity.

**Acceptance Criteria:**
- [ ] `src/evolutor/verification/static.py` defines `StaticAnalyzer` with async methods: `run_ruff()`, `run_mypy()`, `run_bandit()`, `run_radon()`, `run_all()`
- [ ] All analyzers run as subprocesses, parsing their JSON/structured output
- [ ] `run_all()` runs all analyzers in parallel (`asyncio.gather`)
- [ ] `StaticAnalysisReport` model: lint_errors, type_errors, security_issues, complexity_scores, maintainability_index, passed
- [ ] `SecurityIssue` Pydantic model defined

---

### US-026: Property-based testing (`verification/property.py`)
**Description:** As a developer, I want Hypothesis-based property testing so that functions are automatically tested against generated inputs.

**Acceptance Criteria:**
- [ ] `src/evolutor/verification/property.py` defines `PropertyTester` with: `discover_testable_functions()`, `generate_property_tests()`, `run_property_tests()`
- [ ] Uses Python type hints to generate Hypothesis strategies
- [ ] `TestableFunction` and `ParameterInfo` Pydantic models defined
- [ ] `PropertyTestResult` model defined

---

### US-027: Adversarial testing (`verification/adversarial.py`)
**Description:** As a developer, I want adversarial input testing so that edge cases and boundary conditions are automatically exercised.

**Acceptance Criteria:**
- [ ] `src/evolutor/verification/adversarial.py` defines `AdversarialTester` with: `generate_adversarial_inputs()`, `run_adversarial_suite()`, `fuzz()`
- [ ] `AdversarialCase`, `AdversarialReport`, `FuzzResult` Pydantic models defined
- [ ] Fuzzing runs within sandbox

---

### US-028: Consensus verifier (`verification/consensus.py`)
**Description:** As a developer, I want multi-model consensus verification so that code changes require agreement from multiple LLMs before acceptance.

**Acceptance Criteria:**
- [ ] `src/evolutor/verification/consensus.py` defines `ConsensusVerifier` with: `review_change()`, `vote()`
- [ ] Configurable `threshold` (default 0.7) and `models` list
- [ ] `ConsensusResult` model: approved, votes, agreement_ratio, summary
- [ ] `Vote` Pydantic model defined

---

### US-029: Metrics collector (`verification/metrics.py`)
**Description:** As a developer, I want a metrics collection orchestrator so that before/after snapshots can be taken and fitness vectors computed.

**Acceptance Criteria:**
- [ ] `src/evolutor/verification/metrics.py` defines `MetricsCollector` with: `collect_before()`, `collect_after()`, `run_tests()`, `run_benchmarks()`, `compute_fitness()`, `compute_behavior()`
- [ ] `compute_fitness(metrics)` returns `FitnessVector`
- [ ] `compute_behavior(metrics, parent_metrics)` returns `BehaviorDescriptor`
- [ ] `TestResult` and `BenchmarkResult` Pydantic models defined

---

### US-030: Sandbox + Verification unit tests
**Description:** As a developer, I want unit tests for sandbox and verification so that I can verify correctness with mocked Docker.

**Acceptance Criteria:**
- [ ] `tests/unit/test_sandbox.py`: mock docker client, test container create/execute/destroy lifecycle, resource config generation, snapshot create/restore
- [ ] `tests/unit/test_verification.py`: test static analyzer output parsing (with sample ruff/mypy JSON), metrics computation, fitness vector conversion, consensus voting logic
- [ ] `pytest tests/unit/test_sandbox.py tests/unit/test_verification.py -v` passes

---

### Phase 3 — Memory Layer

---

### US-031: Knowledge graph (`memory/knowledge_graph.py`)
**Description:** As a developer, I want an AST-based knowledge graph so that the system can understand code structure and provide relevant context to agents.

**Acceptance Criteria:**
- [ ] `src/evolutor/memory/knowledge_graph.py` defines `KnowledgeGraph` with: `parse_file()`, `parse_directory()`, `add_node()`, `add_edge()`, `query_by_name()`, `query_by_file()`, `get_dependencies()`, `get_dependents()`, `find_related()`, `to_context_string()`
- [ ] Uses tree-sitter to parse Python files, extracting function/class/import nodes
- [ ] Edges: calls, imports, inherits, contains
- [ ] `to_context_string(nodes, max_tokens)` formats nodes for LLM prompts
- [ ] `python -c "from evolutor.memory.knowledge_graph import KnowledgeGraph; ..."` works

---

### US-032: Repo map (`memory/repo_map.py`)
**Description:** As a developer, I want an Aider-style repo map so that agents can quickly orient themselves in a codebase.

**Acceptance Criteria:**
- [ ] `src/evolutor/memory/repo_map.py` defines `RepoMap` with: `generate_map()`, `get_relevant_context()`, `get_file_summary()`, `rank_files_by_relevance()`
- [ ] Uses PageRank-style ranking to surface most important files
- [ ] `FileContext` Pydantic model defined
- [ ] Map generated as concise text for LLM inclusion

---

### US-033: Git memory (`memory/git_memory.py`)
**Description:** As a developer, I want git history-based memory so that agents can learn from past changes.

**Acceptance Criteria:**
- [ ] `src/evolutor/memory/git_memory.py` defines `GitMemory` with: `get_recent_changes()`, `get_file_history()`, `get_related_files()`, `extract_patterns()`, `summarize_branch()`
- [ ] `get_related_files()` finds files frequently changed together (co-change detection)
- [ ] `ChangeRecord` Pydantic model defined

---

### US-034: Playbooks with ACE pattern (`memory/playbooks.py`)
**Description:** As a developer, I want playbook management with helpful/harmful scoring so that successful coding patterns are retained and failures are pruned.

**Acceptance Criteria:**
- [ ] `src/evolutor/memory/playbooks.py` defines `PlaybookManager` with: `load_all()`, `get_by_language()`, `search()`, `record_outcome()`, `create_delta()`, `get_effective_playbook()`, `prune_harmful()`
- [ ] `record_outcome(playbook_id, helpful: bool)` increments respective counter
- [ ] `prune_harmful(threshold=0.3)` removes playbooks where harmful_count/total > threshold
- [ ] `create_delta(parent_id, changes)` returns new `Playbook` with parent_id set

---

### US-035: Scratchpad (`memory/scratchpad.py`)
**Description:** As a developer, I want a session-scoped scratchpad so that agents can store and retrieve working state during a task.

**Acceptance Criteria:**
- [ ] `src/evolutor/memory/scratchpad.py` defines `Scratchpad` with: `set()`, `get()`, `append()`, `get_recent()`, `summarize()`, `clear()`
- [ ] `append(key, value)` treats key as a list and appends
- [ ] `summarize()` returns a text description of current state
- [ ] History tracks (timestamp, key, action) tuples

---

### US-036: Persistent memory (`memory/persistent.py`)
**Description:** As a developer, I want Mem0-backed persistent memory so that knowledge survives across sessions.

**Acceptance Criteria:**
- [ ] `src/evolutor/memory/persistent.py` defines `PersistentMemory` with: `store()`, `search()`, `get_relevant_context()`, `forget()`
- [ ] Supports both local Mem0 mode and API mode (via `mem0_api_key` config)
- [ ] `get_relevant_context(task)` returns `list[MemoryEntry]`

---

### US-037: Seed playbook files
**Description:** As a developer, I want seed playbook markdown files so that agents have initial coding guidelines.

**Acceptance Criteria:**
- [ ] `playbooks/python.md` contains Python coding conventions and patterns
- [ ] `playbooks/typescript.md` contains TypeScript conventions
- [ ] `playbooks/rust.md` contains Rust conventions
- [ ] `playbooks/general.md` contains language-agnostic patterns (testing, commits, etc.)
- [ ] Each file is loadable by `PlaybookManager`

---

### US-038: Memory unit tests
**Description:** As a developer, I want unit tests for all memory layers so that correctness is verified without real git repos or Mem0.

**Acceptance Criteria:**
- [ ] `tests/unit/test_memory.py` covers: parse sample Python file → verify KG nodes/edges; mock GitOps → verify change records and co-change detection; playbook load/search/record outcome/prune; scratchpad set/get/append/clear lifecycle; mock Mem0 client → verify store/search
- [ ] `pytest tests/unit/test_memory.py -v` passes

---

### Phase 4 — Tools Layer + Orchestrator

---

### US-039: File operations tool (`tools/builtin/file_ops.py`)
**Description:** As a developer, I want a file operations tool with OpenAI-compatible schema so that worker agents can read, write, edit, and search files.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/builtin/file_ops.py` defines `FileOpsTool` with: `read_file()`, `write_file()`, `edit_file()`, `search_files()`, `glob_files()`
- [ ] `get_schema()` returns OpenAI function-calling compatible dict
- [ ] All operations scoped to worktree path

---

### US-040: Bash tool (`tools/builtin/bash.py`)
**Description:** As a developer, I want a sandboxed bash execution tool so that worker agents can run shell commands in isolated containers.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/builtin/bash.py` defines `BashTool` with: `execute(command, timeout)`, `get_schema()`
- [ ] Execution delegated to `SandboxManager`
- [ ] Timeout enforced (default 60s)

---

### US-041: Git tool (`tools/builtin/git_tool.py`)
**Description:** As a developer, I want git operations as tool calls so that worker agents can commit their changes.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/builtin/git_tool.py` defines `GitTool` with: `status()`, `diff()`, `commit()`, `create_branch()`, `log()`, `get_schema()`
- [ ] All methods return strings suitable for inclusion in LLM context

---

### US-042: Web tool (`tools/builtin/web.py`)
**Description:** As a developer, I want a web search and fetch tool so that worker agents can look up documentation and packages.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/builtin/web.py` defines `WebTool` with: `search()`, `fetch()`, `get_schema()`
- [ ] Uses httpx for fetching
- [ ] `SearchResult` Pydantic model defined

---

### US-043: MCP registry (`tools/mcp/registry.py`)
**Description:** As a developer, I want an MCP tool registry so that external tool servers can be discovered and called uniformly.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/mcp/registry.py` defines `MCPRegistry` with: `register_server()`, `discover_tools()`, `call_tool()`, `list_all_tools()`
- [ ] `MCPServer`, `MCPServerConfig`, `ToolSchema` Pydantic models defined
- [ ] `register_server` is async

---

### US-044: Tool search (`tools/mcp/tool_search.py`)
**Description:** As a developer, I want semantic tool search across all three tiers so that agents can find the right tool for any task.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/mcp/tool_search.py` defines `ToolSearch` with: `search()`, `get_tool_for_task()`
- [ ] Searches across built-in tools, MCP tools, and ToolForge tools
- [ ] `ToolMatch` Pydantic model: tool_name, tier, relevance_score, schema

---

### US-045: ToolForge (creator/verifier/store)
**Description:** As a developer, I want a ToolForge system so that agents can create, verify, and persist new tools when built-in tools are insufficient.

**Acceptance Criteria:**
- [ ] `src/evolutor/tools/forge/creator.py` defines `ToolCreator` with `create_tool(need_description)` that uses LLM to generate tool code
- [ ] `src/evolutor/tools/forge/verifier.py` defines `ToolVerifier` with `verify(tool_code)` that runs the tool in sandbox and checks safety
- [ ] `src/evolutor/tools/forge/store.py` defines `ToolStore` with: `save()`, `load()`, `list_tools()`, `get_version_history()`
- [ ] Generated tools are stored versioned in `tools/forge/created/`

---

### US-046: Orchestrator state model (`orchestrator/models.py`)
**Description:** As a developer, I want a LangGraph state TypedDict so that the orchestrator graph can pass typed state between nodes.

**Acceptance Criteria:**
- [ ] `src/evolutor/orchestrator/models.py` defines `OrchestratorState` TypedDict with fields: task, plan, current_subtask_index, results, context, iteration, max_iterations, messages, should_continue, final_result

---

### US-047: Planner node (`orchestrator/planner.py`)
**Description:** As a developer, I want a LangGraph planner node so that high-level tasks are automatically decomposed into subtasks.

**Acceptance Criteria:**
- [ ] `src/evolutor/orchestrator/planner.py` defines `PlannerNode` as async callable
- [ ] `__call__(state)` calls LLM with repo map + memory context, returns state with `plan` populated
- [ ] `_build_prompt(task, context)` and `_parse_plan(response)` helper methods
- [ ] Subtasks returned as `list[Task]`

---

### US-048: Worker node (`orchestrator/worker.py`)
**Description:** As a developer, I want a LangGraph worker node so that subtasks are executed using tools in isolated sandboxes.

**Acceptance Criteria:**
- [ ] `src/evolutor/orchestrator/worker.py` defines `WorkerNode` as async callable
- [ ] `__call__(state)` executes current subtask (by index) in worktree+sandbox
- [ ] `_execute_with_tools(task, tools, sandbox)` implements the tool-calling loop
- [ ] Returns state with updated `results`

---

### US-049: Critic node + Orchestrator engine (`orchestrator/critic.py`, `orchestrator/engine.py`)
**Description:** As a developer, I want a critic node and assembled LangGraph engine so that the full planner→worker→critic→evaluator pipeline is wired together.

**Acceptance Criteria:**
- [ ] `critic.py` defines `CriticNode` that reviews diffs and votes accept/revise/reject
- [ ] `engine.py` defines `OrchestratorEngine` with `_build_graph()` assembling `StateGraph`
- [ ] Graph edges: START→planner→worker→critic, with conditional routing after critic (accept→evaluator, revise→worker, reject→planner)
- [ ] Conditional routing after evaluator: next_subtask→worker, done→END, rollback→planner
- [ ] `run(task)` async method returns `TaskResult`

---

### US-050: Scheduler + parallelism (`orchestrator/scheduler.py`, `orchestrator/parallelism.py`)
**Description:** As a developer, I want Redis Streams task queuing and parallel worker execution so that multiple subtasks run concurrently.

**Acceptance Criteria:**
- [ ] `scheduler.py` defines task queue backed by Redis Streams: `enqueue()`, `dequeue()`, `acknowledge()`, `get_pending()`
- [ ] `parallelism.py` defines parallel worker runner with asyncio semaphore limiting concurrency to `OrchestratorConfig.max_parallel_workers`
- [ ] Graceful handling of worker failures (result still recorded, not crashed)

---

### Phase 5 — Evolution Engine

---

### US-051: MAP-Elites archive (`evolution/archive.py`)
**Description:** As a developer, I want a MAP-Elites archive using pyribs so that diverse high-quality code mutations are retained across the behavior space.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/archive.py` defines `EvolutionArchive` wrapping pyribs `GridArchive`
- [ ] Methods: `add(entry)`, `sample_elites(n)`, `sample_diverse(n)`, `get_stats()`, `coverage()`
- [ ] `ArchiveEntry` model: commit_sha, fitness, behavior, mutation_type, parent_sha, timestamp, files_changed
- [ ] `add()` returns `True` if entry became an elite
- [ ] `ArchiveStats` model defined

---

### US-052: Fitness evaluator with NSGA-III (`evolution/fitness.py`)
**Description:** As a developer, I want multi-objective fitness evaluation using pymoo NSGA-III so that the 4-objective Pareto frontier is maintained.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/fitness.py` defines `FitnessEvaluator` with pymoo NSGA3 configured for 4 objectives
- [ ] Methods: `evaluate()`, `compare()`, `select_survivors()`, `rank_population()`
- [ ] `compare(a, b)` returns 1 (a dominates), -1 (b dominates), 0 (non-dominated)
- [ ] `rank_population()` returns list of Pareto fronts (list of lists)

---

### US-053: Mutation operator (`evolution/mutator.py`)
**Description:** As a developer, I want LLM-guided mutation operators so that the evolution engine can generate diverse code variants.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/mutator.py` defines `Mutator` with: `generate_mutation()`, `crossover()`, `select_mutation_type()`
- [ ] 6 mutation types: refactor, optimize, harden, simplify, extend, test_improve
- [ ] `select_mutation_type(metrics)` picks type based on weakest metric dimension
- [ ] `crossover(parent_a, parent_b)` combines changes from two elite archive entries
- [ ] `Mutation` model: id, mutation_type, target_file, original_code, mutated_code, description, parent_sha

---

### US-054: Main evolution loop (`evolution/loop.py`)
**Description:** As a developer, I want the main ask-tell evolution loop so that code improvements are generated, evaluated, and accumulated automatically.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/loop.py` defines `EvolutionLoop` with `run(generations)` async method
- [ ] Loop: generate candidates → evaluate in parallel worktrees+sandboxes → update archive → plateau check → island migration
- [ ] Migration every `evolution.migration_interval` generations
- [ ] `EvolutionReport` model returned: generations_run, archive_coverage, best_fitness, improvements_accepted

---

### US-055: Plateau detector (`evolution/plateau.py`)
**Description:** As a developer, I want ruptures-based plateau detection so that the evolution engine diversifies when fitness stagnates.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/plateau.py` defines `PlateauDetector` with: `record(fitness)`, `detect()`, `suggest_action()`
- [ ] Uses ruptures PELT algorithm on fitness history sliding window
- [ ] Returns `False` if fewer than `window_size` samples recorded
- [ ] `suggest_action()` returns string describing recommended diversification strategy

---

### US-056: Canary deployer (`evolution/canary.py`)
**Description:** As a developer, I want canary deployment of evolved code so that mutations are validated on a subset before full adoption.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/canary.py` defines `CanaryDeployer` with: `deploy_canary()`, `promote()`, `rollback_canary()`, `monitor()`
- [ ] `CanaryResult`, `CanaryMetrics` Pydantic models defined
- [ ] `monitor(canary_id, duration_seconds)` collects metrics during canary period
- [ ] Promotion only allowed if canary metrics meet threshold

---

### US-057: Knowledge extraction (`evolution/knowledge.py`)
**Description:** As a developer, I want evolution knowledge extraction so that successful mutation patterns are fed back into playbooks.

**Acceptance Criteria:**
- [ ] `src/evolutor/evolution/knowledge.py` defines `EvolutionKnowledge` with: `extract_successful_patterns()`, `extract_failure_patterns()`, `update_playbooks()`, `generate_meta_insights()`
- [ ] `update_playbooks()` calls `PlaybookManager.create_delta()` with extracted patterns
- [ ] `generate_meta_insights()` returns string summary for planner context

---

### US-058: Agent prompt templates
**Description:** As a developer, I want versioned Jinja2-templated prompt files so that agent behavior can be improved by evolution.

**Acceptance Criteria:**
- [ ] `prompts/planner.md`: system prompt for task decomposition with repo map and memory placeholders
- [ ] `prompts/worker.md`: system prompt for code implementation with playbook, tool schemas, and task context placeholders
- [ ] `prompts/critic.md`: system prompt for code review with invariants and quality standards
- [ ] `prompts/meta_improver.md`: system prompt for self-improvement with evolution history and archive stats
- [ ] All prompts use `{{ variable_name }}` Jinja2 syntax for placeholders

---

### US-059: Evolution unit tests
**Description:** As a developer, I want unit tests for the evolution engine so that archive, fitness, mutator, and plateau detection are verified.

**Acceptance Criteria:**
- [ ] `tests/unit/test_evolution.py` covers: archive add/select/coverage stats; Pareto dominance comparison; NSGA-III survivor selection; mutation type selection heuristic; plateau detector on synthetic fitness series
- [ ] `pytest tests/unit/test_evolution.py -v` passes

---

### Phase 6 — CLI/TUI + Integration

---

### US-060: Config manager (`cli/config.py`)
**Description:** As a developer, I want layered configuration loading so that settings can be overridden at every level (defaults, project, env, CLI flags).

**Acceptance Criteria:**
- [ ] `src/evolutor/cli/config.py` defines `ConfigManager` with: `load()`, `save()`, `merge_cli_overrides()`, `get_default_config_path()`
- [ ] Load order: `configs/default.toml` → `.evolutor.toml` in project root → env vars → CLI flags
- [ ] Returns `EvolutorConfig` instance

---

### US-061: CLI commands (`cli/app.py`)
**Description:** As a user, I want a Typer CLI with all Evolutor commands so that I can interact with the framework from the terminal.

**Acceptance Criteria:**
- [ ] `src/evolutor/cli/app.py` defines Typer app with commands: `init`, `task`, `evolve`, `status`, `rollback`, `history`, `chat`, `tui`
- [ ] `evolutor --help` shows all commands
- [ ] `evolutor init <path>` creates `.evolutor.toml` in target directory
- [ ] `evolutor task "<description>"` submits a task to the orchestrator
- [ ] `evolutor evolve --generations N` runs the evolution loop
- [ ] `evolutor status` shows active tasks, evolution stats, memory usage

---

### US-062: Chat REPL (`cli/chat.py`)
**Description:** As a user, I want an interactive chat interface so that I can issue natural language instructions to the orchestrator.

**Acceptance Criteria:**
- [ ] `src/evolutor/cli/chat.py` defines `ChatInterface` with async `run()` method
- [ ] REPL loop: Rich prompt → parse intent → dispatch to orchestrator → display result
- [ ] Exits on "exit" or "quit" input
- [ ] Output rendered as Markdown using Rich

---

### US-063: Textual TUI (`cli/tui.py`)
**Description:** As a user, I want a full-screen TUI dashboard so that I can monitor all system activity in real time.

**Acceptance Criteria:**
- [ ] `src/evolutor/cli/tui.py` defines `EvolutorTUI(App)` using Textual
- [ ] Panels: `TaskPanel`, `EvolutionPanel`, `LogPanel`, `MemoryPanel`
- [ ] Header and Footer with key bindings shown
- [ ] Panels update reactively as state changes

---

### US-064: Docker infrastructure
**Description:** As a developer, I want Dockerfile and docker-compose.yml so that the full system can be deployed with a single command.

**Acceptance Criteria:**
- [ ] `Dockerfile` is multi-stage: base Python image → install deps → copy source → set entrypoint to `evolutor`
- [ ] `docker-compose.yml` defines services: evolutor (main), redis (task queue), sandbox (worker template), chromadb (vector store)
- [ ] `docker compose up` starts all services

---

### US-065: Convenience scripts
**Description:** As a developer, I want shell scripts for common operations so that benchmarking and self-improvement are easy to trigger.

**Acceptance Criteria:**
- [ ] `scripts/benchmark.sh` runs `pytest tests/benchmarks/` and saves results
- [ ] `scripts/self_improve.sh` kicks off `evolutor evolve` with production defaults
- [ ] `scripts/setup_sandbox.sh` builds Docker images, configures network policies
- [ ] All scripts are executable (`chmod +x`)

---

### US-066: End-to-end integration test
**Description:** As a developer, I want an end-to-end integration test so that the full pipeline is verified from task submission to git commit.

**Acceptance Criteria:**
- [ ] `tests/integration/test_end_to_end.py` covers: init temp project → submit task ("add type hints to all functions") → verify orchestrator plans → worker executes → critic reviews → kernel evaluator accepts → git history shows commits → mini evolution loop (2 generations) → archive has entries
- [ ] Test uses mocked LLM responses (no real API calls)
- [ ] `pytest tests/integration/test_end_to_end.py -v` passes

---

### US-067: CLI integration tests
**Description:** As a developer, I want CLI integration tests using Typer's test runner so that all commands are verified.

**Acceptance Criteria:**
- [ ] `tests/integration/test_cli.py` uses `typer.testing.CliRunner`
- [ ] Tests: `init`, `status`, `history` commands at minimum
- [ ] All tested commands return `exit_code == 0`
- [ ] `pytest tests/integration/test_cli.py -v` passes

---

### Phase 7 — Hardening + Self-Bootstrap

---

### US-068: Documentation
**Description:** As a developer, I want comprehensive documentation so that contributors can understand and extend the system.

**Acceptance Criteria:**
- [ ] `docs/architecture.md` contains system architecture description with Mermaid diagrams
- [ ] `docs/getting-started.md` covers: installation, first task, first evolution run
- [ ] `docs/configuration.md` documents all `EvolutorConfig` options with examples

---

### US-069: Performance benchmarks
**Description:** As a developer, I want pytest-benchmark suites so that performance regressions are detected automatically.

**Acceptance Criteria:**
- [ ] `tests/benchmarks/bench_evolution.py` benchmarks: mutation generation speed, archive add/sample ops, fitness evaluation throughput
- [ ] `tests/benchmarks/bench_memory.py` benchmarks: knowledge graph parse speed, search latency, repo map generation time
- [ ] `pytest tests/benchmarks/ --benchmark-only` runs without error

---

### US-070: Error handling and resilience audit
**Description:** As a developer, I want comprehensive error handling across all modules so that the system degrades gracefully under failures.

**Acceptance Criteria:**
- [ ] Every async function has try/except with `structlog` error logging
- [ ] All sandbox/worktree operations use context managers for cleanup
- [ ] Graceful degradation: if Redis unavailable → fall back to in-memory queue; if Docker unavailable → run in-process
- [ ] All timeouts are explicit and bounded (no unbounded `await`)

---

### US-071: Finalize kernel invariants
**Description:** As a developer, I want comprehensive built-in invariants so that the kernel enforces all critical safety constraints.

**Acceptance Criteria:**
- [ ] `kernel/invariants.py` includes: tests_must_not_regress (test count cannot decrease), coverage_must_not_regress (≤1% decrease allowed), no_new_security_issues (bandit count cannot increase), kernel_immutability (SHA of kernel files must match), type_check_must_pass (mypy returns 0 errors), no_deleted_public_api (no public signature removal)
- [ ] All invariants registered in default `InvariantRegistry`

---

### US-072: Self-bootstrap validation
**Description:** As a developer, I want to run Evolutor on its own codebase to validate the full pipeline end-to-end.

**Acceptance Criteria:**
- [ ] `evolutor evolve --generations 5 --target src/evolutor/` runs without crash
- [ ] Kernel correctly gates changes (invariant violations are rejected)
- [ ] Rollback works when evolution breaks something
- [ ] Findings are documented in `docs/self-bootstrap-results.md`

---

### US-073: CI/CD configuration
**Description:** As a developer, I want GitHub Actions and pre-commit hooks so that code quality is enforced automatically.

**Acceptance Criteria:**
- [ ] `.github/workflows/ci.yml` runs: lint (ruff) → typecheck (mypy) → test (pytest) → benchmark on every PR
- [ ] `.pre-commit-config.yaml` configures: ruff, mypy, trailing whitespace, EOF newline
- [ ] CI workflow uses Python 3.11

---

### US-074: Comprehensive scenario tests
**Description:** As a developer, I want scenario-based integration tests covering all major system capabilities so that regressions are caught before release.

**Acceptance Criteria:**
- [ ] `tests/integration/` includes scenario tests for: multi-file task change, plateau detection + diversification, concurrent parallel workers, rollback after failed evolution, playbook evolution after task completions, ToolForge creating a tool and using it in a subsequent task
- [ ] All scenario tests pass with mocked LLM and mocked Docker
- [ ] `pytest tests/ -v --timeout=300 -x` passes

---

## Functional Requirements

- FR-1: The system must install via `pip install -e ".[dev]"` with Python 3.11+
- FR-2: All cross-module data must use Pydantic v2 models from `src/evolutor/types/`
- FR-3: All I/O-bound operations must be async; CPU-bound work uses `asyncio.to_thread`
- FR-4: Every module must use `structlog` with bound context (task_id, agent_role, phase)
- FR-5: The kernel evaluator must gate 100% of code changes before acceptance
- FR-6: The sandbox must enforce memory (512MB), CPU (1 core), and PID (256) limits
- FR-7: Evolution must maintain a MAP-Elites archive across the (complexity, novelty) behavior space
- FR-8: The CLI must provide `init`, `task`, `evolve`, `status`, `rollback`, `history`, `chat`, `tui` commands
- FR-9: Every phase must end with `pytest tests/` passing and `ruff check src/` clean
- FR-10: The framework must be able to run `evolutor evolve` targeting its own source code

## Non-Goals

- No GUI (web or desktop) — terminal only
- No cloud deployment infrastructure beyond Docker Compose
- No multi-language support beyond Python for the framework source itself (evolved projects may be any language)
- No real-time collaboration features
- No user authentication / access control
- No paid cloud services required (all defaults must work locally)

## Technical Considerations

- **Build system:** hatchling with `src/` layout
- **Python version:** 3.11+ (uses `match` statement, `tomllib`, `asyncio.TaskGroup`)
- **pygit2 1.19.1** requires libgit2 system library
- **tree-sitter 0.25.2** with `tree-sitter-languages` for multi-language support
- **pyribs** GridArchive solution_dim must accommodate commit SHA storage strategy
- **pymoo 0.6.1.6** NSGA-III reference directions via `get_reference_directions("das-dennis", 4, n_partitions=12)`
- **ruptures 1.1.10** PELT with RBF model for plateau detection
- **LangGraph** StateGraph with TypedDict state and conditional edges
- **Redis** Streams for distributed task queue (fall back to asyncio.Queue if unavailable)

## Success Metrics

- `pip install -e ".[dev]"` completes in under 3 minutes
- `pytest tests/` passes with 0 failures across all 74 implementation tasks
- `ruff check src/` reports 0 errors
- `mypy src/evolutor/types/` passes after Phase 0
- `mypy src/ --strict` passes after Phase 7
- `evolutor evolve --generations 3 --dry-run` completes without crashing
- Evolution archive reaches >10% coverage after 10 generations on a small target project

## Open Questions

- Should the consensus verifier use Anthropic API directly or route through the orchestrator's model config?
- Should chromadb be required or optional (falling back to in-memory vector search)?
- For self-bootstrap (Phase 7), should we target a subset of modules or the full `src/evolutor/`?
