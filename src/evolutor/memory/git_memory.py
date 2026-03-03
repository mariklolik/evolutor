"""Git-based memory for change patterns."""

from __future__ import annotations

from pathlib import Path

import pygit2
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ChangeRecord(BaseModel):
    commit_sha: str
    message: str
    author: str
    files_changed: list[str] = Field(default_factory=list)
    timestamp: int = 0


class GitMemory:
    """Extract patterns and context from git history."""

    def __init__(self, repo_path: str | Path = ".") -> None:
        self.repo = pygit2.Repository(str(repo_path))

    def get_recent_changes(self, max_count: int = 20) -> list[ChangeRecord]:
        if self.repo.head_is_unborn:
            return []
        records = []
        for commit in self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TIME):
            files = []
            if commit.parents:
                diff = self.repo.diff(commit.parents[0], commit)
                files = [patch.delta.new_file.path for patch in diff]
            records.append(ChangeRecord(
                commit_sha=str(commit.id),
                message=commit.message.strip(),
                author=commit.author.name,
                files_changed=files,
                timestamp=commit.commit_time,
            ))
            if len(records) >= max_count:
                break
        return records

    def get_file_history(self, file_path: str, max_count: int = 10) -> list[ChangeRecord]:
        if self.repo.head_is_unborn:
            return []
        records = []
        for commit in self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TIME):
            if commit.parents:
                diff = self.repo.diff(commit.parents[0], commit)
                changed = [patch.delta.new_file.path for patch in diff]
                if file_path in changed:
                    records.append(ChangeRecord(
                        commit_sha=str(commit.id),
                        message=commit.message.strip(),
                        author=commit.author.name,
                        files_changed=changed,
                        timestamp=commit.commit_time,
                    ))
            if len(records) >= max_count:
                break
        return records

    def get_related_files(self, file_path: str, max_count: int = 10) -> list[str]:
        co_changed: dict[str, int] = {}
        history = self.get_file_history(file_path, max_count=50)
        for record in history:
            for f in record.files_changed:
                if f != file_path:
                    co_changed[f] = co_changed.get(f, 0) + 1
        sorted_files = sorted(co_changed.items(), key=lambda x: x[1], reverse=True)
        return [f for f, _ in sorted_files[:max_count]]

    def extract_patterns(self) -> dict[str, int]:
        patterns: dict[str, int] = {}
        changes = self.get_recent_changes(50)
        for record in changes:
            msg = record.message.lower()
            for prefix in ("feat:", "fix:", "refactor:", "test:", "docs:", "chore:"):
                if msg.startswith(prefix):
                    patterns[prefix] = patterns.get(prefix, 0) + 1
        return patterns

    def summarize_branch(self, branch_name: str | None = None) -> str:
        changes = self.get_recent_changes(10)
        if not changes:
            return "No changes recorded."
        lines = [f"Branch: {branch_name or self.repo.head.shorthand}"]
        lines.append(f"Recent {len(changes)} commits:")
        for c in changes:
            lines.append(f"  - {c.message[:80]} ({len(c.files_changed)} files)")
        return "\n".join(lines)
