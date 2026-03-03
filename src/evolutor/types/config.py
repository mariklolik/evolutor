from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    image: str = "python:3.11-slim"
    mem_limit: str = "512m"
    cpu_period: int = 100000
    cpu_quota: int = 100000
    pids_limit: int = 256
    storage_size: str = "1G"
    timeout_seconds: int = 300
    network_mode: str = "none"


class GitConfig(BaseModel):
    worktree_base: str = "/tmp/evolutor/worktrees"
    default_branch: str = "main"
    commit_author: str = "Evolutor <evolutor@localhost>"
    max_worktrees: int = 8


class MemoryConfig(BaseModel):
    chromadb_path: str = ".evolutor/chroma"
    graph_path: str = ".evolutor/knowledge_graph.json"
    playbooks_dir: str = "playbooks"
    scratchpad_max_entries: int = 1000
    mem0_api_key: str = ""
    use_local_mem0: bool = True


class EvolutionConfig(BaseModel):
    archive_dims: list[int] = Field(default_factory=lambda: [20, 20])
    archive_ranges: list[tuple[float, float]] = Field(
        default_factory=lambda: [(0.0, 1.0), (0.0, 1.0)]
    )
    population_size: int = 10
    max_generations: int = 100
    migration_interval: int = 10
    plateau_window: int = 20
    canary_duration_seconds: int = 60
    mutation_types: list[str] = Field(
        default_factory=lambda: [
            "refactor", "optimize", "harden", "simplify", "extend", "test_improve"
        ]
    )


class OrchestratorConfig(BaseModel):
    max_parallel_workers: int = 4
    max_iterations: int = 10
    planner_model: str = "claude-opus-4-6"
    worker_model: str = "claude-sonnet-4-6"
    critic_model: str = "claude-sonnet-4-6"
    meta_improver_model: str = "claude-opus-4-6"
    redis_url: str = "redis://localhost:6379"


class EvolutorConfig(BaseModel):
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    log_level: str = "INFO"
    project_root: str = "."
    anthropic_api_key: str = ""
