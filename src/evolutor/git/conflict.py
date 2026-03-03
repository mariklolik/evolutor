"""Git conflict detection and resolution."""

from __future__ import annotations

from enum import Enum

import pygit2
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ResolutionStrategy(str, Enum):
    ours = "ours"
    theirs = "theirs"


class ConflictInfo(BaseModel):
    file_path: str
    ancestor_oid: str | None = None
    ours_oid: str | None = None
    theirs_oid: str | None = None


class Resolution(BaseModel):
    file_path: str
    strategy: ResolutionStrategy
    resolved_content: str | None = None


class ConflictResolver:
    """Detect and resolve git merge conflicts."""

    def __init__(self, repo: pygit2.Repository) -> None:
        self.repo = repo

    def detect_conflicts(self) -> list[ConflictInfo]:
        index = self.repo.index
        if not index.conflicts:
            return []
        conflicts = []
        for conflict in index.conflicts:
            ancestor, ours, theirs = conflict
            conflicts.append(ConflictInfo(
                file_path=ours.path if ours else (theirs.path if theirs else ancestor.path),
                ancestor_oid=str(ancestor.id) if ancestor else None,
                ours_oid=str(ours.id) if ours else None,
                theirs_oid=str(theirs.id) if theirs else None,
            ))
        return conflicts

    def auto_resolve(self, conflict: ConflictInfo, strategy: ResolutionStrategy) -> Resolution:
        if strategy == ResolutionStrategy.ours:
            oid = conflict.ours_oid
        else:
            oid = conflict.theirs_oid

        content = None
        if oid:
            blob = self.repo.get(pygit2.Oid(hex=oid))
            if blob:
                content = blob.data.decode("utf-8")

        if content is not None:
            index = self.repo.index
            full_path = self.repo.workdir + conflict.file_path
            with open(full_path, "w") as f:
                f.write(content)
            index.add(conflict.file_path)
            index.write()
            del index.conflicts[conflict.file_path]

        logger.info("conflict_resolved", file=conflict.file_path, strategy=strategy.value)
        return Resolution(
            file_path=conflict.file_path,
            strategy=strategy,
            resolved_content=content,
        )

    @staticmethod
    def generate_resolution_prompt(conflict: ConflictInfo, ours_content: str | None, theirs_content: str | None) -> str:
        prompt = f"Merge conflict in {conflict.file_path}:\n\n"
        if ours_content:
            prompt += f"<<<< OURS >>>>\n{ours_content}\n\n"
        if theirs_content:
            prompt += f"<<<< THEIRS >>>>\n{theirs_content}\n\n"
        prompt += "Please resolve this conflict by producing the merged content."
        return prompt
