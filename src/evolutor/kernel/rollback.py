"""Rollback management using git savepoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pygit2
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class Savepoint(BaseModel):
    label: str
    commit_sha: str
    branch: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""


class RollbackManager:
    """Create and restore savepoints using git refs."""

    SAVEPOINT_PREFIX = "refs/savepoints/"

    def __init__(self, repo: pygit2.Repository) -> None:
        self.repo = repo

    def create_savepoint(self, label: str, description: str = "") -> Savepoint:
        if self.repo.head_is_unborn:
            raise RuntimeError("Cannot create savepoint: no commits yet")
        commit = self.repo.head.peel(pygit2.Commit)
        ref_name = f"{self.SAVEPOINT_PREFIX}{label}"
        self.repo.references.create(ref_name, commit.id, force=True)
        branch = self.repo.head.shorthand
        sp = Savepoint(
            label=label,
            commit_sha=str(commit.id),
            branch=branch,
            description=description,
        )
        logger.info("savepoint_created", label=label, sha=sp.commit_sha)
        return sp

    def rollback_to(self, label: str) -> str:
        ref_name = f"{self.SAVEPOINT_PREFIX}{label}"
        try:
            ref = self.repo.references.get(ref_name)
        except Exception:
            ref = None
        if ref is None:
            raise ValueError(f"Savepoint {label} not found")
        commit = ref.peel(pygit2.Commit)
        self.repo.reset(commit.id, pygit2.GIT_RESET_HARD)
        logger.info("rollback_to", label=label, sha=str(commit.id))
        return str(commit.id)

    def rollback_branch(self, branch_name: str, commit_sha: str) -> None:
        branch = self.repo.branches.get(branch_name)
        if branch is None:
            raise ValueError(f"Branch {branch_name} not found")
        oid = pygit2.Oid(hex=commit_sha)
        branch.set_target(oid)
        logger.info("branch_rollback", branch=branch_name, sha=commit_sha)

    def list_savepoints(self) -> list[Savepoint]:
        savepoints = []
        for ref_name in self.repo.references:
            if ref_name.startswith(self.SAVEPOINT_PREFIX):
                label = ref_name[len(self.SAVEPOINT_PREFIX):]
                ref = self.repo.references.get(ref_name)
                commit = ref.peel(pygit2.Commit)
                savepoints.append(Savepoint(
                    label=label,
                    commit_sha=str(commit.id),
                    branch="",
                ))
        return savepoints
