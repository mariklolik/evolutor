"""Metrics collection for code quality evaluation."""

from __future__ import annotations

import asyncio
import subprocess
import time

import structlog
from pydantic import BaseModel, Field

from evolutor.types.metrics import BehaviorDescriptor, CodeMetrics, FitnessVector

logger = structlog.get_logger()


class TestResult(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.passed / self.total


class BenchmarkResult(BaseModel):
    name: str = ""
    mean_seconds: float = 0.0
    stddev_seconds: float = 0.0
    rounds: int = 0


class MetricsCollector:
    """Collect and compute code quality metrics."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root
        self._before: CodeMetrics | None = None
        self._after: CodeMetrics | None = None

    async def collect_before(self) -> CodeMetrics:
        self._before = await self._collect()
        return self._before

    async def collect_after(self) -> CodeMetrics:
        self._after = await self._collect()
        return self._after

    async def run_tests(self, test_path: str = "tests/") -> TestResult:
        try:
            start = time.time()
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["python", "-m", "pytest", test_path, "-q", "--tb=no"],
                    capture_output=True, text=True, cwd=self.project_root,
                    env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                ),
            )
            duration = time.time() - start
            # Parse pytest output
            output = result.stdout
            total = passed = failed = errors = 0
            for line in output.splitlines():
                if "passed" in line or "failed" in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "passed" and i > 0:
                            try:
                                passed = int(parts[i - 1])
                            except ValueError:
                                pass
                        if p == "failed" and i > 0:
                            try:
                                failed = int(parts[i - 1])
                            except ValueError:
                                pass
            total = passed + failed + errors
            return TestResult(
                total=total, passed=passed, failed=failed,
                errors=errors, duration_seconds=duration,
            )
        except Exception as e:
            logger.warning("test_run_failed", error=str(e))
            return TestResult()

    async def run_benchmarks(self, bench_path: str = "tests/benchmarks/") -> list[BenchmarkResult]:
        return []

    def compute_fitness(self, metrics: CodeMetrics) -> FitnessVector:
        security_score = 1.0 - min(metrics.security_issues / 10.0, 1.0)
        return FitnessVector(
            test_pass_rate=metrics.test_pass_rate,
            coverage=metrics.coverage_percent / 100.0,
            complexity=min(metrics.cyclomatic_complexity / 20.0, 1.0),
            security_score=security_score,
        )

    def compute_behavior(self, metrics: CodeMetrics) -> BehaviorDescriptor:
        return BehaviorDescriptor(
            complexity=min(metrics.cyclomatic_complexity / 20.0, 1.0),
            novelty=0.5,
        )

    async def _collect(self) -> CodeMetrics:
        return CodeMetrics()
