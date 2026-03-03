"""Trust scoring for agents and changes."""

from __future__ import annotations

from enum import IntEnum

import structlog

logger = structlog.get_logger()


class TrustLevel(IntEnum):
    L1 = 1  # New / untrusted
    L2 = 2  # Basic trust
    L3 = 3  # Moderate trust
    L4 = 4  # High trust
    L5 = 5  # Full trust


TRUST_THRESHOLDS = {
    TrustLevel.L2: 5,
    TrustLevel.L3: 15,
    TrustLevel.L4: 30,
    TrustLevel.L5: 60,
}

REVIEW_REQUIRED_BELOW = TrustLevel.L3


class TrustScorer:
    """Compute and manage trust scores for agents."""

    def __init__(self) -> None:
        self._scores: dict[str, dict] = {}

    def compute_trust(self, agent_id: str) -> TrustLevel:
        info = self._scores.get(agent_id, {"successes": 0, "failures": 0})
        net = info["successes"] - info["failures"] * 2
        for level in (TrustLevel.L5, TrustLevel.L4, TrustLevel.L3, TrustLevel.L2):
            if net >= TRUST_THRESHOLDS[level]:
                return level
        return TrustLevel.L1

    def should_require_review(self, agent_id: str) -> bool:
        return self.compute_trust(agent_id) < REVIEW_REQUIRED_BELOW

    def update_trust(self, agent_id: str, success: bool) -> TrustLevel:
        if agent_id not in self._scores:
            self._scores[agent_id] = {"successes": 0, "failures": 0}
        if success:
            self._scores[agent_id]["successes"] += 1
        else:
            self._scores[agent_id]["failures"] += 1
        level = self.compute_trust(agent_id)
        logger.info("trust_updated", agent=agent_id, success=success, level=level.name)
        return level

    def get_scores(self) -> dict[str, dict]:
        return dict(self._scores)
