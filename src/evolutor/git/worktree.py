"""Git worktree management."""

from __future__ import annotations

import shutil
from pathlib import Path

import pygit2
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class WorktreeInfo(BaseModel):
    name: str
    path: str
    branch: str
    is_locked: bool = False


class WorktreeManager:
    """Manage git worktrees for parallel task execution."""

    def __init__(self, repo_path: str | Path, base_dir: str | Path = "/tmp/evolutor/worktrees") -> None:
        self.repo_path = Path(repo_path)
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.repo = pygit2.Repository(str(self.repo_path))

    def create(self, name: str, branch: str | None = None) -> WorktreeInfo:
        wt_path = self.base_dir / name
        if wt_path.exists():
            shutil.rmtree(wt_path)
        ref = None
        if branch:
            ref = self.repo.branches.get(branch)
            if ref is None:
                commit = self.repo.head.peel(pygit2.Commit)
                self.repo.branches.create(branch, commit)
                ref = self.repo.branches.get(branch)
        self.repo.add_worktree(name, str(wt_path), ref)
        actual_branch = branch or name
        logger.info("worktree_created", name=name, path=str(wt_path))
        return WorktreeInfo(name=name, path=str(wt_path), branch=actual_branch)

    def remove(self, name: str) -> None:
        wt_path = self.base_dir / name
        try:
            wt = self.repo.lookup_worktree(name)
            if wt.is_locked:
                wt.unlock()
            wt.prune(True)
        except Exception:
            logger.warning("worktree_prune_failed", name=name)
        if wt_path.exists():
            shutil.rmtree(wt_path)
        logger.info("worktree_removed", name=name)

    def list_active(self) -> list[WorktreeInfo]:
        result = []
        if not self.base_dir.exists():
            return result
        for wt_dir in self.base_dir.iterdir():
            if wt_dir.is_dir() and (wt_dir / ".git").exists():
                try:
                    wt_repo = pygit2.Repository(str(wt_dir))
                    branch = wt_repo.head.shorthand if not wt_repo.head_is_unborn else "HEAD"
                    result.append(WorktreeInfo(
                        name=wt_dir.name,
                        path=str(wt_dir),
                        branch=branch,
                    ))
                except Exception:
                    continue
        return result

    def get_worktree_repo(self, name: str) -> pygit2.Repository:
        wt_path = self.base_dir / name
        return pygit2.Repository(str(wt_path))

    def cleanup_stale(self) -> int:
        cleaned = 0
        for wt_dir in self.base_dir.iterdir() if self.base_dir.exists() else []:
            if wt_dir.is_dir() and not (wt_dir / ".git").exists():
                shutil.rmtree(wt_dir)
                cleaned += 1
        return cleaned
