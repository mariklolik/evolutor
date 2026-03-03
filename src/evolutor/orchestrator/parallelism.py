"""Parallel worker execution with semaphore control."""

from __future__ import annotations

import asyncio

import structlog

from evolutor.orchestrator.engine import OrchestratorEngine
from evolutor.types.task import Task, TaskResult

logger = structlog.get_logger()


class ParallelRunner:
    """Run multiple tasks in parallel with concurrency control."""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)

    async def run_tasks(self, tasks: list[Task]) -> list[TaskResult]:
        async def _run_one(task: Task) -> TaskResult:
            async with self._semaphore:
                engine = OrchestratorEngine()
                return await engine.run(task)

        results = await asyncio.gather(*[_run_one(t) for t in tasks])
        logger.info("parallel_run_complete", total=len(tasks), succeeded=sum(1 for r in results if r.success))
        return list(results)
