"""In-memory scratchpad for agent working memory."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


class Scratchpad:
    """Key-value scratchpad with ordered access."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries = max_entries
        self._data: OrderedDict[str, dict] = OrderedDict()

    def set(self, key: str, value: str) -> None:
        self._data[key] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._data.move_to_end(key)
        self._enforce_limit()

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        return entry["value"] if entry else None

    def append(self, key: str, value: str) -> None:
        existing = self.get(key) or ""
        self.set(key, existing + value)

    def get_recent(self, count: int = 10) -> list[tuple[str, str]]:
        items = list(self._data.items())
        recent = items[-count:] if len(items) > count else items
        return [(k, v["value"]) for k, v in reversed(recent)]

    def summarize(self) -> str:
        items = self.get_recent(20)
        lines = [f"Scratchpad ({len(self._data)} entries):"]
        for key, value in items:
            preview = value[:100] + "..." if len(value) > 100 else value
            lines.append(f"  {key}: {preview}")
        return "\n".join(lines)

    def clear(self) -> None:
        self._data.clear()

    def _enforce_limit(self) -> None:
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)
