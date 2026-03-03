"""Invariant registry and built-in invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class InvariantSeverity(str, Enum):
    error = "error"
    warning = "warning"


class InvariantViolation(BaseModel):
    invariant_name: str
    message: str
    severity: InvariantSeverity = InvariantSeverity.error
    details: dict[str, Any] = Field(default_factory=dict)


class InvariantReport(BaseModel):
    passed: bool = True
    violations: list[InvariantViolation] = Field(default_factory=list)

    def add_violation(self, violation: InvariantViolation) -> None:
        self.violations.append(violation)
        if violation.severity == InvariantSeverity.error:
            self.passed = False


@dataclass
class Invariant:
    name: str
    description: str
    check: Callable[..., InvariantViolation | None]
    enabled: bool = True


class InvariantRegistry:
    """Registry of invariants that must hold after every change."""

    def __init__(self) -> None:
        self._invariants: dict[str, Invariant] = {}
        self._register_builtins()

    def register(self, invariant: Invariant) -> None:
        self._invariants[invariant.name] = invariant

    def unregister(self, name: str) -> None:
        self._invariants.pop(name, None)

    def check_all(self, context: dict[str, Any] | None = None) -> InvariantReport:
        ctx = context or {}
        report = InvariantReport()
        for inv in self._invariants.values():
            if not inv.enabled:
                continue
            try:
                violation = inv.check(ctx)
                if violation:
                    report.add_violation(violation)
            except Exception as e:
                report.add_violation(InvariantViolation(
                    invariant_name=inv.name,
                    message=f"Invariant check raised: {e}",
                    severity=InvariantSeverity.error,
                ))
        return report

    def list_invariants(self) -> list[str]:
        return list(self._invariants.keys())

    def _register_builtins(self) -> None:
        self.register(Invariant(
            name="tests_must_pass",
            description="All tests must pass",
            check=_check_tests_must_pass,
        ))
        self.register(Invariant(
            name="no_security_regressions",
            description="No new security issues introduced",
            check=_check_no_security_regressions,
        ))
        self.register(Invariant(
            name="kernel_immutable",
            description="Kernel files must not be modified by agents",
            check=_check_kernel_immutable,
        ))
        self.register(Invariant(
            name="config_valid",
            description="Configuration must remain valid",
            check=_check_config_valid,
        ))
        self.register(Invariant(
            name="tests_must_not_regress",
            description="Test count must not decrease",
            check=_check_tests_must_not_regress,
        ))
        self.register(Invariant(
            name="coverage_floor",
            description="Coverage must stay above minimum threshold",
            check=_check_coverage_floor,
        ))
        self.register(Invariant(
            name="no_new_security_issues",
            description="No new security issues from static analysis",
            check=_check_no_new_security_issues,
        ))
        self.register(Invariant(
            name="kernel_immutability_sha",
            description="Kernel file SHA checksums must not change",
            check=_check_kernel_immutability_sha,
        ))
        self.register(Invariant(
            name="type_check_must_pass",
            description="Type checking must pass with zero errors",
            check=_check_type_check_must_pass,
        ))
        self.register(Invariant(
            name="no_deleted_public_api",
            description="Public API symbols must not be removed",
            check=_check_no_deleted_public_api,
        ))


def _check_tests_must_pass(ctx: dict[str, Any]) -> InvariantViolation | None:
    test_result = ctx.get("test_result")
    if test_result and not test_result.get("passed", True):
        return InvariantViolation(
            invariant_name="tests_must_pass",
            message=f"Tests failed: {test_result.get('failures', 0)} failures",
            details=test_result,
        )
    return None


def _check_no_security_regressions(ctx: dict[str, Any]) -> InvariantViolation | None:
    before = ctx.get("security_issues_before", 0)
    after = ctx.get("security_issues_after", 0)
    if after > before:
        return InvariantViolation(
            invariant_name="no_security_regressions",
            message=f"Security issues increased from {before} to {after}",
        )
    return None


def _check_kernel_immutable(ctx: dict[str, Any]) -> InvariantViolation | None:
    changed_files = ctx.get("changed_files", [])
    for f in changed_files:
        if f.startswith("src/evolutor/kernel/"):
            return InvariantViolation(
                invariant_name="kernel_immutable",
                message=f"Kernel file modified: {f}",
            )
    return None


def _check_config_valid(ctx: dict[str, Any]) -> InvariantViolation | None:
    config_error = ctx.get("config_error")
    if config_error:
        return InvariantViolation(
            invariant_name="config_valid",
            message=f"Config validation failed: {config_error}",
        )
    return None


def _check_tests_must_not_regress(ctx: dict[str, Any]) -> InvariantViolation | None:
    before_count = ctx.get("test_count_before", 0)
    after_count = ctx.get("test_count_after", 0)
    if before_count > 0 and after_count < before_count:
        return InvariantViolation(
            invariant_name="tests_must_not_regress",
            message=f"Test count decreased from {before_count} to {after_count}",
            details={"before": before_count, "after": after_count},
        )
    return None


def _check_coverage_floor(ctx: dict[str, Any]) -> InvariantViolation | None:
    coverage = ctx.get("coverage_percent", 100.0)
    floor = ctx.get("coverage_floor", 60.0)
    if coverage < floor:
        return InvariantViolation(
            invariant_name="coverage_floor",
            message=f"Coverage {coverage:.1f}% below floor {floor:.1f}%",
            details={"coverage": coverage, "floor": floor},
        )
    return None


def _check_no_new_security_issues(ctx: dict[str, Any]) -> InvariantViolation | None:
    new_issues = ctx.get("new_security_issues", [])
    if new_issues:
        return InvariantViolation(
            invariant_name="no_new_security_issues",
            message=f"{len(new_issues)} new security issue(s) found",
            details={"issues": new_issues},
        )
    return None


def _check_kernel_immutability_sha(ctx: dict[str, Any]) -> InvariantViolation | None:
    expected_shas = ctx.get("kernel_file_shas", {})
    actual_shas = ctx.get("kernel_file_shas_after", {})
    for path, expected in expected_shas.items():
        actual = actual_shas.get(path)
        if actual and actual != expected:
            return InvariantViolation(
                invariant_name="kernel_immutability_sha",
                message=f"Kernel file SHA changed: {path}",
                details={"path": path, "expected": expected, "actual": actual},
            )
    return None


def _check_type_check_must_pass(ctx: dict[str, Any]) -> InvariantViolation | None:
    type_errors = ctx.get("type_check_errors", 0)
    if type_errors > 0:
        return InvariantViolation(
            invariant_name="type_check_must_pass",
            message=f"Type checking found {type_errors} error(s)",
            details={"error_count": type_errors},
        )
    return None


def _check_no_deleted_public_api(ctx: dict[str, Any]) -> InvariantViolation | None:
    deleted_symbols = ctx.get("deleted_public_symbols", [])
    if deleted_symbols:
        return InvariantViolation(
            invariant_name="no_deleted_public_api",
            message=f"Public API symbols removed: {', '.join(deleted_symbols[:5])}",
            details={"deleted": deleted_symbols},
        )
    return None
