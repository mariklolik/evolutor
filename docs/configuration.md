# Configuration

## Config Sources (priority order)

1. CLI flags (highest priority)
2. Environment variables
3. `.evolutor.toml` (project-specific)
4. `configs/default.toml` (defaults)

## Config Files

### configs/default.toml
Main configuration with all sections: sandbox, git, memory, evolution, orchestrator.

### configs/models.toml
LLM model configuration per agent role (planner, worker, critic, meta_improver).

### configs/sandbox.toml
Docker container and network settings.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key | (empty) |
| `REDIS_URL` | Redis connection | `redis://localhost:6379` |
| `EVOLUTOR_LOG_LEVEL` | Logging level | `INFO` |

## Sections

### [sandbox]
- `image` — Docker base image
- `mem_limit` — Container memory limit
- `timeout_seconds` — Execution timeout

### [git]
- `worktree_base` — Worktree directory
- `default_branch` — Default branch name
- `max_worktrees` — Maximum concurrent worktrees

### [memory]
- `chromadb_path` — ChromaDB storage path
- `playbooks_dir` — Playbook files directory
- `use_local_mem0` — Use local memory (vs API)

### [evolution]
- `archive_dims` — MAP-Elites grid dimensions
- `population_size` — Evolution population size
- `max_generations` — Maximum generations
- `mutation_types` — Enabled mutation types

### [orchestrator]
- `max_parallel_workers` — Concurrent workers
- `max_iterations` — Max orchestrator iterations
- `planner_model` — LLM for planning
- `worker_model` — LLM for execution
