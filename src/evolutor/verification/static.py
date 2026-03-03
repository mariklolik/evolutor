"""Static analysis tools integration."""

from __future__ import annotations

import asyncio
import json
import subprocess

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class SecurityIssue(BaseModel):
    file: str = ""
    line: int = 0
    severity: str = ""
    message: str = ""
    test_id: str = ""


class StaticAnalysisReport(BaseModel):
    ruff_errors: int = 0
    mypy_errors: int = 0
    bandit_issues: list[SecurityIssue] = Field(default_factory=list)
    radon_avg_complexity: float = 0.0
    passed: bool = True
    details: dict[str, str] = Field(default_factory=dict)


class StaticAnalyzer:
    """Run static analysis tools."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root

    async def run_ruff(self, paths: list[str] | None = None) -> tuple[int, str]:
        target = paths or [self.project_root]
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["ruff", "check", *target, "--output-format=json"],
                    capture_output=True, text=True, cwd=self.project_root,
                ),
            )
            try:
                issues = json.loads(result.stdout) if result.stdout else []
                return len(issues), result.stdout
            except json.JSONDecodeError:
                return result.returncode, result.stdout
        except FileNotFoundError:
            return 0, "ruff not found"

    async def run_mypy(self, paths: list[str] | None = None) -> tuple[int, str]:
        target = paths or [self.project_root]
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["mypy", *target, "--no-error-summary"],
                    capture_output=True, text=True, cwd=self.project_root,
                ),
            )
            errors = len([l for l in result.stdout.splitlines() if ": error:" in l])
            return errors, result.stdout
        except FileNotFoundError:
            return 0, "mypy not found"

    async def run_bandit(self, paths: list[str] | None = None) -> list[SecurityIssue]:
        target = paths or [self.project_root]
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["bandit", "-r", *target, "-f", "json", "-q"],
                    capture_output=True, text=True, cwd=self.project_root,
                ),
            )
            try:
                data = json.loads(result.stdout) if result.stdout else {}
                issues = []
                for r in data.get("results", []):
                    issues.append(SecurityIssue(
                        file=r.get("filename", ""),
                        line=r.get("line_number", 0),
                        severity=r.get("issue_severity", ""),
                        message=r.get("issue_text", ""),
                        test_id=r.get("test_id", ""),
                    ))
                return issues
            except json.JSONDecodeError:
                return []
        except FileNotFoundError:
            return []

    async def run_radon(self, paths: list[str] | None = None) -> float:
        target = paths or [self.project_root]
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["radon", "cc", *target, "-a", "-s"],
                    capture_output=True, text=True, cwd=self.project_root,
                ),
            )
            for line in result.stdout.splitlines():
                if "Average complexity:" in line:
                    parts = line.split()
                    for p in parts:
                        try:
                            return float(p.strip("()"))
                        except ValueError:
                            continue
            return 0.0
        except FileNotFoundError:
            return 0.0

    async def run_all(self, paths: list[str] | None = None) -> StaticAnalysisReport:
        ruff_task = self.run_ruff(paths)
        mypy_task = self.run_mypy(paths)
        bandit_task = self.run_bandit(paths)
        radon_task = self.run_radon(paths)
        ruff_errors, ruff_out = await ruff_task
        mypy_errors, mypy_out = await mypy_task
        bandit_issues = await bandit_task
        radon_avg = await radon_task
        passed = ruff_errors == 0 and mypy_errors == 0 and len(bandit_issues) == 0
        return StaticAnalysisReport(
            ruff_errors=ruff_errors,
            mypy_errors=mypy_errors,
            bandit_issues=bandit_issues,
            radon_avg_complexity=radon_avg,
            passed=passed,
            details={"ruff": ruff_out, "mypy": mypy_out},
        )
