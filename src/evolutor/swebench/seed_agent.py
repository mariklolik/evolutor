"""
Evolutor Seed Agent — Live-SWE-agent pattern with evolvable sections.

The evolution loop can modify:
  - SYSTEM_PROMPT
  - REFLECTION_PROMPT
  - TOOL_TEMPLATES (reusable tool patterns from past generations)
  - WORKFLOW_HINTS
  - MAX_STEPS, STEP_TIMEOUT settings

The evolution loop CANNOT modify:
  - The Anthropic API call format
  - The bash execution mechanism
  - The git diff extraction
  - This comment block
"""

import anthropic
import subprocess
import os
import json

# ===== EVOLVABLE SECTION: System Prompt =====
SYSTEM_PROMPT = """You are a helpful assistant that can interact with a computer \
shell to solve programming tasks. You have access to a bash tool.

You can also CREATE CUSTOM TOOLS as Python scripts when they would help you \
solve the current task more effectively. To create a tool, write a Python \
script to a file and make it executable.

GUIDELINES:
- Start by understanding the issue: read relevant files, search for related code
- Reproduce the bug if possible
- Make minimal, targeted changes
- Test your changes
- When done, the patch will be extracted via git diff"""

# ===== EVOLVABLE SECTION: Reflection Prompt =====
REFLECTION_PROMPT = """Reflect on your previous actions and decide:
1. Are you making progress toward solving the issue?
2. Would creating a custom tool (Python script) help you work more effectively?
3. What should your next action be?

Note: creating reusable tools for code search, editing, or analysis \
can dramatically improve your efficiency."""

# ===== EVOLVABLE SECTION: Tool Templates =====
TOOL_TEMPLATES = ""

# ===== EVOLVABLE SECTION: Workflow Hints =====
WORKFLOW_HINTS = ""

INSTANCE_TEMPLATE = """I have uploaded a Python code repository in {repo_dir}.
Help solve the following problem:

<problem_statement>
{problem_statement}
</problem_statement>

{workflow_hints}

WORKFLOW:
1. Read and understand the issue
2. Explore the relevant code
3. Create any tools that would help (optional but recommended)
4. Make targeted changes to fix the issue
5. Test your changes
6. Verify with git diff"""

BASH_TOOL = {
    "name": "bash",
    "description": "Execute a bash command in the repository.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute"
            }
        },
        "required": ["command"]
    }
}

# ===== EVOLVABLE SECTION: Step limit and timeout =====
MAX_STEPS = 50
STEP_TIMEOUT = 30


def execute_bash(command: str, cwd: str, timeout: int = STEP_TIMEOUT) -> str:
    """Run bash command, return stdout+stderr truncated to 10000 chars."""
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
        )
        output = result.stdout + result.stderr
        if len(output) > 10000:
            output = output[:5000] + "\n... truncated ...\n" + output[-5000:]
        if not output.strip():
            output = "(no output)"
        return f"Exit code: {result.returncode}\n{output}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error: {str(e)}"


def solve_task(
    problem_statement: str,
    repo_dir: str,
    model: str | None = None,
) -> str:
    """Solve a SWE-bench task. Returns git diff patch."""
    model = model or os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic()

    system = SYSTEM_PROMPT
    if TOOL_TEMPLATES.strip():
        system += f"\n\nREUSABLE TOOL TEMPLATES:\n{TOOL_TEMPLATES}"

    messages = [{
        "role": "user",
        "content": INSTANCE_TEMPLATE.format(
            repo_dir=repo_dir,
            problem_statement=problem_statement,
            workflow_hints=WORKFLOW_HINTS,
        )
    }]

    for step in range(MAX_STEPS):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            tools=[BASH_TOOL],
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            break

        tool_results = []
        for tool_use in tool_uses:
            if tool_use.name == "bash":
                command = tool_use.input.get("command", "echo 'no command'")
                output = execute_bash(command, cwd=repo_dir)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": output,
                })
        messages.append({"role": "user", "content": tool_results})

        # Live-SWE-agent reflection: inject every N steps
        if step > 0 and step % 5 == 0 and REFLECTION_PROMPT:
            messages.append({
                "role": "user",
                "content": REFLECTION_PROMPT
            })

    # Extract patch
    patch = execute_bash("git diff", cwd=repo_dir, timeout=10)
    return patch


def solve(
    issue: str,
    repo_root: str,
    model: str | None = None,
    max_steps: int | None = None,
) -> dict:
    """Backward-compatible wrapper around solve_task."""
    model = model or os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")
    patch = solve_task(issue, repo_root, model=model)
    success = bool(patch and "Exit code" not in patch and patch.strip().startswith("diff"))
    return {
        "success": success,
        "summary": "",
        "steps": 0,
        "files_changed": [],
        "patch": patch,
    }
