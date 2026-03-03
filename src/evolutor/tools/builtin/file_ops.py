"""File operations tool."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import structlog

logger = structlog.get_logger()


class FileOpsTool:
    """Tool for file system operations."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root)

    def read_file(self, path: str) -> str:
        full = self.project_root / path
        return full.read_text()

    def write_file(self, path: str, content: str) -> None:
        full = self.project_root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    def edit_file(self, path: str, old_text: str, new_text: str) -> bool:
        full = self.project_root / path
        content = full.read_text()
        if old_text not in content:
            return False
        content = content.replace(old_text, new_text, 1)
        full.write_text(content)
        return True

    def search_files(self, pattern: str, path: str = ".") -> list[dict]:
        results = []
        search_dir = self.project_root / path
        for p in search_dir.rglob("*.py"):
            if "__pycache__" in p.parts or ".git" in p.parts:
                continue
            try:
                content = p.read_text()
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pattern, line):
                        results.append({
                            "file": str(p.relative_to(self.project_root)),
                            "line": i,
                            "text": line.strip(),
                        })
            except Exception:
                continue
        return results

    def glob_files(self, pattern: str, path: str = ".") -> list[str]:
        search_dir = self.project_root / path
        return [
            str(p.relative_to(self.project_root))
            for p in search_dir.rglob(pattern)
            if "__pycache__" not in p.parts and ".git" not in p.parts
        ]

    @staticmethod
    def get_schema() -> dict:
        return {
            "name": "file_ops",
            "description": "File system operations",
            "functions": {
                "read_file": {"params": {"path": "str"}, "returns": "str"},
                "write_file": {"params": {"path": "str", "content": "str"}, "returns": "None"},
                "edit_file": {"params": {"path": "str", "old_text": "str", "new_text": "str"}, "returns": "bool"},
                "search_files": {"params": {"pattern": "str", "path": "str"}, "returns": "list[dict]"},
                "glob_files": {"params": {"pattern": "str", "path": "str"}, "returns": "list[str]"},
            },
        }
