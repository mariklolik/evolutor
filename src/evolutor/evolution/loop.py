"""Evolution loop — HGM tree + MAP-Elites + cascading eval for seed_agent.py."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from pydantic import BaseModel

from evolutor.evolution.archive import EvolutionArchive
from evolutor.evolution.cascade import CascadingEvaluator
from evolutor.evolution.mutator import Mutator
from evolutor.evolution.plateau import PlateauDetector
from evolutor.evolution.tree import EvolutionTree
from evolutor.kernel.invariants import KernelIntegrityChecker
from evolutor.swebench.harness import eval_agent_code_docker

logger = structlog.get_logger()

SEED_AGENT_PATH = "src/evolutor/swebench/seed_agent.py"


@dataclass
class EvolutionConfig:
    eval_budget: int = 100
    expansion_alpha: float = 0.6
    max_steps_per_task: int = 50
    task_timeout: int = 600
    mutation_timeout: int = 120
    plateau_window: int = 40
    cascade_max_stage: int = 1


class EvolutionReport(BaseModel):
    evals_completed: int = 0
    tree_nodes: int = 1
    best_fitness: float = 0.0
    best_agent_id: str = "root"
    archive_coverage: float = 0.0
    plateaus_detected: int = 0
    cascade_rejections: int = 0
    mutations_attempted: int = 0
    mutations_accepted: int = 0
    eval_log: list = []
