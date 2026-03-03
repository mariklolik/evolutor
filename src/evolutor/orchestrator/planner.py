"""Planner node — decomposes tasks into subtasks via LLM."""

from __future__ import annotations

import json
import os

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.types.task import Task

logger = structlog.get_logger()

_SYSTEM = """You are a software project planner. Decompose the task into 3-8 concrete independently-implementable subtasks.
Respond with ONLY a JSON array of objects with "title" and "description" keys. No prose, no markdown."""


def _client():
    import anthropic
    return anthropic.Anthropic(
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )


def _model() -> str:
    return os.environ.get("EVOLUTOR_MODEL", "anthropic/claude-sonnet-4.6")


class PlannerNode:
    async def __call__(self, state: OrchestratorState) -> OrchestratorState:
        import asyncio
        task = state.get("task")
        if not task:
            state["plan"] = []
            return state
        try:
            subtasks = await asyncio.to_thread(self._plan, task)
            state["plan"] = subtasks
            state["current_subtask_index"] = 0
            state["should_continue"] = bool(subtasks)
            logger.info("plan_created", task=task.title, subtasks=len(subtasks))
        except Exception as e:
            logger.error("planner_error", error=str(e))
            state["plan"] = [Task(parent_id=task.id, title=f"Implement: {task.title}", description=task.description)]
            state["current_subtask_index"] = 0
            state["should_continue"] = True
        return state

    def _plan(self, task: Task) -> list[Task]:
        resp = _client().messages.create(
            model=_model(), max_tokens=1024, system=_SYSTEM,
            messages=[{"role": "user", "content": f"Task: {task.title}\n\n{task.description}"}],
        )
        text = resp.content[0].text.strip().lstrip("```json").lstrip("```").rstrip("```")
        items = json.loads(text)
        return [Task(parent_id=task.id, title=i["title"], description=i["description"]) for i in items]
