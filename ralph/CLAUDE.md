# Evolutor — Autonomous Implementation Agent

You are building the **Evolutor** framework. Working directory: `/home/mekashirskiy/evolutor`

---

## MANDATORY LOOP — follow these steps in order, every single iteration

### STEP 1 — Find your next story (run this bash command NOW)

```bash
jq -r '[.userStories[] | select(.passes == false)] | .[0] | "\(.id): \(.title)"' ralph/prd.json
```

That prints the next incomplete story. If it prints `null` then all stories are done — output `<promise>COMPLETE</promise>` and stop.

### STEP 2 — Implement the story

Satisfy every acceptance criterion listed in the Story Reference section below.

### STEP 3 — Mark it DONE in prd.json (run immediately after implementing)

```bash
# Replace US-XXX with the actual story ID
jq '(.userStories[] | select(.id == "US-XXX")).passes |= true' ralph/prd.json > ralph/prd.json.tmp && mv ralph/prd.json.tmp ralph/prd.json
echo "DONE: US-XXX: <short title> ($(date '+%Y-%m-%d %H:%M'))" >> ralph/progress.txt
```

### STEP 4 — Commit and push (run immediately after marking DONE)

```bash
cd /home/mekashirskiy/evolutor
git add -A
git commit -m "feat: US-XXX: <short title>"
git push -u origin HEAD
```

If push fails, reconfigure remote:
```bash
git remote set-url origin "https://<GH_PAT>@github.com/mariklolik/evolutor.git"
git push -u origin HEAD
```
Fallback classic PAT: see environment variable `GH_PAT_CLASSIC`

### STEP 6 — Continue to the next story

Go back to STEP 1 and do the next story. Keep going until you have done as many stories as possible.

### STEP 7 — When ALL 74 stories are DONE

Output this exact string: `<promise>COMPLETE</promise>`

---

## Phase branches — create ONCE at the start of each phase

```bash
# Phase 0 (US-001 to US-009)
git checkout -b phase-0-scaffolding 2>/dev/null || true && git push -u origin phase-0-scaffolding 2>/dev/null || true

# Phase 1 (US-010 to US-020) — only after US-009 done
git checkout -b phase-1-git-kernel && git push -u origin phase-1-git-kernel

# Phase 2 (US-021 to US-030)
git checkout -b phase-2-sandbox-verification && git push -u origin phase-2-sandbox-verification

# Phase 3 (US-031 to US-038)
git checkout -b phase-3-memory && git push -u origin phase-3-memory

# Phase 4 (US-039 to US-050)
git checkout -b phase-4-tools-orchestrator && git push -u origin phase-4-tools-orchestrator

# Phase 5 (US-051 to US-059)
git checkout -b phase-5-evolution && git push -u origin phase-5-evolution

# Phase 6 (US-060 to US-067)
git checkout -b phase-6-cli-tui && git push -u origin phase-6-cli-tui

# Phase 7 (US-068 to US-074)
git checkout -b phase-7-hardening && git push -u origin phase-7-hardening
```

---

## Story Reference (acceptance criteria per story)

### Phase 0 — Scaffolding + Types

**US-001 — pyproject.toml**
- `pyproject.toml` at repo root: name=evolutor, version=0.1.0, requires-python=">=3.11", build backend hatchling
- Deps: pydantic>=2, structlog, httpx, typer[all], rich, pygit2, dulwich, githubkit, mem0ai, chromadb, networkx, tree-sitter, tree-sitter-languages, pyribs, pymoo, ruptures, hypothesis, ruff, mypy, bandit, radon, coverage, pytest-benchmark, docker, langgraph, redis
- Dev extras: pytest, pytest-asyncio, pytest-cov, ruff, mypy, pre-commit
- Entry point: `evolutor = "evolutor.cli.app:main"`
- `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` sections
- Run: `pip install -e ".[dev]"` and confirm success

**US-002 — Package skeleton**
- Directories + `__init__.py`: src/evolutor/{cli,kernel,orchestrator,memory,evolution,verification,git,sandbox,tools/builtin,tools/mcp,tools/forge,types}/
- Empty test dirs: tests/unit/, tests/integration/, tests/benchmarks/
- Empty support dirs: configs/, playbooks/, prompts/, scripts/, docs/
- `pytest tests/` must collect 0 tests, 0 failures

**US-003 — Entry points**
- `src/evolutor/__init__.py`: `__version__ = "0.1.0"`, configure structlog
- `src/evolutor/__main__.py`: `from evolutor.cli.app import main; main()`

