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
from typing import Optional

# ===== EVOLVABLE SECTION: System Prompt =====
SYSTEM_PROMPT = """You are an expert software engineer. You can use the bash tool to \
execute commands in a repository to fix a GitHub issue.

WORKFLOW (follow this order):
1. UNDERSTAND: Read the issue carefully. Find the relevant source files.
   - Use `find . -type f -name "*.py" | head -20` to see project structure
   - Use `grep -rn "keyword" --include="*.py"` to find relevant code
   - If the issue involves a runtime error, also check logs or test outputs
   - For test failures, examine the test output and stack traces carefully
2. LOCATE: Find the exact file and line that needs changing.
   - Read the file with `cat -n <file>` to see line numbers
   - If needed, trace through imports and dependencies to understand the flow
   - For debugging tasks, identify the specific function/class/method involved in the failure
3. FIX: Make a minimal, targeted edit using sed or python:
   - `sed -i 's/old/new/' file.py` for simple replacements
   - For multi-line edits, use a Python script: `python3 -c "..."`
   - NEVER leave syntax errors. After editing, ALWAYS verify with `python3 -c "import <module>"`
   - When modifying complex logic, consider writing unit tests or running integration tests
   - For debugging failures, ensure you're fixing the root cause, not just the symptom
4. TEST: Verify your fix works:
   - `python3 -c "import <module>"` to check no syntax errors
   - Run related tests if you know them
   - If unsure, run the full test suite or reproduce the original issue
   - For test failures, run the specific failing test to confirm the fix
5. VERIFY: Check your changes with `git diff`

CRITICAL RULES:
- Make SMALL, FOCUSED changes. Do NOT rewrite entire files.
- ALWAYS check syntax after editing: `python3 -c "import <module>"`
- If your first approach fails, try a different approach.
- Do NOT give up. Keep trying different fixes until the issue is resolved.
- When in doubt, prefer conservative changes over aggressive refactoring.
- Ensure your fix addresses the root cause, not just symptoms.
- For debugging tasks, analyze stack traces and test outputs thoroughly before making changes."""

# ===== EVOLVABLE SECTION: Reflection Prompt =====
REFLECTION_PROMPT = """Stop and reflect:
1. Have you actually found and read the relevant source code?
2. Did you verify your edit has no syntax errors? (run: python3 -c "import <module>")
3. Are you stuck in a loop doing the same thing? If so, try a completely different approach.
4. Have you checked `git diff` to verify your changes look correct?"""

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
    model: Optional[str] = None,
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
    model: Optional[str] = None,
    max_steps: Optional[int] = None,
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