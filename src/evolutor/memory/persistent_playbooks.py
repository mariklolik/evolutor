"""PersistentPlaybookStore — ACE-pattern cross-session learning.

Accumulates helpful/harmful strategy tags from both:
- Offline evolution (which mutations improved scores)
- Runtime tool synthesis (which tools were effective)

This is what makes dual-mode evolution work: both offline and runtime
improvements feed into the same persistent store, and the next generation
gets context about what worked before.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from evolutor.tools.synthesizer import SynthesizedTool

logger = structlog.get_logger()


class PersistentPlaybookStore:
    """Persistent strategy store that survives across sessions.

    Implements ACE (Accumulate-Compress-Emit) pattern:
    - Accumulate: record outcomes from evolution + runtime
    - Compress: prune harmful strategies, keep top helpful
    - Emit: format as context string for mutation LLM prompts
    """

    def __init__(self, store_path: str | Path | None = None):
        self._path = Path(store_path or "playbooks/persistent_store.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {"helpful": [], "harmful": [], "tools": [], "version": 1}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def add_helpful(self, strategy: str, delta: float, source: str = "evolution") -> None:
        """Record a strategy that improved performance."""
        entry = {
            "strategy": strategy[:500],
            "delta": delta,
            "source": source,
            "ts": int(time.time()),
        }
        self._data["helpful"].append(entry)
        # Keep only top 50 by delta
        self._data["helpful"] = sorted(
            self._data["helpful"], key=lambda x: x.get("delta", 0), reverse=True
        )[:50]
        self._save()
        logger.info("playbook_helpful_added", delta=delta, source=source)

    def add_harmful(self, strategy: str, delta: float, source: str = "evolution") -> None:
        """Record a strategy that degraded performance."""
        entry = {
            "strategy": strategy[:500],
            "delta": delta,
            "source": source,
            "ts": int(time.time()),
        }
        self._data["harmful"].append(entry)
        self._data["harmful"] = self._data["harmful"][-30:]  # keep recent 30
        self._save()

    def add_tool_pattern(self, tool: "SynthesizedTool", context: str) -> None:
        """Persist a runtime-synthesized tool for future use."""
        entry = {
            "name": tool.name,
            "description": tool.description,
            "code": tool.code,
            "context": context[:200],
            "ts": int(time.time()),
        }
        # Deduplicate by name
        self._data["tools"] = [t for t in self._data["tools"] if t.get("name") != tool.name]
        self._data["tools"].append(entry)
        self._data["tools"] = self._data["tools"][-20:]  # keep recent 20
        self._save()
        logger.info("playbook_tool_saved", name=tool.name)

    def get_context_for_mutation(self, top_n: int = 5) -> str:
        """Format playbook context for injection into mutation LLM prompts.

        This is the key ACE 'Emit' step — give the LLM history of what worked.
        """
        lines = ["## Playbook Context (what worked / what didn't in previous generations)"]

        helpful = self._data["helpful"][:top_n]
        if helpful:
            lines.append("\n### Previously Helpful Strategies:")
            for h in helpful:
                lines.append(f"- [{h['source']}, delta={h.get('delta', 0):+.3f}] {h['strategy']}")

        harmful = self._data["harmful"][-3:]
        if harmful:
            lines.append("\n### Previously Harmful (avoid these):")
            for h in harmful:
                lines.append(f"- [{h['source']}] {h['strategy']}")

        tools = self._data["tools"][-3:]
        if tools:
            lines.append("\n### Available Synthesized Tools:")
            for t in tools:
                lines.append(f"- {t['name']}: {t['description']}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def stats(self) -> dict:
        return {
            "helpful_count": len(self._data["helpful"]),
            "harmful_count": len(self._data["harmful"]),
            "tools_count": len(self._data["tools"]),
        }
