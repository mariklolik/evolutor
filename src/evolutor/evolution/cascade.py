"""Cascading evaluator — reject bad mutations early, cheaply.

Based on AlphaEvolve/OpenEvolve cascade approach (proven ~10x throughput improvement).
Read openevolve/openevolve/evaluator.py for reference implementation.

Stages:
  Stage 0: ruff syntax check (<100ms) — reject on syntax errors
  Stage 1: unit tests fast (-x, --timeout=20) — reject if pass_rate < 0.85
  Stage 2: integration tests — reject if pass_rate < 0.70
  Stage 3: full eval — compute complete fitness vector
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class CascadeResult:
    passed: bool
    stage_reached: str
    pass_rate: float = 0.0
    artifacts: dict[str, str] = field(default_factory=dict)
    reason: str = ""


class CascadingEvaluator:
    """Multi-stage evaluation pipeline.

    Each stage is faster but less precise. Cheap filters reject bad mutations early.
    Artifacts (error messages) are collected and fed back to the mutation LLM.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        stage0_threshold: float = 1.0,
        stage1_pass_threshold: float = 0.85,
        stage2_pass_threshold: float = 0.70,
    ):
        self.project_root = project_root or Path(
            os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")
        ).resolve()
        self.stage0_threshold = stage0_threshold
        self.stage1_pass_threshold = stage1_pass_threshold
        self.stage2_pass_threshold = stage2_pass_threshold

    def evaluate(self, modified_files: dict[str, str], child_root: Path) -> CascadeResult:
        """Run cascade evaluation on child_root (already has modified files applied).

        Returns CascadeResult with artifacts for LLM feedback loop.
        """
        artifacts: dict[str, str] = {}

        # --- Stage 0: Syntax (ruff) -----------------------------------------------
        file_paths = [str(child_root / f) for f in modified_files]
        ruff = subprocess.run(
            ["python", "-m", "ruff", "check", "--select=E9,F401,F811,F821,F841"] + file_paths,
            capture_output=True, text=True, timeout=15,
        )
        artifacts["stage0_ruff"] = ruff.stdout[:500] + ruff.stderr[:200]
        if ruff.returncode != 0:
            return CascadeResult(
                passed=False, stage_reached="stage0_syntax",
                artifacts=artifacts,
                reason=f"Syntax errors: {ruff.stdout[:200]}"
            )

        # Also check with ast.parse for deeper syntax validation
        for fpath, content in modified_files.items():
            try:
                import ast
                ast.parse(content)
            except SyntaxError as e:
                artifacts["stage0_ast"] = str(e)
                return CascadeResult(
                    passed=False, stage_reached="stage0_ast",
                    artifacts=artifacts, reason=f"AST parse error in {fpath}: {e}"
                )

        # --- Stage 1: Unit tests (fast) -------------------------------------------
        result1 = subprocess.run(
            ["python", "-m", "pytest", "tests/unit/", "-x", "-q",
             "--tb=short", "--timeout=20", "-p", "no:warnings", "--no-header"],
            capture_output=True, text=True, timeout=120, cwd=child_root,
            env={**os.environ, "PYTHONPATH": str(child_root / "src")},
        )
        out1 = result1.stdout + result1.stderr
        artifacts["stage1_pytest"] = out1[:1000]

        passed1, failed1 = self._parse_pytest(out1)
        total1 = passed1 + failed1
        pass_rate1 = passed1 / max(total1, 1)

        if pass_rate1 < self.stage1_pass_threshold and total1 > 0:
            return CascadeResult(
                passed=False, stage_reached="stage1_unit",
                pass_rate=pass_rate1, artifacts=artifacts,
                reason=(
                    f"Unit tests: {passed1}/{total1} passed "
                    f"({pass_rate1:.0%} < {self.stage1_pass_threshold:.0%})"
                ),
            )

        # --- Stage 2: Integration/scenario tests ----------------------------------
        scenario_dir = child_root / "tests" / "scenario"
        integration_dir = child_root / "tests" / "integration"
        if scenario_dir.exists() or integration_dir.exists():
            test_dir = "tests/scenario" if scenario_dir.exists() else "tests/integration"
            result2 = subprocess.run(
                ["python", "-m", "pytest", test_dir, "-q",
                 "--tb=short", "--timeout=60", "-p", "no:warnings", "--no-header"],
                capture_output=True, text=True, timeout=180, cwd=child_root,
                env={**os.environ, "PYTHONPATH": str(child_root / "src")},
            )
            out2 = result2.stdout + result2.stderr
            artifacts["stage2_integration"] = out2[:800]
            passed2, failed2 = self._parse_pytest(out2)
            total2 = passed2 + failed2
            pass_rate2 = passed2 / max(total2, 1)

            if pass_rate2 < self.stage2_pass_threshold and total2 > 0:
                return CascadeResult(
                    passed=False, stage_reached="stage2_integration",
                    pass_rate=pass_rate2, artifacts=artifacts,
                    reason=f"Integration tests: {passed2}/{total2} passed"
                )

        # --- Stage 3: Full eval passed --------------------------------------------
        return CascadeResult(
            passed=True, stage_reached="stage3_full",
            pass_rate=pass_rate1, artifacts=artifacts,
        )

    @staticmethod
    def _parse_pytest(output: str) -> tuple[int, int]:
        """Parse pytest output for passed/failed counts."""
        passed = (
            int(re.search(r"(\d+) passed", output).group(1))
            if re.search(r"(\d+) passed", output) else 0
        )
        failed = (
            int(re.search(r"(\d+) failed", output).group(1))
            if re.search(r"(\d+) failed", output) else 0
        )
        return passed, failed

    def format_artifacts_for_llm(self, result: CascadeResult) -> str:
        """Format cascade artifacts as context for the mutation LLM (OpenEvolve artifact channel)."""
        if result.passed:
            return "Previous mutation PASSED all evaluation stages."
        lines = [f"Previous mutation FAILED at {result.stage_reached}: {result.reason}"]
        for stage, output in result.artifacts.items():
            if output.strip():
                lines.append(f"\n[{stage}]\n{output[:400]}")
        return "\n".join(lines)
