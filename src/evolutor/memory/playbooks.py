"""Playbook management for coding strategies."""

from __future__ import annotations

from pathlib import Path

import structlog

from evolutor.types.memory import Playbook

logger = structlog.get_logger()


class PlaybookManager:
    """Load, search, and manage playbooks."""

    def __init__(self, playbooks_dir: str = "playbooks") -> None:
        self.playbooks_dir = Path(playbooks_dir)
        self._playbooks: dict[str, Playbook] = {}

    def load_all(self) -> list[Playbook]:
        if not self.playbooks_dir.exists():
            return []
        for f in self.playbooks_dir.glob("*.md"):
            content = f.read_text()
            language = f.stem
            pb = Playbook(name=f.stem, language=language, content=content)
            self._playbooks[pb.id] = pb
        logger.info("playbooks_loaded", count=len(self._playbooks))
        return list(self._playbooks.values())

    def get_by_language(self, language: str) -> list[Playbook]:
        return [pb for pb in self._playbooks.values() if pb.language == language]

    def search(self, query: str) -> list[Playbook]:
        query_lower = query.lower()
        return [
            pb for pb in self._playbooks.values()
            if query_lower in pb.content.lower() or query_lower in pb.name.lower()
        ]

    def record_outcome(self, playbook_id: str, helpful: bool) -> None:
        pb = self._playbooks.get(playbook_id)
        if pb:
            if helpful:
                pb.helpful_count += 1
            else:
                pb.harmful_count += 1

    def create_delta(self, parent_id: str, new_content: str) -> Playbook:
        parent = self._playbooks.get(parent_id)
        if not parent:
            raise ValueError(f"Parent playbook {parent_id} not found")
        delta = Playbook(
            parent_id=parent_id,
            name=f"{parent.name}_delta",
            language=parent.language,
            content=new_content,
        )
        self._playbooks[delta.id] = delta
        return delta

    def get_effective_playbook(self, playbook_id: str) -> Playbook:
        pb = self._playbooks.get(playbook_id)
        if not pb:
            raise ValueError(f"Playbook {playbook_id} not found")
        # If it's a delta, merge with parent
        if pb.parent_id:
            parent = self._playbooks.get(pb.parent_id)
            if parent:
                merged = Playbook(
                    name=pb.name,
                    language=pb.language,
                    content=parent.content + "\n\n---\n\n" + pb.content,
                    helpful_count=pb.helpful_count,
                    harmful_count=pb.harmful_count,
                )
                return merged
        return pb

    def prune_harmful(self, threshold: float = 0.3) -> int:
        pruned = 0
        to_remove = [
            pid for pid, pb in self._playbooks.items()
            if pb.score() < threshold and (pb.helpful_count + pb.harmful_count) > 5
        ]
        for pid in to_remove:
            del self._playbooks[pid]
            pruned += 1
        return pruned
