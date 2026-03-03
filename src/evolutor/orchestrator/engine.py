"""Orchestrator engine — LangGraph-based state machine."""

from __future__ import annotations

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.orchestrator.planner import PlannerNode
from evolutor.orchestrator.worker import WorkerNode
from evolutor.orchestrator.critic import CriticNode
from evolutor.types.task import Task, TaskResult

logger = structlog.get_logger()


class OrchestratorEngine:
    """LangGraph-based orchestration engine."""

    def __init__(self) -> None:
        self.planner = PlannerNode()
        self.worker = WorkerNode()
        self.critic = CriticNode()

    async def run(self, task: Task, max_iterations: int = 10) -> TaskResult:
        state: OrchestratorState = {
            "task": task,
            "plan": [],
            "current_subtask_index": 0,
            "results": [],
            "context": {},
            "iteration": 0,
            "max_iterations": max_iterations,
            "messages": [],
            "should_continue": True,
            "final_result": None,
        }

        try:
            # Plan
            state = await self.planner(state)

            # Execute loop
            while state.get("should_continue", False):
                state = await self.worker(state)
                state = await self.critic(state)

                if state.get("iteration", 0) >= max_iterations:
                    break

            result = state.get("final_result")
            if result is None:
                result = TaskResult(task_id=task.id, success=False, error="No result produced")

        except Exception as e:
            logger.error("orchestrator_error", task=task.title, error=str(e), exc_info=True)
            result = TaskResult(task_id=task.id, success=False, error=str(e))

        logger.info("orchestrator_done", task=task.title, success=result.success)
        return result

    def build_graph(self):
        """Build a LangGraph StateGraph for the orchestrator."""
        try:
            from langgraph.graph import StateGraph, END

            graph = StateGraph(OrchestratorState)
            graph.add_node("planner", self.planner)
            graph.add_node("worker", self.worker)
            graph.add_node("critic", self.critic)

            graph.set_entry_point("planner")
            graph.add_edge("planner", "worker")
            graph.add_edge("worker", "critic")

            def should_continue(state):
                if state.get("should_continue", False):
                    return "worker"
                return END

            graph.add_conditional_edges("critic", should_continue)
            return graph.compile()
        except ImportError:
            logger.warning("langgraph_not_available")
            return None
