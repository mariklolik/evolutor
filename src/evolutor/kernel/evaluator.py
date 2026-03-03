"""Evaluation of code changes against invariants and metrics."""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from evolutor.kernel.invariants import InvariantRegistry, InvariantReport
from evolutor.types.metrics import CodeMetrics, FitnessVector

logger = structlog.get_logger()


class EvaluationResult(BaseModel):
    accepted: bool = False
    reason: str = ""
    invariant_report: InvariantReport = Field(default_factory=InvariantReport)
    metrics_delta: dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0


class Evaluator:
    """Evaluate code changes against invariants and quality metrics."""

    def __init__(self, registry: InvariantRegistry | None = None) -> None:
        self.registry = registry or InvariantRegistry()

    async def evaluate(self, context: dict[str, Any]) -> EvaluationResult:
        report = self.registry.check_all(context)
        metrics_before = context.get("metrics_before", {})
        metrics_after = context.get("metrics_after", {})
        delta = self.compute_delta(metrics_before, metrics_after)
        accepted = report.passed
        reason = "All invariants passed" if accepted else f"{len(report.violations)} violation(s)"
        confidence = 1.0 if accepted else 0.0
        return EvaluationResult(
            accepted=accepted,
            reason=reason,
            invariant_report=report,
            metrics_delta=delta,
            confidence=confidence,
        )

    @staticmethod
    def compute_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
        all_keys = set(before) | set(after)
        return {k: after.get(k, 0.0) - before.get(k, 0.0) for k in all_keys}

    @staticmethod
    def should_accept(result: EvaluationResult) -> bool:
        return result.accepted and result.confidence >= 0.5
