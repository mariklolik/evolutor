"""Repository map and context generation."""

from __future__ import annotations

from pathlib import Path

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class FileContext(BaseModel):
    file_path: str
    summary: str = ""
    relevance_score: float = 0.0
    symbols: list[str] = Field(default_factory=list)
    line_count: int = 0


class RepoMap:
    """Generate repository maps and relevant context."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root)

    def generate_map(self, extensions: list[str] | None = None) -> list[FileContext]:
        exts = extensions or [".py"]
        contexts = []
        for ext in exts:
            for p in sorted(self.project_root.rglob(f"*{ext}")):
                if ".git" in p.parts or "__pycache__" in p.parts or ".mypy_cache" in p.parts:
                    continue
                try:
                    content = p.read_text()
                    line_count = len(content.splitlines())
                    symbols = self._extract_symbols(content)
                    rel_path = str(p.relative_to(self.project_root))
                    contexts.append(FileContext(
                        file_path=rel_path,
                        summary=f"{len(symbols)} symbols, {line_count} lines",
                        symbols=symbols,
                        line_count=line_count,
                    ))
                except Exception:
                    continue
        return contexts

    def get_relevant_context(self, query: str, top_k: int = 10) -> list[FileContext]:
        all_files = self.generate_map()
        query_lower = query.lower()
        for f in all_files:
            score = 0.0
            for sym in f.symbols:
                if query_lower in sym.lower():
                    score += 1.0
            if query_lower in f.file_path.lower():
                score += 0.5
            f.relevance_score = score
        return sorted(all_files, key=lambda x: x.relevance_score, reverse=True)[:top_k]

    def get_file_summary(self, file_path: str) -> FileContext:
        full_path = self.project_root / file_path
        try:
            content = full_path.read_text()
            line_count = len(content.splitlines())
            symbols = self._extract_symbols(content)
            return FileContext(
                file_path=file_path,
                summary=f"{len(symbols)} symbols, {line_count} lines",
                symbols=symbols,
                line_count=line_count,
            )
        except Exception as e:
            return FileContext(file_path=file_path, summary=f"Error: {e}")

    def rank_files_by_relevance(self, query: str) -> list[str]:
        contexts = self.get_relevant_context(query, top_k=50)
        return [c.file_path for c in contexts if c.relevance_score > 0]

    @staticmethod
    def _extract_symbols(content: str) -> list[str]:
        import re
        symbols = []
        for line in content.splitlines():
            m = re.match(r"^(?:class|def)\s+(\w+)", line.strip())
            if m:
                symbols.append(m.group(1))
        return symbols