**US-004 — Config types**
- `src/evolutor/types/config.py`: SandboxConfig, GitConfig, MemoryConfig, EvolutionConfig, OrchestratorConfig, EvolutorConfig (all Pydantic v2, all fields have defaults)

**US-005 — Task types**
- `src/evolutor/types/task.py`: TaskStatus enum, TaskPriority enum, Task model, TaskResult model
- Verify: `python -c "from evolutor.types.task import Task; print(Task(title='t', description='d').model_dump_json())"`

**US-006 — Agent types**
- `src/evolutor/types/agent.py`: AgentRole enum (planner/worker/critic/meta_improver), AgentState, AgentMessage

**US-007 — Metrics types**
- `src/evolutor/types/metrics.py`: CodeMetrics, FitnessVector (with `to_minimize() -> list[float]`), BehaviorDescriptor

**US-008 — Memory types**
- `src/evolutor/types/memory.py`: MemoryEntry, KnowledgeNode, Playbook (with helpful_count, harmful_count)

**US-009 — Config files + boilerplate**
- `configs/default.toml`, `configs/models.toml`, `configs/sandbox.toml`
- `README.md`, `LICENSE` (MIT), `AGENTS.md`, `EVOLUTOR.md`

---

### Phase 1 — Git Layer + Kernel Core

**US-010 — git/ops.py**
- `GitOps` class using pygit2: current_branch, create_branch, checkout, stage_files, commit, get_diff, get_log, get_file_at_ref, merge, cherry_pick

**US-011 — git/worktree.py**
- `WorktreeManager`: create, remove, list_active, get_worktree_repo, cleanup_stale
- `WorktreeInfo` Pydantic model

**US-012 — git/branching.py**
- `BranchStrategy`: generate_branch_name, parse_branch_name, get_evolution_branches, get_merge_candidates
- Prefixes: feat/, fix/, evo/, exp/

**US-013 — git/conflict.py**
- `ConflictResolver`: detect_conflicts, auto_resolve (ours/theirs strategy), generate_resolution_prompt
- ConflictInfo, Resolution models

**US-014 — git/audit.py**
- `AuditLog` using `refs/notes/evolutor` git notes
- record_action, get_history, get_actions_for_commit
- AuditEntry model

**US-015 — kernel/invariants.py**
- `InvariantRegistry`, `Invariant`, `InvariantReport`, `InvariantViolation`
- Built-ins: tests_must_pass, no_security_regressions, kernel_immutable, config_valid

**US-016 — kernel/evaluator.py**
- `Evaluator` with async `evaluate()`, `compute_delta()`, `should_accept()`
- `EvaluationResult` model: accepted, reason, invariant_report, metrics_delta, confidence

**US-017 — kernel/rollback.py**
- `RollbackManager`: create_savepoint, rollback_to, rollback_branch, list_savepoints
- `Savepoint` model

**US-018 — kernel/safety.py**
- `SafetyBoundary`: check_file_access, check_command, validate_diff, get_risk_level
- PROTECTED_PATHS: src/evolutor/kernel/, pyproject.toml, .git/
- `RiskLevel` enum: safe/moderate/high/critical

**US-019 — kernel/trust.py**
- `TrustScorer`: compute_trust, should_require_review, update_trust
- Trust levels L1-L5

**US-020 — Unit tests: git + kernel**
- `tests/unit/test_git_ops.py`: temp git repo fixture, test all GitOps methods, WorktreeManager, BranchStrategy, AuditLog
- `tests/unit/test_kernel.py`: InvariantRegistry, Evaluator, RollbackManager, SafetyBoundary, TrustScorer
- `pytest tests/unit/test_git_ops.py tests/unit/test_kernel.py -v` must pass

---

### Phase 2 — Sandbox + Verification

**US-021 — sandbox/docker.py**
- `SandboxManager` (async): create, execute, destroy, list_active, cleanup_all
- `SandboxInstance`, `ExecutionResult` models

**US-022 — sandbox/resource.py**
- `ResourceLimiter`: get_container_config, check_usage
- `ResourceUsage` model

**US-023 — sandbox/network.py**
- `NetworkPolicy`: create_isolated_network, apply_policy, block_all, cleanup_networks

**US-024 — sandbox/snapshot.py**
- `SnapshotManager`: create_snapshot, restore_snapshot, list_snapshots, prune_old

**US-025 — verification/static.py**
- `StaticAnalyzer` (async): run_ruff, run_mypy, run_bandit, run_radon, run_all (parallel)
- `StaticAnalysisReport`, `SecurityIssue` models

