"""Evolution archive using pyribs GridArchive."""

from __future__ import annotations

import re

import numpy as np
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


def compute_behavior(agent_code: str) -> list[float]:
    """Compute behavioral dimensions for MAP-Elites.

    Returns [complexity, tool_diversity] as floats in [0, 1].

    complexity:    normalize line count — 50 lines → 0.0, 500 lines → 1.0
    tool_diversity: count 'def ' definitions in TOOL_TEMPLATES section → normalize /10
    """
    lines = agent_code.splitlines()
    n_lines = len(lines)
    complexity = min(1.0, max(0.0, (n_lines - 50) / 450.0))

    # Count tool functions in TOOL_TEMPLATES section
    tool_count = 0
    try:
        # Find TOOL_TEMPLATES section between its marker and the next marker
        marker_re = re.compile(r"# ===== EVOLVABLE SECTION")
        in_templates = False
        for line in lines:
            if "EVOLVABLE SECTION: Tool Templates" in line:
                in_templates = True
                continue
            if in_templates:
                if marker_re.search(line):
                    break  # next section reached
                if line.strip().startswith("def "):
                    tool_count += 1
    except Exception:
        pass

    tool_diversity = min(1.0, tool_count / 10.0)
    return [complexity, tool_diversity]


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

    # ── MAP-Elites 10×10 grid ────────────────────────────────────────────────

    def _ensure_grid(self) -> None:
        if not hasattr(self, "_grid"):
            # dict[cell_index: int] -> (node_id: str, fitness: float)
            self._grid: dict[int, tuple[str, float]] = {}

    def add_with_behavior(self, node_id: str, fitness: float, agent_code: str) -> None:
        """Add agent to MAP-Elites grid cell based on behavioral dimensions."""
        self._ensure_grid()
        behavior = compute_behavior(agent_code)
        row = int(behavior[0] * 9.99)
        col = int(behavior[1] * 9.99)
        idx = row * 10 + col
        existing = self._grid.get(idx)
        if existing is None or fitness > existing[1]:
            self._grid[idx] = (node_id, fitness)
            logger.debug("archive_cell_updated", cell=idx, node=node_id, fitness=fitness)

    def get_underexplored_cells(self) -> list[int]:
        """Return list of cell indices (0-99) with no entries."""
        self._ensure_grid()
        return [i for i in range(100) if i not in self._grid]

    def sample_from_cell(self, cell_index: int) -> str | None:
        """Return node_id from a specific cell, or None if empty."""
        self._ensure_grid()
        entry = self._grid.get(cell_index)
        return entry[0] if entry else None
