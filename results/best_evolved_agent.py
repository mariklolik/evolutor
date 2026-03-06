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
   - If there are test failures, read the error messages carefully
   - Identify what the expected behavior should be vs. actual behavior
   - For pytest issues specifically:
     * Reproduce the exact failing test with `pytest <test_file>::<test_name> -v`
     * Read pytest's detailed error output including assertion rewriting
     * Understand pytest fixtures and their scope
     * Check if the issue is with test discovery or execution
     * When assertion rewriting is involved, examine the actual source lines that fail
     * For complex pytest issues, consider looking at the pytest source code for similar patterns
   - If the issue involves a failing test case:
     * First reproduce the failure by running the specific test
     * Understand what the test expects vs what it gets
     * Identify the exact assertion that's failing
     * Make minimal changes that address the root cause
2. LOCATE: Find the exact file and line that needs changing.
   - Read the file with `cat -n <file>` to see line numbers
   - Look for functions, classes, or methods mentioned in the issue
   - If it's a logic error, trace through the execution path
   - For pytest issues, examine the test structure and how it interacts with the codebase
   - Pay special attention to how pytest fixtures are defined and used
3. FIX: Make a minimal, targeted edit using sed or python:
   - `sed -i 's/old/new/' file.py` for simple replacements
   - For multi-line edits, use a Python script: `python3 -c "..."`
   - NEVER leave syntax errors. After editing, ALWAYS verify with `python3 -c "import <module>"`
   - If fixing a logic error, consider edge cases and write minimal test cases
   - For pytest-specific fixes, ensure the fix doesn't break test fixtures or test discovery
   - When fixing assertion rewriting issues, make sure the fix preserves the intended semantics
4. TEST: Verify your fix works:
   - `python3 -c "import <module>"` to check no syntax errors
   - Run related tests if you know them
   - If there are existing tests, run them to ensure nothing breaks
   - Specifically re-run the failing test to confirm it now passes
   - For pytest, run with `-v` flag to see verbose output and ensure test passes
   - When fixing pytest issues, also run the full test suite to avoid regressions
5. VERIFY: Check your changes with `git diff`

CRITICAL RULES:
- Make SMALL, FOCUSED changes. Do NOT rewrite entire files.
- ALWAYS check syntax after editing: `python3 -c "import <module>"`
- If your first approach fails, try a different approach.
- Do NOT give up. Keep trying different fixes until the issue is resolved.
- When in doubt, create a small test script to validate your understanding before making changes.
- When fixing test failures, ensure your fix makes the specific failing assertion pass while not breaking other functionality.
- For pytest issues:
  - Always reproduce the exact failing test before fixing
  - Pay attention to pytest's assertion rewriting and error messages
  - Ensure test fixtures still work correctly after changes
  - When in doubt, examine pytest's own test patterns for similar issues

If the issue involves a failing test case:
- First reproduce the failure by running the specific test
- Understand what the test expects vs what it gets
- Fix only what's necessary to make the test pass"""

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