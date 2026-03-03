"""Critic node — reviews work and decides accept/revise/reject."""

from __future__ import annotations

from enum import Enum

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.types.task import TaskResult

logger = structlog.get_logger()


class CriticDecision(str, Enum):
    accept = "accept"
    revise = "revise"
    reject = "reject"


class CriticNode:
    """Reviews worker output and makes accept/revise/reject decisions."""

    async def __call__(self, state: OrchestratorState) -> OrchestratorState:
        results = state.get("results", [])
        if not results:
            state["should_continue"] = False
            return state

        last_result = results[-1]

        try:
            decision = self._decide(last_result, state)

            if decision == CriticDecision.accept:
                plan = state.get("plan", [])
                idx = state.get("current_subtask_index", 0)
                if idx >= len(plan):
                    state["should_continue"] = False
                    state["final_result"] = last_result
                else:
                    state["should_continue"] = True
            elif decision == CriticDecision.revise:
                state["current_subtask_index"] = max(0, state.get("current_subtask_index", 1) - 1)
                iteration = state.get("iteration", 0) + 1
                state["iteration"] = iteration
                state["should_continue"] = iteration < state.get("max_iterations", 10)
            else:
                state["should_continue"] = False
                state["final_result"] = TaskResult(
                    task_id=last_result.task_id, success=False, error="Rejected by critic",
                )

            logger.info("critic_decision", decision=decision.value)
        except Exception as e:
            logger.error("critic_error", error=str(e), exc_info=True)
            state["should_continue"] = False
            state["final_result"] = TaskResult(
                task_id=last_result.task_id, success=False, error=f"Critic error: {e}",
            )

        return state

    def _decide(self, result: TaskResult, state: OrchestratorState) -> CriticDecision:
        if result.success:
            return CriticDecision.accept
        iteration = state.get("iteration", 0)
        if iteration < state.get("max_iterations", 10) - 1:
            return CriticDecision.revise
        return CriticDecision.reject
