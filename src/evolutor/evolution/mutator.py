"""Mutation generation for SWE-bench agent evolution.

Uses DGM-style diagnosis: analyze failure logs, choose one of 5 targeted
mutation types, output the complete modified seed_agent.py.
"""
from __future__ import annotations

import ast
import os
import re
from enum import Enum

import anthropic

import structlog

logger = structlog.get_logger()


class MutationType(str, Enum):
    improve_system_prompt = "improve_system_prompt"
    add_tool_template = "add_tool_template"
    improve_reflection = "improve_reflection"
    add_workflow_hint = "add_workflow_hint"
    optimize_parameters = "optimize_parameters"


DIAGNOSIS_PROMPT = """You are an expert at improving AI coding agents for SWE-bench.

Here is the current coding agent (seed_agent.py):

```python
{agent_code}
```

The agent was evaluated on SWE-bench tasks and produced these failures:

{failed_task_logs}

Analyze the failures and output ONE targeted improvement. Choose the mutation type
that best addresses the root cause.

Available mutation types:
- improve_system_prompt: Agent doesn't attempt to solve / exits early / misunderstands task
- add_tool_template: Agent struggles with file editing / code search operations
- improve_reflection: Agent loops without progress / repeats same failed actions
- add_workflow_hint: Agent uses wrong approach for the task type
- optimize_parameters: Agent times out / uses too many steps without solving

Output your response with these EXACT sections:

MUTATION_TYPE: <one of the 5 types above>

ANALYSIS: <root cause of failures — be specific>

PLAN: <exact change to make — which section, what to add/change>

CODE:
===FILE: src/evolutor/swebench/seed_agent.py===
<complete modified seed_agent.py — the ENTIRE file, not a diff>
===END===

IMPORTANT:
- Output the ENTIRE seed_agent.py file in the CODE section
- Keep the EVOLVABLE SECTION markers intact
- Make exactly one focused change
- Do not use placeholders — output real, runnable Python code
"""


class Mutator:
    """Generate LLM-powered mutations of the seed agent."""

    def extract_code_from_response(self, text: str, fallback_code: str = "") -> str:
        """Extract Python code from LLM response text.

        Tries three formats in order:
        1. ===FILE: path===\\ncontent\\n===END=== markers (preferred)
        2. Markdown ```python ... ``` code blocks
        3. Raw Python detection (lines starting with import/def/class)

        Returns fallback_code if nothing found — never returns empty string.
        """
        # Format 1: marker-based (battle-tested)
        marker_pattern = re.compile(
            r"===FILE:\s*(.+?)===\n(.*?)===END===", re.DOTALL
        )
        matches = marker_pattern.findall(text)
        if matches:
            path, content = matches[0]  # Take first match
            content = content.strip()
            # Strip markdown fences if model wrapped content inside markers
            if content.startswith("```python"):
                content = content[len("```python"):].lstrip("\n")
            elif content.startswith("```"):
                content = content[3:].lstrip("\n")
            if content.endswith("```"):
                content = content[:-3].rstrip("\n")
            if content.strip():
                return content

        # Format 2: markdown code blocks
        md_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
        md_matches = md_pattern.findall(text)
        if md_matches:
            content = md_matches[0].strip()
            if content:
                return content

        # Also try ``` without language specifier
        md_bare = re.compile(r"```\n(.*?)```", re.DOTALL)
        bare_matches = md_bare.findall(text)
        if bare_matches:
            for candidate in bare_matches:
                candidate = candidate.strip()
                if any(kw in candidate for kw in ("def ", "import ", "class ")):
                    return candidate

        # Format 3: raw Python detection
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ", "def ", "class ", '"""')):
                candidate = "\n".join(lines[i:]).strip()
                if candidate:
                    return candidate

        # Last resort: return fallback
        logger.warning("extract_code_fallback", text_len=len(text))
        return fallback_code or text.strip()

    def select_mutation_type(self, failure_text: str) -> str:
        """Heuristic: pick mutation type from failure text keywords."""
        t = failure_text.lower()
        if "exit" in t or "step 0" in t:
            return "improve_system_prompt"
        if "loop" in t or "repeat" in t:
            return "improve_reflection"
        if "timeout" in t or "timed out" in t:
            return "optimize_parameters"
        return "improve_system_prompt"

    def diagnose_and_mutate(
        self,
        parent_code: str,
        failed_task_logs: str,
    ) -> tuple[str, str, str]:
        """LLM-powered mutation with structured diagnosis.

        Returns (child_code, mutation_type_str, description_str).
        Falls back to parent_code on syntax errors or LLM failures.
        """
        prompt = DIAGNOSIS_PROMPT.format(
            agent_code=parent_code,
            failed_task_logs=failed_task_logs[:50000],
        )

        client = anthropic.Anthropic()
        model = os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text

            # Parse mutation type
            mutation_type_str = self.select_mutation_type(failed_task_logs)
            for line in text.splitlines():
                if line.startswith("MUTATION_TYPE:"):
                    mutation_type_str = line.split(":", 1)[1].strip()
                    break

            # Parse analysis/description
            description = ""
            for line in text.splitlines():
                if line.startswith("ANALYSIS:"):
                    description = line.split(":", 1)[1].strip()
                    break

            # Extract code
            child_code = self.extract_code_from_response(text, fallback_code=parent_code)

            # Validate extracted code with ast.parse
            try:
                ast.parse(child_code)
            except SyntaxError:
                logger.warning("mutation_syntax_error", keeping="parent")
                return parent_code, "optimize_parameters", "syntax error in mutation, keeping parent"

            logger.info("mutation_ok", mut_type=mutation_type_str, code_len=len(child_code))
            return child_code, mutation_type_str, description

        except Exception as e:
            logger.error("diagnose_and_mutate_error", error=str(e))
            return parent_code, "optimize_parameters", f"mutation failed: {e}"

    def mutate(
        self,
        parent_code: str,
        failed_task_logs: str,
        mutation_type: MutationType | None = None,
    ) -> tuple[str, str]:
        """Call LLM to generate a mutated agent. Returns (child_code, mutation_description)."""
        import anthropic

        prompt = DIAGNOSIS_PROMPT.format(
            agent_code=parent_code,
            failed_task_logs=failed_task_logs[:30000],
        )

        client = anthropic.Anthropic()
        model = os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text

            # Extract mutation type from response
            mut_type = "unknown"
            for line in text.splitlines():
                if line.startswith("MUTATION_TYPE:"):
                    mut_type = line.split(":", 1)[1].strip()
                    break

            # Extract analysis
            analysis = ""
            in_analysis = False
            for line in text.splitlines():
                if line.startswith("ANALYSIS:"):
                    analysis = line.split(":", 1)[1].strip()
                    in_analysis = True
                elif line.startswith(("PLAN:", "CODE:", "MUTATION_TYPE:")):
                    in_analysis = False
                elif in_analysis:
                    analysis += " " + line.strip()

            # Extract code
            child_code = self.extract_code_from_response(text, fallback_code=parent_code)
            description = f"{mut_type}: {analysis[:200]}"

            logger.info("mutation_generated", mut_type=mut_type, code_len=len(child_code))
            return child_code, description

        except Exception as e:
            logger.error("mutation_llm_error", error=str(e))
            return parent_code, f"mutation_failed: {str(e)}"
