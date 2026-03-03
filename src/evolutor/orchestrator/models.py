"""Orchestrator state models."""

from __future__ import annotations

from typing import Any, TypedDict

from evolutor.types.task import Task, TaskResult


class OrchestratorState(TypedDict, total=False):
    task: Task | None
    plan: list[Task]
    current_subtask_index: int
    results: list[TaskResult]
    context: dict[str, Any]
    iteration: int
    max_iterations: int
    messages: list[dict[str, Any]]
    should_continue: bool
    final_result: TaskResult | None
