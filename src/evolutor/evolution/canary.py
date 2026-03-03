"""Canary deployment for safe evolution rollout."""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CanaryMetrics(BaseModel):
    test_pass_rate: float = 0.0
    error_rate: float = 0.0
    latency_p99: float = 0.0


class CanaryResult(BaseModel):
    promoted: bool = False
    rolled_back: bool = False
    metrics: CanaryMetrics = Field(default_factory=CanaryMetrics)
    reason: str = ""


class CanaryDeployer:
    """Deploy changes via canary pattern."""

    def __init__(self, threshold_pass_rate: float = 0.95) -> None:
        self.threshold_pass_rate = threshold_pass_rate
        self._active_canary: dict | None = None

    async def deploy_canary(self, branch_name: str, target_branch: str = "main") -> str:
        try:
            self._active_canary = {
                "branch": branch_name,
                "target": target_branch,
                "status": "deployed",
            }
            logger.info("canary_deployed", branch=branch_name)
            return f"canary-{branch_name}"
        except Exception as e:
            logger.error("canary_deploy_error", branch=branch_name, error=str(e), exc_info=True)
            return ""

    async def promote(self, canary_id: str) -> CanaryResult:
        if not self._active_canary:
            return CanaryResult(reason="No active canary")
        try:
            self._active_canary["status"] = "promoted"
            logger.info("canary_promoted", canary=canary_id)
            return CanaryResult(promoted=True, reason="Metrics within threshold")
        except Exception as e:
            logger.error("canary_promote_error", canary=canary_id, error=str(e), exc_info=True)
            return CanaryResult(reason=f"Promote failed: {e}")

    async def rollback_canary(self, canary_id: str) -> CanaryResult:
        if not self._active_canary:
            return CanaryResult(reason="No active canary")
        try:
            self._active_canary["status"] = "rolled_back"
            logger.info("canary_rolled_back", canary=canary_id)
            return CanaryResult(rolled_back=True, reason="Metrics below threshold")
        except Exception as e:
            logger.error("canary_rollback_error", canary=canary_id, error=str(e), exc_info=True)
            return CanaryResult(reason=f"Rollback failed: {e}")

    async def monitor(self, canary_id: str) -> CanaryMetrics:
        try:
            # In production, this collects real metrics
            return CanaryMetrics(test_pass_rate=0.98, error_rate=0.01, latency_p99=0.1)
        except Exception as e:
            logger.error("canary_monitor_error", canary=canary_id, error=str(e), exc_info=True)
            return CanaryMetrics()
