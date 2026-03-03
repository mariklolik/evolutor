"""Tool search for finding the right tool for a task."""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from evolutor.tools.mcp.registry import MCPRegistry, ToolSchema

logger = structlog.get_logger()


class ToolMatch(BaseModel):
    tool: ToolSchema
    relevance_score: float = 0.0


class ToolSearch:
    """Search for tools matching a task description."""

    def __init__(self, registry: MCPRegistry) -> None:
        self.registry = registry

    def search(self, query: str, top_k: int = 5) -> list[ToolMatch]:
        tools = self.registry.list_all_tools()
        query_lower = query.lower()
        matches = []
        for tool in tools:
            score = 0.0
            if query_lower in tool.name.lower():
                score += 1.0
            if query_lower in tool.description.lower():
                score += 0.5
            if score > 0:
                matches.append(ToolMatch(tool=tool, relevance_score=score))
        return sorted(matches, key=lambda m: m.relevance_score, reverse=True)[:top_k]

    def get_tool_for_task(self, task_description: str) -> ToolMatch | None:
        matches = self.search(task_description, top_k=1)
        return matches[0] if matches else None
