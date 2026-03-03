"""Tool store — save and load generated tools."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger()


class ToolStore:
    """Persistent storage for generated tools."""

    def __init__(self, store_dir: str = ".evolutor/tools") -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, code: str, version: int = 1) -> str:
        tool_dir = self.store_dir / name
        tool_dir.mkdir(parents=True, exist_ok=True)
        filepath = tool_dir / f"v{version}.py"
        filepath.write_text(code)
        # Write metadata
        meta = tool_dir / "meta.txt"
        meta.write_text(f"name={name}\nversion={version}\nupdated={datetime.now(timezone.utc).isoformat()}\n")
        logger.info("tool_saved", name=name, version=version)
        return str(filepath)

    def load(self, name: str, version: int | None = None) -> str | None:
        tool_dir = self.store_dir / name
        if not tool_dir.exists():
            return None
        if version:
            filepath = tool_dir / f"v{version}.py"
        else:
            # Load latest
            files = sorted(tool_dir.glob("v*.py"))
            if not files:
                return None
            filepath = files[-1]
        return filepath.read_text() if filepath.exists() else None

    def list_tools(self) -> list[str]:
        if not self.store_dir.exists():
            return []
        return [d.name for d in self.store_dir.iterdir() if d.is_dir()]

    def get_version_history(self, name: str) -> list[int]:
        tool_dir = self.store_dir / name
        if not tool_dir.exists():
            return []
        versions = []
        for f in tool_dir.glob("v*.py"):
            try:
                v = int(f.stem[1:])
                versions.append(v)
            except ValueError:
                continue
        return sorted(versions)
