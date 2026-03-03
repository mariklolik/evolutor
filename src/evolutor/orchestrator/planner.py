"""Planner node — decomposes tasks into subtasks."""

from __future__ import annotations

from typing import Any

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.types.task import Task

logger = structlog.get_logger()


class PlannerNode:
    """Decomposes a task into subtasks using LLM."""

    async def __call__(self, state: OrchestratorState) -> OrchestratorState:
        task = state.get("task")
        if not task:
            state["plan"] = []
            return state

        try:
            # In production, this calls an LLM to decompose the task
            # For now, create a single subtask
            subtask = Task(
                parent_id=task.id,
                title=f"Execute: {task.title}",
                description=task.description,
            )
            state["plan"] = [subtask]
            state["current_subtask_index"] = 0
            logger.info("plan_created", task=task.title, subtasks=len(state["plan"]))
        except Exception as e:
            logger.error("planner_error", task=task.title, error=str(e), exc_info=True)
            state["plan"] = []
            state["should_continue"] = False

        return state
