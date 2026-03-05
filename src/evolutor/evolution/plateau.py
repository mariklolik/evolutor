"""Plateau detection using change point detection."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class PlateauDetector:
    """Detect fitness plateaus using variance analysis."""

    def __init__(self, window_size: int = 20, variance_threshold: float = 0.001) -> None:
        self.window_size = window_size
        self.variance_threshold = variance_threshold
        self._history: list[float] = []

    def record(self, fitness: float) -> None:
        self._history.append(fitness)

    def detect(self) -> bool:
        if len(self._history) < self.window_size:
            return False
        try:
            import ruptures
            import numpy as np
            signal = list(self._history[-self.window_size:])
            algo = ruptures.Pelt(model="rbf").fit(signal)
            breakpoints = algo.predict(pen=3)
            # No changepoint found = plateau
            if len(breakpoints) <= 1:
                return float(np.std(signal)) < 0.02
            return False
        except (ImportError, Exception):
            # Fallback variance method
            window = self._history[-self.window_size:]
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            return variance < self.variance_threshold

    def suggest_action(self) -> str:
        if not self.detect():
            return "continue"
        if len(self._history) > self.window_size * 3:
            return "diversify"
        return "increase_mutation_rate"

    def reset(self) -> None:
        self._history.clear()

    def record_batch(self, fitness_values: list[float]) -> None:
        """Record multiple fitness values at once."""
        for v in fitness_values:
            self.record(v)

    def should_diversify(self, window: int = 40) -> bool:
        """Return True if recent fitness is plateauing."""
        if len(self._history) < window:
            return False
        return self.detect()


class DiversificationStrategy:
    """Diversification via under-explored MAP-Elites cells and wider mutations."""

    def __init__(self, archive, tree) -> None:
        self.archive = archive
        self.tree = tree

    def select_diverse_parent(self) -> str:
        """Pick a parent from an under-explored archive cell, or fall back to Thompson."""
        try:
            import random
            underexplored = self.archive.get_underexplored_cells()
            if underexplored:
                # Find occupied cells near under-explored ones
                occupied = [
                    i for i in range(100)
                    if i not in underexplored and self.archive.sample_from_cell(i) is not None
                ]
                if occupied:
                    # Pick a random occupied cell neighboring an under-explored cell
                    node_id = self.archive.sample_from_cell(random.choice(occupied))
                    if node_id and node_id in self.tree.nodes:
                        return node_id
        except Exception:
            pass
        return self.tree.thompson_sample()

    def get_wider_mutation_params(self) -> dict:
        """Return parameters for more exploratory mutations during plateau."""
        return {"temperature": 1.5, "force_type": "improve_system_prompt"}

    def apply(self, tree, archive) -> str:
        """Select diverse parent for evolution during plateau."""
        self.tree = tree
        self.archive = archive
        return self.select_diverse_parent()
