"""Mutation generation for code evolution."""

from __future__ import annotations

import random
from enum import Enum
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class MutationType(str, Enum):
    refactor = "refactor"
    optimize = "optimize"
    harden = "harden"
    simplify = "simplify"
    extend = "extend"
    test_improve = "test_improve"


class Mutation(BaseModel):
    mutation_type: MutationType
    description: str
    target_files: list[str] = Field(default_factory=list)
    prompt: str = ""


class Mutator:
    """Generate mutations for code evolution."""

    def generate_mutation(self, target_files: list[str], context: str = "") -> Mutation:
        mutation_type = self.select_mutation_type(context)
        prompts = {
            MutationType.refactor: "Refactor this code for better readability and maintainability.",
            MutationType.optimize: "Optimize this code for better performance.",
            MutationType.harden: "Add error handling and input validation.",
            MutationType.simplify: "Simplify this code by removing unnecessary complexity.",
            MutationType.extend: "Extend this code with useful new functionality.",
            MutationType.test_improve: "Add or improve tests for better coverage.",
        }
        return Mutation(
            mutation_type=mutation_type,
            description=f"{mutation_type.value} on {len(target_files)} file(s)",
            target_files=target_files,
            prompt=prompts[mutation_type],
        )

    def crossover(self, mutation_a: Mutation, mutation_b: Mutation) -> Mutation:
        target_files = list(set(mutation_a.target_files + mutation_b.target_files))
        return Mutation(
            mutation_type=random.choice([mutation_a.mutation_type, mutation_b.mutation_type]),
            description=f"crossover: {mutation_a.mutation_type.value} + {mutation_b.mutation_type.value}",
            target_files=target_files,
            prompt=f"{mutation_a.prompt}\n\nAdditionally: {mutation_b.prompt}",
        )

    def select_mutation_type(self, context: str = "") -> MutationType:
        """Heuristic mutation type selection based on context."""
        context_lower = context.lower()
        if "slow" in context_lower or "performance" in context_lower:
            return MutationType.optimize
        if "error" in context_lower or "crash" in context_lower:
            return MutationType.harden
        if "complex" in context_lower or "long" in context_lower:
            return MutationType.simplify
        if "coverage" in context_lower or "test" in context_lower:
            return MutationType.test_improve
        if "feature" in context_lower or "add" in context_lower:
            return MutationType.extend
        return random.choice(list(MutationType))

    async def apply_mutation(
        self, target_files: list[str], project_root: "Path", context: str = ""
    ) -> dict[str, str]:
        """Call LLM to generate real code changes. Returns {filepath: new_content}.

        Based on DGM self_improve_step.py pattern: give LLM full file content + failure context,
        get back modified files as JSON.
        """
        import os
        import json
        import re
        import anthropic
        from pathlib import Path

        mutation = self.generate_mutation(target_files, context)
        project_root = Path(project_root)

        # Read target files (skip >40KB files)
        file_contents: dict[str, str] = {}
        for f in target_files[:3]:
            p = project_root / f
            if p.exists() and p.stat().st_size < 40_000:
                file_contents[f] = p.read_text(errors="replace")

        if not file_contents:
            logger.warning("apply_mutation_no_readable_files", files=target_files)
            return {}

        # DGM-style prompt: include full code + mutation goal + rules
        files_section = "\n\n".join(
            f"### FILE: {k}\n```python\n{v}\n```" for k, v in file_contents.items()
        )
        prompt = (
            f"## Mutation Goal\n{mutation.description}\n"
            f"## Mutation Type\n{mutation.mutation_type.value}\n"
            f"## Context\n{context}\n\n"
            f"## Files to Modify\n{files_section}\n\n"
            "## Instructions\n"
            "Implement the mutation. For EACH modified file, output it using this EXACT format:\n"
            "===FILE: src/path/to/file.py===\n"
            "<complete new file content here>\n"
            "===END===\n\n"
            "Rules:\n"
            "1. Keep all existing imports and function signatures unless specifically changing them\n"
            "2. Do not break existing test contracts\n"
            "3. Make the smallest focused change that achieves the mutation goal\n"
            "4. Output ONLY the file blocks — no explanation, no markdown fences"
        )

        client = anthropic.Anthropic(
            base_url=os.environ.get("ANTHROPIC_BASE_URL", "http://localhost:4000"),
            api_key=os.environ.get("ANTHROPIC_API_KEY", "sk-local"),
        )

        try:
            resp = client.messages.create(
                model=os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6"),
                max_tokens=8192,
                system=(
                    "You are an expert Python developer implementing precise code mutations. "
                    "Output modified files using ===FILE: path=== ... ===END=== markers. "
                    "No JSON, no markdown, no explanation."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            return self._extract_json_files(text, fallback_paths=target_files[:1])
        except Exception as e:
            logger.error("apply_mutation_llm_error", error=str(e))
            return {}

    def _extract_json_files(self, text: str, fallback_paths: list[str] | None = None) -> dict[str, str]:
        """Extract {filepath: content} from LLM response.

        Supports three formats:
        1. Marker format: ===FILE: path===\\ncontent\\n===END===  (preferred)
        2. JSON format: {"path": "content"}  (legacy fallback)
        3. Raw code block: ```python\\ncode\\n``` (last resort, uses fallback_paths[0])
        """
        import json
        import re

        # Format 1: marker-based (no JSON escaping issues)
        marker_pattern = re.compile(
            r"===FILE:\s*(.+?)===\n(.*?)===END===", re.DOTALL
        )
        matches = marker_pattern.findall(text)
        if matches:
            result = {}
            for path, content in matches:
                # Strip markdown fences if model wrapped content
                content = content.strip()
                if content.startswith("```python"):
                    content = content[len("```python"):].lstrip("\n")
                elif content.startswith("```"):
                    content = content[3:].lstrip("\n")
                if content.endswith("```"):
                    content = content[:-3].rstrip("\n")
                result[path.strip()] = content
            return result

        # Format 2: JSON fallback — strip markdown fences first
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1].strip()
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return {k: v for k, v in result.items() if isinstance(v, str)}
        except json.JSONDecodeError:
            pass
        # Try to find JSON object in text
        match = re.search(r'\{["\s]*"[^"]+"\s*:', text, re.DOTALL)
        if match:
            try:
                return json.loads(text[match.start():])
            except Exception:
                pass
        # Format 3: raw code block fallback — use first target file as key
        if fallback_paths:
            clean = text.strip()
            # Strip leading "python" if model started inside a code fence
            if clean.startswith("python\n"):
                clean = clean[7:]
            # Try to detect Python code (has def/class/import)
            if any(kw in clean for kw in ("def ", "class ", "import ", "from ")):
                logger.info("apply_mutation_raw_code_fallback", path=fallback_paths[0])
                return {fallback_paths[0]: clean}
        logger.warning("apply_mutation_json_parse_failed", text_preview=text[:200])
        return {}
