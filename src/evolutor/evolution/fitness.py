"""Fitness evaluation using pymoo NSGA-III."""

from __future__ import annotations

import numpy as np
import structlog

from evolutor.types.metrics import FitnessVector

logger = structlog.get_logger()


class FitnessEvaluator:
    """Multi-objective fitness evaluation using pymoo."""

    def __init__(self, n_objectives: int = 4) -> None:
        self.n_objectives = n_objectives

    def evaluate(self, fitness: FitnessVector) -> list[float]:
        return fitness.to_minimize()

    def compare(self, a: FitnessVector, b: FitnessVector) -> int:
        """Pareto comparison: -1 if a dominates b, 1 if b dominates a, 0 otherwise."""
        a_vals = np.array(a.to_minimize())
        b_vals = np.array(b.to_minimize())
        a_better = np.all(a_vals <= b_vals) and np.any(a_vals < b_vals)
        b_better = np.all(b_vals <= a_vals) and np.any(b_vals < a_vals)
        if a_better:
            return -1
        if b_better:
            return 1
        return 0

    def select_survivors(self, population: list[FitnessVector], count: int) -> list[int]:
        """Select best solutions using non-dominated sorting."""
        n = len(population)
        if n <= count:
            return list(range(n))

        # Simple non-dominated sorting
        fronts = self._non_dominated_sort(population)
        selected = []
        for front in fronts:
            if len(selected) + len(front) <= count:
                selected.extend(front)
            else:
                remaining = count - len(selected)
                selected.extend(front[:remaining])
                break
        return selected

    def rank_population(self, population: list[FitnessVector]) -> list[tuple[int, int]]:
        """Return (index, rank) pairs sorted by rank."""
        fronts = self._non_dominated_sort(population)
        ranking = []
        for rank, front in enumerate(fronts):
            for idx in front:
                ranking.append((idx, rank))
        return sorted(ranking, key=lambda x: x[1])

    def _non_dominated_sort(self, population: list[FitnessVector]) -> list[list[int]]:
        n = len(population)
        domination_count = [0] * n
        dominated_by: list[list[int]] = [[] for _ in range(n)]
        fronts: list[list[int]] = [[]]

        for i in range(n):
            for j in range(i + 1, n):
                cmp = self.compare(population[i], population[j])
                if cmp == -1:
                    dominated_by[i].append(j)
                    domination_count[j] += 1
                elif cmp == 1:
                    dominated_by[j].append(i)
                    domination_count[i] += 1

        for i in range(n):
            if domination_count[i] == 0:
                fronts[0].append(i)

        current = 0
        while fronts[current]:
            next_front = []
            for i in fronts[current]:
                for j in dominated_by[i]:
                    domination_count[j] -= 1
                    if domination_count[j] == 0:
                        next_front.append(j)
            current += 1
            fronts.append(next_front)

        return [f for f in fronts if f]