**US-026 — verification/property.py**
- `PropertyTester`: discover_testable_functions, generate_property_tests, run_property_tests
- `TestableFunction`, `PropertyTestResult` models

**US-027 — verification/adversarial.py**
- `AdversarialTester`: generate_adversarial_inputs, run_adversarial_suite, fuzz
- `AdversarialCase`, `AdversarialReport`, `FuzzResult` models

**US-028 — verification/consensus.py**
- `ConsensusVerifier`: review_change, vote (threshold=0.7)
- `ConsensusResult`, `Vote` models

**US-029 — verification/metrics.py**
- `MetricsCollector`: collect_before, collect_after, run_tests, run_benchmarks, compute_fitness, compute_behavior
- `TestResult`, `BenchmarkResult` models

**US-030 — Unit tests: sandbox + verification**
- `tests/unit/test_sandbox.py`: mock docker, test lifecycle, resource config, snapshots
- `tests/unit/test_verification.py`: static analyzer output parsing, metrics/fitness, consensus voting
- Both must pass with `pytest`

---

### Phase 3 — Memory Layer

**US-031 — memory/knowledge_graph.py**
- `KnowledgeGraph`: parse_file (tree-sitter), add_node, add_edge, query_by_name, query_by_file, get_dependencies, get_dependents, find_related, to_context_string
- Edges: calls, imports, inherits, contains

**US-032 — memory/repo_map.py**
- `RepoMap`: generate_map, get_relevant_context, get_file_summary, rank_files_by_relevance
- `FileContext` model

**US-033 — memory/git_memory.py**
- `GitMemory`: get_recent_changes, get_file_history, get_related_files, extract_patterns, summarize_branch
- `ChangeRecord` model

**US-034 — memory/playbooks.py**
- `PlaybookManager`: load_all, get_by_language, search, record_outcome, create_delta, get_effective_playbook, prune_harmful

**US-035 — memory/scratchpad.py**
- `Scratchpad`: set, get, append, get_recent, summarize, clear

**US-036 — memory/persistent.py**
- `PersistentMemory` (Mem0): store, search, get_relevant_context, forget
- Supports local mode and API mode

**US-037 — Seed playbooks**
- `playbooks/python.md`, `playbooks/typescript.md`, `playbooks/rust.md`, `playbooks/general.md`

**US-038 — Unit tests: memory**
- `tests/unit/test_memory.py`: KG parse, git memory, playbooks, scratchpad, persistent (mocked)
- Must pass with `pytest`

---

### Phase 4 — Tools + Orchestrator

**US-039 — tools/builtin/file_ops.py**
- `FileOpsTool`: read_file, write_file, edit_file, search_files, glob_files, get_schema()

**US-040 — tools/builtin/bash.py**
- `BashTool`: execute(command, timeout=60), get_schema() — uses SandboxManager

**US-041 — tools/builtin/git_tool.py**
- `GitTool`: status, diff, commit, create_branch, log, get_schema()

**US-042 — tools/builtin/web.py**
- `WebTool`: search, fetch (httpx), get_schema()
- `SearchResult` model

**US-043 — tools/mcp/registry.py**
- `MCPRegistry`: register_server, discover_tools, call_tool, list_all_tools
- `MCPServer`, `MCPServerConfig`, `ToolSchema` models

**US-044 — tools/mcp/tool_search.py**
- `ToolSearch`: search, get_tool_for_task
- `ToolMatch` model

**US-045 — tools/forge/ (creator, verifier, store)**
- `ToolCreator`: create_tool(need_description) → LLM generates code
- `ToolVerifier`: verify(tool_code) → runs in sandbox
- `ToolStore`: save, load, list_tools, get_version_history

**US-046 — orchestrator/models.py**
- `OrchestratorState` TypedDict: task, plan, current_subtask_index, results, context, iteration, max_iterations, messages, should_continue, final_result

**US-047 — orchestrator/planner.py**
- `PlannerNode` (async callable): decomposes Task into list[Task] subtasks using LLM

**US-048 — orchestrator/worker.py**
- `WorkerNode` (async callable): executes current subtask using tools in sandbox

**US-049 — orchestrator/critic.py + engine.py**
- `CriticNode`: accept/revise/reject decisions
- `OrchestratorEngine`: LangGraph StateGraph with full routing (planner→worker→critic→evaluator)

**US-050 — orchestrator/scheduler.py + parallelism.py**
- Redis Streams task queue with enqueue/dequeue/acknowledge
- Parallel worker runner with asyncio semaphore

---

### Phase 5 — Evolution Engine

