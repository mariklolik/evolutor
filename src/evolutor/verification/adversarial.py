"""Adversarial testing and fuzzing."""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class AdversarialCase(BaseModel):
    name: str
    input_data: str
    expected_behavior: str = "no crash"
    category: str = "general"


class FuzzResult(BaseModel):
    iterations: int = 0
    crashes: int = 0
    unique_bugs: int = 0
    coverage_delta: float = 0.0


class AdversarialReport(BaseModel):
    cases_run: int = 0
    cases_passed: int = 0
    cases_failed: int = 0
    failures: list[str] = Field(default_factory=list)
    fuzz_result: FuzzResult | None = None


class AdversarialTester:
    """Generate and run adversarial test cases."""

    ADVERSARIAL_INPUTS = [
        "",
        " " * 1000,
        "\x00" * 100,
        "A" * 10000,
        "<script>alert(1)</script>",
        "'; DROP TABLE users; --",
        "../../../etc/passwd",
        "\n\r\n\r",
        "{{7*7}}",
        "${7*7}",
        None,
    ]

    def generate_adversarial_inputs(self, input_type: str = "string") -> list:
        if input_type == "string":
            return [i for i in self.ADVERSARIAL_INPUTS if isinstance(i, str)]
        return list(self.ADVERSARIAL_INPUTS)

    def run_adversarial_suite(
        self, target_fn: callable, cases: list[AdversarialCase] | None = None
    ) -> AdversarialReport:
        if cases is None:
            cases = [
                AdversarialCase(name=f"adversarial_{i}", input_data=str(inp))
                for i, inp in enumerate(self.generate_adversarial_inputs())
            ]
        report = AdversarialReport(cases_run=len(cases))
        for case in cases:
            try:
                target_fn(case.input_data)
                report.cases_passed += 1
            except Exception as e:
                report.cases_failed += 1
                report.failures.append(f"{case.name}: {e}")
        return report

    def fuzz(self, target_fn: callable, iterations: int = 100) -> FuzzResult:
        import random
        import string

        crashes = 0
        for _ in range(iterations):
            length = random.randint(0, 1000)
            data = "".join(random.choices(string.printable, k=length))
            try:
                target_fn(data)
            except Exception:
                crashes += 1
        return FuzzResult(iterations=iterations, crashes=crashes, unique_bugs=min(crashes, 5))
