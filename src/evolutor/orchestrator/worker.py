"""Worker node — executes subtasks using LLM tool-use agentic loop."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.types.task import TaskResult, TaskStatus

logger = structlog.get_logger()

_MAX_ROUNDS = 20

_TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the project. Path is relative to project root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
                "content": {"type": "string", "description": "Full file content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_bash",
        "description": "Run a bash command in the project root. Returns stdout+stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 60)",
                    "default": 60,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories inside a path (relative to project root).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to project root (default: .)",
                    "default": ".",
                },
            },
        },
    },
]

_SYSTEM = (
    "You are an expert software engineer implementing tasks autonomously. "
    "You have tools to read files, write files, run bash commands, and list directories. "
    "All file paths are relative to the project root. "
    "Implement the task completely and correctly. "
    "When done, write a brief summary of what you implemented."
)


def _project_root() -> Path:
    return Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()


def _client():
    import anthropic

    return anthropic.Anthropic(
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )


def _model() -> str:
    return os.environ.get("EVOLUTOR_MODEL", "anthropic/claude-sonnet-4.6")


def _execute_tool(name: str, inputs: dict[str, Any], root: Path) -> str:
    try:
        if name == "read_file":
            path = root / inputs["path"]
            if not path.exists():
                return f"File not found: {inputs['path']}"
            text = path.read_text(errors="replace")
            return text[:16000] if len(text) > 16000 else text

        elif name == "write_file":
            path = root / inputs["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(inputs["content"])
            return f"Wrote {len(inputs['content'])} bytes to {inputs['path']}"

        elif name == "run_bash":
            proc = subprocess.run(
                inputs["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=inputs.get("timeout", 60),
                cwd=root,
            )
            output = proc.stdout + proc.stderr
            if len(output) > 8000:
                output = output[:8000] + "\n... (truncated)"
            return output or "(no output)"

        elif name == "list_files":
            path = root / inputs.get("path", ".")
            if not path.exists():
                return f"Directory not found: {inputs.get('path', '.')}"
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
            lines = []
            for p in entries[:200]:
                prefix = "  " if p.is_file() else "D "
                lines.append(f"{prefix}{p.name}")
            return "\n".join(lines) or "(empty)"

        else:
            return f"Unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {inputs.get('timeout', 60)}s"
    except Exception as e:
        return f"Tool error ({name}): {e}"


def _run_worker(subtask_title: str, subtask_description: str) -> tuple[bool, str, list[str]]:
    """Synchronous agentic loop. Returns (success, summary, files_changed)."""
    client = _client()
    root = _project_root()

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Task: {subtask_title}\n\n"
                f"Description: {subtask_description}\n\n"
                f"Project root: {root}\n\n"
                "Implement this task completely."
            ),
        }
    ]

    files_changed: list[str] = []
    summary = ""

    for round_num in range(_MAX_ROUNDS):
        resp = client.messages.create(
            model=_model(),
            max_tokens=4096,
            system=_SYSTEM,
            tools=_TOOLS,  # type: ignore[arg-type]
            messages=messages,  # type: ignore[arg-type]
        )

        # Separate tool uses and text blocks
        tool_uses = []
        texts = []
        for block in resp.content:
            block_type = getattr(block, "type", None)
            if block_type == "tool_use":
                tool_uses.append(block)
            elif block_type == "text":
                texts.append(block.text)

        # Append assistant turn
        messages.append({"role": "assistant", "content": resp.content})  # type: ignore[arg-type]

        if texts:
            summary = texts[-1]

        if not tool_uses:
            # LLM finished without calling any tool — we're done
            break

        # Execute tools and collect results
        tool_results = []
        for tu in tool_uses:
            result_text = _execute_tool(tu.name, tu.input, root)
            logger.info("worker_tool", tool=tu.name, keys=list(tu.input.keys()), round=round_num)
            if tu.name == "write_file":
                files_changed.append(str(tu.input.get("path", "")))
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result_text,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return True, summary or "Task completed", files_changed


class WorkerNode:
    """Executes the current subtask using LLM tool-use agentic loop."""

    async def __call__(self, state: OrchestratorState) -> OrchestratorState:
        plan = state.get("plan", [])
        idx = state.get("current_subtask_index", 0)

        if idx >= len(plan):
            state["should_continue"] = False
            return state

        subtask = plan[idx]
        subtask.status = TaskStatus.in_progress
        logger.info("worker_executing", subtask=subtask.title, index=idx)

        try:
            success, summary, files_changed = await asyncio.to_thread(
                _run_worker, subtask.title, subtask.description
            )
            result = TaskResult(
                task_id=subtask.id,
                success=success,
                files_changed=files_changed,
                metrics={"summary": summary},
            )
            subtask.status = TaskStatus.completed
        except Exception as e:
            logger.error("worker_error", subtask=subtask.title, error=str(e), exc_info=True)
            result = TaskResult(task_id=subtask.id, success=False, error=str(e))
            subtask.status = TaskStatus.failed

        results = state.get("results", [])
        results.append(result)
        state["results"] = results
        state["current_subtask_index"] = idx + 1

        return state
