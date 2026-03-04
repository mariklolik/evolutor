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

    def select_parent_by_cmp(self) -> str | None:
        """HGM Clade-Metaproductivity: Thompson sampling Beta(1+wins, 1+losses).

        Ref: HGM paper §3.2 Algorithm 1 — θ_a ~ Beta(1+n_success^Clade(a), 1+n_failure^Clade(a))
        Selects agents by evolutionary fertility (future improvement potential), not current score.
        """
        try:
            import numpy as np
        except ImportError:
            return None

        if not hasattr(self, "_clade"):
            self._clade: dict[str, dict] = {}

        entries = getattr(self, "_entries", [])
        if not entries:
            # Try ribs archive
            if self._archive is not None:
                try:
                    df = self._archive.as_pandas()
                    if len(df) == 0:
                        return None
                    # No CMP data yet — return highest fitness
                    return str(df["objective"].idxmax())
                except Exception:
                    return None
            return None

        best_sample, best_id = -1.0, None
        for entry in entries:
            clade = self._clade.get(entry.solution_id, {"wins": 1, "losses": 1})
            # Thompson sample: explores uncertain lineages, exploits proven ones
            sample = float(np.random.beta(1 + clade["wins"], 1 + clade["losses"]))
            if sample > best_sample:
                best_sample, best_id = sample, entry.solution_id
        return best_id

    def update_clade_stats(self, agent_id: str, parent_id: str | None, success: bool) -> None:
        """Propagate descendant score up lineage tree (HGM CMP mechanism).

        When agent_id achieves result, ALL its ancestors' CMP estimates are updated.
        This is the key insight: a parent that produces successful children has high CMP.
        """
        if not hasattr(self, "_clade"):
            self._clade = {}
        if not hasattr(self, "_lineage"):
            self._lineage: dict[str, str] = {}

        if parent_id:
            self._lineage[agent_id] = parent_id

        # Walk up the tree updating all ancestors
        current = parent_id
        visited: set = set()
        while current and current not in visited:
            visited.add(current)
            if current not in self._clade:
                self._clade[current] = {"wins": 1, "losses": 1}
            if success:
                self._clade[current]["wins"] += 1
            else:
                self._clade[current]["losses"] += 1
            current = self._lineage.get(current)

    def coverage(self) -> float:
        return self.get_stats().coverage
