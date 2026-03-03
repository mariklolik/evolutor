"""Branch naming strategy and management."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pygit2
import structlog

logger = structlog.get_logger()

PREFIXES = ("feat/", "fix/", "evo/", "exp/")


@dataclass
class ParsedBranch:
    prefix: str
    task_id: str
    description: str


class BranchStrategy:
    """Generate and parse branch names following conventions."""

    def __init__(self, repo: pygit2.Repository) -> None:
        self.repo = repo

    @staticmethod
    def generate_branch_name(prefix: str, task_id: str, description: str) -> str:
        if prefix not in PREFIXES:
            raise ValueError(f"Invalid prefix: {prefix}. Must be one of {PREFIXES}")
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:40]
        return f"{prefix}{task_id}/{slug}"

    @staticmethod
    def parse_branch_name(name: str) -> ParsedBranch | None:
        for prefix in PREFIXES:
            if name.startswith(prefix):
                rest = name[len(prefix):]
                parts = rest.split("/", 1)
                task_id = parts[0]
                description = parts[1] if len(parts) > 1 else ""
                return ParsedBranch(prefix=prefix, task_id=task_id, description=description)
        return None

    def get_evolution_branches(self) -> list[str]:
        return [
            name for name in self.repo.branches
            if name.startswith("evo/")
        ]

    def get_merge_candidates(self, target_branch: str = "main") -> list[str]:
        candidates = []
        if self.repo.head_is_unborn:
            return candidates
        try:
            target = self.repo.branches.get(target_branch)
            if target is None:
                return candidates
        except Exception:
            return candidates
        for name in self.repo.branches:
            if name == target_branch:
                continue
            for prefix in PREFIXES:
                if name.startswith(prefix):
                    candidates.append(name)
                    break
        return candidates
