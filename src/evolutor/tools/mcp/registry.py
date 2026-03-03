"""MCP (Model Context Protocol) server registry."""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ToolSchema(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    server_name: str = ""


class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class MCPServer(BaseModel):
    config: MCPServerConfig
    tools: list[ToolSchema] = Field(default_factory=list)
    is_running: bool = False


class MCPRegistry:
    """Registry for MCP servers and their tools."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServer] = {}

    def register_server(self, config: MCPServerConfig) -> MCPServer:
        server = MCPServer(config=config)
        self._servers[config.name] = server
        logger.info("mcp_server_registered", name=config.name)
        return server

    def discover_tools(self, server_name: str) -> list[ToolSchema]:
        server = self._servers.get(server_name)
        if not server:
            return []
        # In production, this would communicate with the MCP server
        return server.tools

    async def call_tool(self, server_name: str, tool_name: str, args: dict) -> Any:
        server = self._servers.get(server_name)
        if not server:
            raise ValueError(f"Server {server_name} not registered")
        # Placeholder for MCP protocol call
        logger.info("mcp_tool_call", server=server_name, tool=tool_name)
        return {"result": "mock", "tool": tool_name, "args": args}

    def list_all_tools(self) -> list[ToolSchema]:
        tools = []
        for server in self._servers.values():
            tools.extend(server.tools)
        return tools