**US-051 — evolution/archive.py**
- `EvolutionArchive` (pyribs GridArchive): add, sample_elites, sample_diverse, get_stats, coverage
- `ArchiveEntry`, `ArchiveStats` models

**US-052 — evolution/fitness.py**
- `FitnessEvaluator` (pymoo NSGA-III, 4 objectives): evaluate, compare (Pareto), select_survivors, rank_population

**US-053 — evolution/mutator.py**
- `Mutator`: generate_mutation, crossover, select_mutation_type (heuristic)
- 6 types: refactor, optimize, harden, simplify, extend, test_improve
- `Mutation` model

**US-054 — evolution/loop.py**
- `EvolutionLoop.run(generations)`: ask→evaluate→tell→plateau check→migrate
- `EvolutionReport` model

**US-055 — evolution/plateau.py**
- `PlateauDetector` (ruptures PELT): record, detect, suggest_action

**US-056 — evolution/canary.py**
- `CanaryDeployer`: deploy_canary, promote, rollback_canary, monitor
- `CanaryResult`, `CanaryMetrics` models

**US-057 — evolution/knowledge.py**
- `EvolutionKnowledge`: extract_successful_patterns, extract_failure_patterns, update_playbooks, generate_meta_insights

**US-058 — Agent prompt templates**
- `prompts/planner.md`, `prompts/worker.md`, `prompts/critic.md`, `prompts/meta_improver.md`
- Jinja2 `{{ variable }}` placeholders

**US-059 — Unit tests: evolution**
- `tests/unit/test_evolution.py`: archive, Pareto dominance, mutation heuristic, plateau detector
- Must pass with `pytest`

---

### Phase 6 — CLI/TUI + Integration

**US-060 — cli/config.py**
- `ConfigManager`: load (toml→env→CLI), save, merge_cli_overrides, get_default_config_path

**US-061 — cli/app.py**
- Typer app: init, task, evolve, status, rollback, history, chat, tui commands
- `evolutor --help` shows all commands

**US-062 — cli/chat.py**
- `ChatInterface`: async REPL using Rich (read→dispatch→display Markdown)

**US-063 — cli/tui.py**
- `EvolutorTUI(App)` using Textual: TaskPanel, EvolutionPanel, LogPanel, MemoryPanel

**US-064 — Docker infra**
- `Dockerfile` (multi-stage), `docker-compose.yml` (evolutor + redis + sandbox + chromadb)

**US-065 — Scripts**
- `scripts/benchmark.sh`, `scripts/self_improve.sh`, `scripts/setup_sandbox.sh` (all chmod +x)

**US-066 — E2E integration test**
- `tests/integration/test_end_to_end.py`: full pipeline with mocked LLM

**US-067 — CLI integration tests**
- `tests/integration/test_cli.py`: Typer CliRunner, init/status/history pass exit_code==0

---

### Phase 7 — Hardening + Self-Bootstrap

**US-068 — Documentation**
- `docs/architecture.md` (Mermaid diagrams), `docs/getting-started.md`, `docs/configuration.md`

**US-069 — Benchmarks**
- `tests/benchmarks/bench_evolution.py`, `tests/benchmarks/bench_memory.py`

**US-070 — Error handling audit**
- Every async function: try/except with structlog
- Context managers for sandbox/worktree cleanup
- Graceful degradation (Redis→asyncio.Queue, Docker→in-process)

**US-071 — Finalize invariants**
- Add to kernel/invariants.py: tests_must_not_regress, coverage_floor, no_new_security_issues, kernel_immutability (SHA check), type_check_must_pass, no_deleted_public_api

**US-072 — Self-bootstrap validation**
- `evolutor evolve --generations 5 --target src/evolutor/` runs
- Document findings in `docs/self-bootstrap-results.md`

**US-073 — CI/CD**
- `.github/workflows/ci.yml`: lint→typecheck→test→benchmark on PR
- `.pre-commit-config.yaml`: ruff, mypy, trailing-whitespace, end-of-file-fixer

**US-074 — Scenario tests**
- `tests/integration/` scenario tests: multi-file task, plateau+diversify, concurrent workers, rollback, playbook evolution, ToolForge create+use
- All pass with mocked LLM + mocked Docker

---

## Rules

- Python 3.11+ only; `src/evolutor/` layout; hatchling build
- Pydantic v2 for all models; async for all I/O; structlog for logging
- No over-engineering — minimal implementation that satisfies acceptance criteria
- `ruff check` and `mypy` must pass on every file you write before marking DONE
- EVERY commit must be pushed — no local-only commits
- Progress tracking is MANDATORY — if you skip writing to progress.txt or skip git push, you are failing the task
