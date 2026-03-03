"""Evolution archive using pyribs GridArchive."""

from __future__ import annotations

import numpy as np
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ArchiveEntry(BaseModel):
    solution_id: str
    fitness: float = 0.0
    behavior: list[float] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ArchiveStats(BaseModel):
    total_entries: int = 0
    coverage: float = 0.0
    best_fitness: float = 0.0
    mean_fitness: float = 0.0


class EvolutionArchive:
    """MAP-Elites archive using ribs GridArchive."""

    def __init__(self, dims: list[int] | None = None, ranges: list[tuple[float, float]] | None = None) -> None:
        self._dims = dims or [20, 20]
        self._ranges = ranges or [(0.0, 1.0), (0.0, 1.0)]
        self._archive = None
        self._init_archive()

    def _init_archive(self) -> None:
        try:
            from ribs.archives import GridArchive
            self._archive = GridArchive(
                solution_dim=1,
                dims=self._dims,
                ranges=self._ranges,
            )
        except Exception as e:
            logger.warning("ribs_archive_init_failed", error=str(e))
            self._entries: list[ArchiveEntry] = []

    def add(self, solution_id: str, fitness: float, behavior: list[float], metadata: dict | None = None) -> None:
        entry = ArchiveEntry(solution_id=solution_id, fitness=fitness, behavior=behavior, metadata=metadata or {})
        if self._archive is not None:
            try:
                self._archive.add(
                    np.array([[0.0]]),
                    np.array([fitness]),
                    np.array([behavior]),
                )
            except Exception as e:
                logger.warning("archive_add_failed", error=str(e))
        else:
            self._entries.append(entry)

    def sample_elites(self, count: int = 5) -> list[ArchiveEntry]:
        if self._archive is not None:
            try:
                df = self._archive.as_pandas()
                if len(df) == 0:
                    return []
                top = df.nlargest(min(count, len(df)), "objective")
                return [
                    ArchiveEntry(solution_id=str(i), fitness=row["objective"])
                    for i, row in top.iterrows()
                ]
            except Exception:
                pass
        if hasattr(self, "_entries"):
            sorted_entries = sorted(self._entries, key=lambda e: e.fitness, reverse=True)
            return sorted_entries[:count]
        return []

    def sample_diverse(self, count: int = 5) -> list[ArchiveEntry]:
        if self._archive is not None:
            try:
                elites = self._archive.sample_elites(min(count, len(self._archive)))
                return [
                    ArchiveEntry(solution_id=str(i), fitness=float(elites["objective"][i]))
                    for i in range(len(elites["objective"]))
                ]
            except Exception:
                pass
        return self.sample_elites(count)

    def get_stats(self) -> ArchiveStats:
        if self._archive is not None:
            try:
                df = self._archive.as_pandas()
                if len(df) == 0:
                    return ArchiveStats()
                return ArchiveStats(
                    total_entries=len(df),
                    coverage=len(df) / (self._dims[0] * self._dims[1]),
                    best_fitness=float(df["objective"].max()),
                    mean_fitness=float(df["objective"].mean()),
                )
            except Exception:
                pass
        entries = getattr(self, "_entries", [])
        if not entries:
            return ArchiveStats()
        fitnesses = [e.fitness for e in entries]
        return ArchiveStats(
            total_entries=len(entries),
            coverage=len(entries) / (self._dims[0] * self._dims[1]),
            best_fitness=max(fitnesses),
            mean_fitness=sum(fitnesses) / len(fitnesses),
        )

    def coverage(self) -> float:
        return self.get_stats().coverage
