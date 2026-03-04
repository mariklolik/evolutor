"""RuntimeToolSynthesizer — synthesize new tools at runtime when agent is stuck.

Based on Live-SWE-agent §3.2: step-reflection decision → tool code generation → registration.
Key differences from Live-SWE-agent:
1. Safety kernel validates every tool before registration (DGM reward-hacking prevention)
2. Successful tools saved to persistent playbook store (cross-session learning)
3. Tools fed back into offline evolution archive
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class SynthesizedTool:
    name: str
    description: str
    code: str
    input_schema: dict[str, Any]
    synthesized_for: str  # task context that triggered synthesis


class RuntimeToolSynthesizer:
    """Synthesize Python tools at runtime when agent encounters recurring operations."""

    REFLECTION_PROMPT = (
        "Reflect on the previous tool result and trajectory. "
        "Should you create a custom tool to handle this type of operation more efficiently? "
        "A custom tool is worth creating if: (1) you'll need this operation 3+ more times, "
        "(2) it would reduce context window usage, (3) bash pipelines for this are complex.\n\n"
        "If YES: write the tool as:\n"
        "<tool_synthesis>\n"
        "name: tool_name\n"
        "description: what it does\n"
        "code: def tool_name(args): ...\n"
        "</tool_synthesis>\n\n"
        "If NO: just continue with your next action."
    )

    def __init__(self, playbook_store=None):
        self.playbook_store = playbook_store
        self._synthesized: dict[str, SynthesizedTool] = {}

    def should_reflect(self, step: int, tool_result: str) -> bool:
        """Decide if we should inject step-reflection (every 3 steps or after errors)."""
        if step % 3 == 0:
            return True
        if "error" in tool_result.lower() or "not found" in tool_result.lower():
            return True
        return False

    def parse_synthesis_request(self, llm_response: str) -> SynthesizedTool | None:
        """Extract tool synthesis from LLM response if present."""
        match = re.search(r"<tool_synthesis>(.*?)</tool_synthesis>", llm_response, re.DOTALL)
        if not match:
            return None

        content = match.group(1).strip()
        lines = content.split("\n")
        fields: dict[str, str] = {}
        current_field = None
        current_content: list[str] = []

        for line in lines:
            if line.startswith("name:"):
                fields["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                fields["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("code:"):
                current_field = "code"
                current_content = [line.split(":", 1)[1]]
            elif current_field == "code":
                current_content.append(line)

        if current_field == "code":
            fields["code"] = "\n".join(current_content)

        if not all(k in fields for k in ("name", "description", "code")):
            return None

        return SynthesizedTool(
            name=fields["name"],
            description=fields["description"],
            code=fields["code"],
            input_schema={"type": "object", "properties": {}, "required": []},
            synthesized_for="",
        )

    def validate_tool(self, tool: SynthesizedTool) -> bool:
        """Safety kernel validation — prevent dangerous tool code."""
        dangerous_patterns = [
            r"rm\s+-rf",
            r"os\.system",
            r"subprocess.*shell=True.*rm",
            r"__import__\(['\"]os['\"]",
            r"eval\(",
            r"exec\(",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, tool.code):
                logger.warning("tool_synthesis_rejected_unsafe", pattern=pattern, tool=tool.name)
                return False

        # Validate Python syntax
        try:
            ast.parse(tool.code)
        except SyntaxError as e:
            logger.warning("tool_synthesis_rejected_syntax", error=str(e), tool=tool.name)
            return False

        return True

    def register_tool(self, tool: SynthesizedTool, task_context: str = "") -> dict | None:
        """Register tool for use in agent loop. Returns tool_use format dict."""
        tool.synthesized_for = task_context

        if not self.validate_tool(tool):
            return None

        self._synthesized[tool.name] = tool

        # Persist to playbook store for cross-session learning
        if self.playbook_store:
            try:
                self.playbook_store.add_tool_pattern(tool, task_context)
            except Exception as e:
                logger.warning("tool_persist_failed", error=str(e))

        logger.info("tool_synthesized_registered", name=tool.name)

        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }

    def execute_synthesized_tool(self, name: str, inputs: dict, repo_root: Path) -> str:
        """Execute a previously synthesized tool."""
        tool = self._synthesized.get(name)
        if not tool:
            return f"Unknown synthesized tool: {name}"

        try:
            namespace: dict = {}
            exec(tool.code, namespace)  # noqa: S102
            fn = namespace.get(tool.name)
            if not fn:
                return f"Tool function '{tool.name}' not found in code"
            result = fn(**inputs)
            return str(result) if result is not None else "(no output)"
        except Exception as e:
            return f"Tool execution error: {e}"
