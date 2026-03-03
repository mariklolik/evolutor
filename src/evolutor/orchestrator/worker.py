"""Worker node — executes subtasks using tools."""

from __future__ import annotations

from typing import Any

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.types.task import TaskResult, TaskStatus

logger = structlog.get_logger()


class WorkerNode:
    """Executes the current subtask using available tools."""

    async def __call__(self, state: OrchestratorState) -> OrchestratorState:
        plan = state.get("plan", [])
        idx = state.get("current_subtask_index", 0)

        if idx >= len(plan):
            state["should_continue"] = False
            return state

        subtask = plan[idx]
        subtask.status = TaskStatus.in_progress
        logger.info("worker_executing", subtask=subtask.title)

        # In production, this uses tools/LLM to execute the subtask
        result = TaskResult(
            task_id=subtask.id,
            success=True,
        )
        subtask.status = TaskStatus.completed
        results = state.get("results", [])
        results.append(result)
        state["results"] = results
        state["current_subtask_index"] = idx + 1

        return state
