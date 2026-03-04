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
