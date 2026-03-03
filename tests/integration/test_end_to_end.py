"""End-to-end integration test with mocked LLM."""

from __future__ import annotations

import asyncio

import pytest

from evolutor.orchestrator.engine import OrchestratorEngine
from evolutor.types.task import Task, TaskResult


class TestEndToEnd:
    def test_full_pipeline_mocked(self):
        """Test the full orchestrator pipeline with default mock behavior."""
        engine = OrchestratorEngine()
        task = Task(
            title="Add logging to module",
            description="Add structlog logging to the file operations module",
        )
        result = asyncio.get_event_loop().run_until_complete(engine.run(task, max_iterations=3))
        assert isinstance(result, TaskResult)
        assert result.success

    def test_evolution_loop_mocked(self):
        """Test the evolution loop runs without errors."""
        from evolutor.evolution.loop import EvolutionLoop
        loop = EvolutionLoop()
        report = asyncio.get_event_loop().run_until_complete(loop.run(generations=3))
        assert report.generations_completed == 3
        assert report.total_mutations == 3

    def test_memory_pipeline(self):
        """Test memory subsystem works end-to-end."""
        from evolutor.memory.scratchpad import Scratchpad
        from evolutor.memory.persistent import PersistentMemory

        sp = Scratchpad()
        sp.set("task_context", "Adding error handling")
        assert sp.get("task_context") is not None

        pm = PersistentMemory(use_local=True)
        pm.store("Successful pattern: always add try/except to I/O")
        results = pm.search("pattern")
        assert len(results) >= 1

    def test_verification_pipeline(self):
        """Test verification subsystem basics."""
        from evolutor.verification.consensus import ConsensusVerifier, ConsensusResult, Vote
        from evolutor.kernel.invariants import InvariantRegistry

        # Invariants pass
        reg = InvariantRegistry()
        report = reg.check_all({})
        assert report.passed

        # Consensus voting
        cv = ConsensusVerifier(threshold=0.6)
        result = ConsensusResult(threshold=0.6)
        votes = [
            Vote(voter_id="a1", accept=True, confidence=1.0),
            Vote(voter_id="a2", accept=True, confidence=0.8),
        ]
        result = cv.vote(result, votes)
        assert result.accepted
