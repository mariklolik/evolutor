"""Cascading evaluator — reject bad mutations early, cheaply.

Three evaluation stages with increasing cost and task count.
Stops at first failure, saving 3-5x compute vs full evaluation.

Stages:
  Stage 0: ast.parse() syntax check (<1ms)
  Stage 1: smoke — run on 1 task, check it doesn't crash at step 0
  Stage 2: medium — run on 3 tasks, accept if >=1 pass
  Stage 3: full — run on all tasks
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger()

STAGE_NAMES = ("stage0_syntax", "stage1_smoke", "stage2_medium", "stage3_full")


@dataclass
class CascadeResult:
    passed: bool
    stage_reached: str           # one of STAGE_NAMES
    pass_rate: float = 0.0
    tasks_passed: int = 0
    tasks_total: int = 0
    rejection_reason: str = ""
    agent_logs: str = ""         # truncated to 2000 chars


class CascadingEvaluator:
    """Multi-stage SWE-bench evaluation pipeline.

    Each stage runs more tasks. Cheap filters reject bad mutations early.
    Composite reward: syntax_valid*0.1 + runs_without_crash*0.3 + pass_rate*0.6
    """

    def __init__(
        self,
        tasks: list[dict],
        project_root: Path | str,
        model: str = "claude-sonnet-4-6",
    ):
        self.tasks = tasks
        self.project_root = Path(project_root)
        self.model = model or os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6")

    def evaluate(self, agent_code: str, max_stage: int = 3) -> CascadeResult:
        """Run cascade evaluation, stopping at first failure."""
        # Stage 0: syntax
        if not self._stage0_syntax(agent_code):
            return CascadeResult(
                passed=False,
                stage_reached="stage0_syntax",
                rejection_reason="syntax error in agent code",
            )
        if max_stage == 0:
            return CascadeResult(passed=True, stage_reached="stage0_syntax", pass_rate=1.0)

        # Stage 1: smoke test (1 task)
        result1 = self._stage1_smoke(agent_code)
        if not result1.passed:
            return result1
        if max_stage == 1:
            return result1

        # Stage 2: medium (3 tasks, pass if >=1)
        result2 = self._stage2_medium(agent_code)
        if not result2.passed:
            return result2
        if max_stage == 2:
            return result2

        # Stage 3: full
        return self._stage3_full(agent_code)

    def _stage0_syntax(self, agent_code: str) -> bool:
        """Check code is valid Python via ast.parse."""
        try:
            ast.parse(agent_code)
            return True
        except SyntaxError:
            return False

    def _stage1_smoke(self, agent_code: str) -> CascadeResult:
        """Run on 1 task. Passes if agent doesn't crash at step 0."""
        from evolutor.swebench.harness import eval_agent_code_docker

        if not self.tasks:
            return CascadeResult(passed=True, stage_reached="stage1_smoke",
                                 pass_rate=1.0, tasks_passed=0, tasks_total=0,
                                 rejection_reason="no tasks available")

        task = self.tasks[0]
        try:
            result = eval_agent_code_docker(
                agent_code=agent_code,
                task=task,
                project_root=self.project_root,
                model=self.model,
                timeout=120,
            )
            logs = (result.logs or "")[:2000]
            # Smoke passes if agent produced some output (didn't crash immediately)
            produced_output = bool(logs.strip()) and "Error" not in (result.error or "")[:50]
            if not produced_output and not result.passed:
                return CascadeResult(
                    passed=False,
                    stage_reached="stage1_smoke",
                    tasks_passed=0,
                    tasks_total=1,
                    rejection_reason=f"smoke test crashed: {result.error}",
                    agent_logs=logs,
                )
            return CascadeResult(
                passed=True,
                stage_reached="stage1_smoke",
                pass_rate=1.0 if result.passed else 0.0,
                tasks_passed=1 if result.passed else 0,
                tasks_total=1,
                agent_logs=logs,
            )
        except Exception as e:
            return CascadeResult(
                passed=False,
                stage_reached="stage1_smoke",
                rejection_reason=str(e),
            )

    def _stage2_medium(self, agent_code: str) -> CascadeResult:
        """Run on first 3 tasks. Accept if >=1/3 pass."""
        from evolutor.swebench.harness import eval_agent_code_docker

        sample = self.tasks[:3]
        passed_count = 0
        all_logs = []

        for task in sample:
            try:
                result = eval_agent_code_docker(
                    agent_code=agent_code,
                    task=task,
                    project_root=self.project_root,
                    model=self.model,
                    timeout=300,
                )
                if result.passed:
                    passed_count += 1
                all_logs.append(f"[{task['instance_id']}] {'PASS' if result.passed else 'FAIL'}")
            except Exception as e:
                all_logs.append(f"[{task['instance_id']}] ERROR: {e}")

        logs = "\n".join(all_logs)[:2000]
        pass_rate = passed_count / max(len(sample), 1)
        passed = passed_count >= 1  # At least 1/3 must pass

        return CascadeResult(
            passed=passed,
            stage_reached="stage2_medium",
            pass_rate=pass_rate,
            tasks_passed=passed_count,
            tasks_total=len(sample),
            rejection_reason="" if passed else f"only {passed_count}/{len(sample)} passed",
            agent_logs=logs,
        )

    def _stage3_full(self, agent_code: str) -> CascadeResult:
        """Run on all tasks."""
        from evolutor.swebench.harness import eval_agent_code_docker

        passed_count = 0
        all_logs = []

        for task in self.tasks:
            try:
                result = eval_agent_code_docker(
                    agent_code=agent_code,
                    task=task,
                    project_root=self.project_root,
                    model=self.model,
                    timeout=600,
                )
                if result.passed:
                    passed_count += 1
                all_logs.append(f"[{task['instance_id']}] {'PASS' if result.passed else 'FAIL'}")
            except Exception as e:
                all_logs.append(f"[{task['instance_id']}] ERROR: {e}")

        logs = "\n".join(all_logs)[:2000]
        pass_rate = passed_count / max(len(self.tasks), 1)

        return CascadeResult(
            passed=True,  # Stage 3 always "passes" — records final pass rate
            stage_reached="stage3_full",
            pass_rate=pass_rate,
            tasks_passed=passed_count,
            tasks_total=len(self.tasks),
            agent_logs=logs,
        )
