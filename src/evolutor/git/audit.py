"""Git-based audit log using git notes on refs/notes/evolutor."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pygit2
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

NOTES_REF = "refs/notes/evolutor"


class AuditEntry(BaseModel):
    action: str
    details: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent: str = "system"
    commit_sha: str | None = None


class AuditLog:
    """Append-only audit log stored as git notes."""

    def __init__(self, repo: pygit2.Repository) -> None:
        self.repo = repo
        self._sig = pygit2.Signature("Evolutor Audit", "audit@evolutor")

    def record_action(self, commit_sha: str, entry: AuditEntry) -> None:
        entry.commit_sha = commit_sha
        oid = pygit2.Oid(hex=commit_sha)
        existing = ""
        try:
            note = self.repo.notes.get(oid, NOTES_REF)
            if note:
                existing = note.message + "\n"
        except Exception:
            pass
        note_text = existing + entry.model_dump_json()
        try:
            self.repo.notes.create(
                self._sig, self._sig, note_text, oid, NOTES_REF, force=True,
            )
        except Exception:
            self.repo.notes.create(
                self._sig, self._sig, note_text, oid, NOTES_REF,
            )
        logger.info("audit_recorded", action=entry.action, commit=commit_sha)

    def get_history(self, max_count: int = 50) -> list[AuditEntry]:
        entries: list[AuditEntry] = []
        if self.repo.head_is_unborn:
            return entries
        for commit in self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TIME):
            try:
                note = self.repo.notes.get(commit.id, NOTES_REF)
                if note:
                    for line in note.message.strip().split("\n"):
                        line = line.strip()
                        if line:
                            try:
                                entries.append(AuditEntry.model_validate_json(line))
                            except Exception:
                                continue
            except Exception:
                continue
            if len(entries) >= max_count:
                break
        return entries

    def get_actions_for_commit(self, commit_sha: str) -> list[AuditEntry]:
        oid = pygit2.Oid(hex=commit_sha)
        entries: list[AuditEntry] = []
        try:
            note = self.repo.notes.get(oid, NOTES_REF)
            if note:
                for line in note.message.strip().split("\n"):
                    line = line.strip()
                    if line:
                        try:
                            entries.append(AuditEntry.model_validate_json(line))
                        except Exception:
                            continue
        except Exception:
            pass
        return entries
