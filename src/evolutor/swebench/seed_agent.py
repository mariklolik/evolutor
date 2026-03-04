"""Seed coding agent — mini-SWE-agent scaffold + Live-SWE-agent step-reflection.

This is the minimal agent that the evolution loop improves over generations.
Design principles (from paper analysis):
- Radical simplicity: ~150 lines, easy for LLM to understand and modify
- 4 tools (not bash-only): bash, view_file, edit_file, search_code
- THOUGHT\\nACTION format (better than XML/JSON for reasoning)
- Step-reflection after each action (Live-SWE-agent §3.2)
- Cross-LLM: planner uses smaller model than executor (SAGE insight)
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# ============================================================
# TOOL DEFINITIONS (anthropic tool_use format)
# ============================================================
TOOLS = [
    {
        "name": "bash",
        "description": (
            "Run a bash command in the repository root. Returns stdout+stderr. "
            "Use for: running tests, installing packages, git operations, compiling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Bash command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)", "default": 60},
            },
            "required": ["cmd"],
        },
    },
    {
        "name": "view_file",
        "description": (
            "Read a file with line numbers. Essential for precise editing. "
            "Use start/end to read specific sections of large files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"},
                "start": {"type": "integer", "description": "Start line (1-indexed, optional)"},
                "end": {"type": "integer", "description": "End line (inclusive, optional)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace exact string in a file. Surgical edit — does NOT rewrite entire file. "
            "old_str must match exactly (including indentation). "
            "Use view_file first to get exact content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"},
                "old_str": {"type": "string", "description": "Exact string to replace (must be unique in file)"},
                "new_str": {"type": "string", "description": "New string to insert in place of old_str"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
    {
        "name": "search_code",
        "description": (
            "Search codebase with regex using ripgrep. Returns matching lines with file:line context. "
            "Automatically excludes __pycache__, .git, node_modules, *.pyc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search"},
                "path": {"type": "string", "description": "Path to search in (default: repo root)"},
                "file_pattern": {"type": "string", "description": "File glob filter e.g. '*.py'"},
            },
            "required": ["pattern"],
        },
    },
]

# ============================================================
# SYSTEM PROMPT (SWE-agent style: capability + format guidance)
# ============================================================
SYSTEM_PROMPT = """You are an expert software engineer solving GitHub issues autonomously.

You have 4 tools:
- bash: run commands, tests, git operations
- view_file: read files with line numbers (always use this before editing)
- edit_file: surgical string replacement (exact match required)
- search_code: ripgrep search across codebase

## Format
Always respond with:
THOUGHT: [your reasoning about what to do next]
ACTION: [tool call]

## Strategy
1. Start by understanding the issue and the codebase structure
2. Use search_code to find relevant files/functions
3. Use view_file to read code before editing
4. Make minimal targeted changes — don't rewrite large sections
5. Run tests after changes to validate your fix
6. Submit only when tests pass

## Step-Reflection (Live-SWE-agent pattern)
After each tool result, reflect briefly:
- Did this reveal what I needed?
- Should I create a helper script for this recurring operation?
- Am I making progress or going in circles?"""

STEP_REFLECT_SUFFIX = (
    "\n\nBriefly reflect: What did this result tell you? "
    "Are you making progress? What's your next action?"
)


# ============================================================
# TOOL EXECUTION
# ============================================================
def _execute_tool(name: str, inputs: dict[str, Any], root: Path) -> str:
    try:
        if name == "bash":
            result = subprocess.run(
                inputs["cmd"], shell=True, capture_output=True, text=True,
                timeout=inputs.get("timeout", 60), cwd=root,
            )
            out = result.stdout + result.stderr
            return (out[:8000] + "\n...(truncated)") if len(out) > 8000 else out or "(no output)"

        elif name == "view_file":
            p = root / inputs["path"]
            if not p.exists():
                return f"File not found: {inputs['path']}"
            lines = p.read_text(errors="replace").splitlines()
            start = max(0, inputs.get("start", 1) - 1)
            end = inputs.get("end", len(lines))
            selected = lines[start:end]
            numbered = [f"{start+i+1:4d} | {l}" for i, l in enumerate(selected)]
            return "\n".join(numbered)

        elif name == "edit_file":
            p = root / inputs["path"]
            if not p.exists():
                return f"File not found: {inputs['path']}"
            content = p.read_text()
            old_str = inputs["old_str"]
            new_str = inputs["new_str"]
            if old_str not in content:
                return f"ERROR: old_str not found in {inputs['path']}. Use view_file to check exact content."
            count = content.count(old_str)
            if count > 1:
                return f"ERROR: old_str appears {count} times. Make it more specific to be unique."
            p.write_text(content.replace(old_str, new_str, 1))
            return f"OK: replaced in {inputs['path']}"

        elif name == "search_code":
            pattern = inputs["pattern"]
            search_path = str(root / inputs.get("path", "."))
            file_filter = inputs.get("file_pattern", "")
            cmd = ["rg", "--line-number", "--color=never",
                   "--glob=!__pycache__", "--glob=!*.pyc", "--glob=!.git",
                   "--glob=!node_modules"]
            if file_filter:
                cmd += ["-g", file_filter]
            cmd += [pattern, search_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = result.stdout
            return (out[:6000] + "\n...(truncated)") if len(out) > 6000 else out or "(no matches)"

        return f"Unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Tool error ({name}): {e}"


# ============================================================
# MAIN AGENT LOOP
# ============================================================
def solve(
    issue: str,
    repo_root: Path,
    model: str | None = None,
    max_steps: int = 50,
) -> dict[str, Any]:
    """Solve a GitHub issue by autonomously editing code.

    Returns: {"success": bool, "summary": str, "steps": int, "files_changed": list}
    """
    import anthropic

    model = model or os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic(
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "http://localhost:4000"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", "sk-local"),
    )

    messages: list[dict] = [{"role": "user", "content": f"Issue to solve:\n{issue}"}]
    files_changed: list[str] = []
    summary = ""
    format_errors = 0

    for step in range(max_steps):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore
                messages=messages,  # type: ignore
            )
        except Exception as e:
            logger.error("seed_agent_llm_error", step=step, error=str(e))
            break

        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        texts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]

        messages.append({"role": "assistant", "content": resp.content})  # type: ignore

        if texts:
            summary = texts[-1]

        if resp.stop_reason == "end_turn" and not tool_uses:
            logger.info("seed_agent_complete", step=step, reason="end_turn")
            return {"success": True, "summary": summary, "steps": step, "files_changed": files_changed}

        if not tool_uses:
            format_errors += 1
            if format_errors > 3:
                break
            messages.append({"role": "user", "content": "Please use a tool to continue solving the issue."})
            continue

        format_errors = 0
        tool_results = []
        for tc in tool_uses:
            result = _execute_tool(tc.name, tc.input, repo_root)
            logger.debug("seed_agent_tool", step=step, tool=tc.name)
            if tc.name == "edit_file" and "OK:" in result:
                path = tc.input.get("path", "")
                if path not in files_changed:
                    files_changed.append(path)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result + STEP_REFLECT_SUFFIX,
            })

        messages.append({"role": "user", "content": tool_results})

    return {"success": False, "summary": summary or "max steps reached", "steps": max_steps, "files_changed": files_changed}


if __name__ == "__main__":
    import sys
    issue = sys.argv[1] if len(sys.argv) > 1 else "Add a hello world test to tests/unit/"
    root = Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()
    result = solve(issue, root)
    print(result)
