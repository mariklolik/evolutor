"""Unit tests for kernel modules."""

from __future__ import annotations

import asyncio

import pygit2
import pytest

from evolutor.kernel.invariants import (
    InvariantRegistry,
    Invariant,
    InvariantReport,
    InvariantViolation,
    InvariantSeverity,
)
from evolutor.kernel.evaluator import Evaluator, EvaluationResult
from evolutor.kernel.rollback import RollbackManager, Savepoint
from evolutor.kernel.safety import SafetyBoundary, RiskLevel
from evolutor.kernel.trust import TrustScorer, TrustLevel


class TestInvariantRegistry:
    def test_builtins_registered(self):
        reg = InvariantRegistry()
        names = reg.list_invariants()
        assert "tests_must_pass" in names
        assert "no_security_regressions" in names
        assert "kernel_immutable" in names
        assert "config_valid" in names

    def test_check_all_passes_no_context(self):
        reg = InvariantRegistry()
        report = reg.check_all({})
        assert report.passed

    def test_tests_must_pass_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"test_result": {"passed": False, "failures": 3}})
        assert not report.passed
        assert any(v.invariant_name == "tests_must_pass" for v in report.violations)

    def test_security_regression_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"security_issues_before": 0, "security_issues_after": 2})
        assert not report.passed

    def test_kernel_immutable_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"changed_files": ["src/evolutor/kernel/safety.py"]})
        assert not report.passed

    def test_register_custom(self):
        reg = InvariantRegistry()
        custom = Invariant(
            name="custom_check",
            description="Always passes",
            check=lambda ctx: None,
        )
        reg.register(custom)
        assert "custom_check" in reg.list_invariants()

    def test_unregister(self):
        reg = InvariantRegistry()
        reg.unregister("tests_must_pass")
        assert "tests_must_pass" not in reg.list_invariants()

    def test_disabled_invariant_skipped(self):
        reg = InvariantRegistry()
        reg.register(Invariant(
            name="always_fail",
            description="Would fail",
            check=lambda ctx: InvariantViolation(invariant_name="always_fail", message="fail"),
            enabled=False,
        ))
        report = reg.check_all({})
        assert report.passed

    def test_new_invariants_registered(self):
        reg = InvariantRegistry()
        names = reg.list_invariants()
        assert "tests_must_not_regress" in names
        assert "coverage_floor" in names
        assert "no_new_security_issues" in names
        assert "kernel_immutability_sha" in names
        assert "type_check_must_pass" in names
        assert "no_deleted_public_api" in names

    def test_tests_must_not_regress_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"test_count_before": 50, "test_count_after": 45})
        assert not report.passed
        assert any(v.invariant_name == "tests_must_not_regress" for v in report.violations)

    def test_tests_must_not_regress_passes(self):
        reg = InvariantRegistry()
        report = reg.check_all({"test_count_before": 50, "test_count_after": 55})
        assert not any(v.invariant_name == "tests_must_not_regress" for v in report.violations)

    def test_coverage_floor_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"coverage_percent": 40.0, "coverage_floor": 60.0})
        assert not report.passed
        assert any(v.invariant_name == "coverage_floor" for v in report.violations)

    def test_coverage_floor_passes(self):
        reg = InvariantRegistry()
        report = reg.check_all({"coverage_percent": 80.0, "coverage_floor": 60.0})
        assert not any(v.invariant_name == "coverage_floor" for v in report.violations)

    def test_no_new_security_issues_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"new_security_issues": ["SQL injection in query.py"]})
        assert not report.passed
        assert any(v.invariant_name == "no_new_security_issues" for v in report.violations)

    def test_kernel_immutability_sha_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({
            "kernel_file_shas": {"kernel/safety.py": "abc123"},
            "kernel_file_shas_after": {"kernel/safety.py": "def456"},
        })
        assert not report.passed
        assert any(v.invariant_name == "kernel_immutability_sha" for v in report.violations)

    def test_type_check_must_pass_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"type_check_errors": 5})
        assert not report.passed
        assert any(v.invariant_name == "type_check_must_pass" for v in report.violations)

    def test_no_deleted_public_api_violation(self):
        reg = InvariantRegistry()
        report = reg.check_all({"deleted_public_symbols": ["MyClass", "my_function"]})
        assert not report.passed
        assert any(v.invariant_name == "no_deleted_public_api" for v in report.violations)


class TestEvaluator:
    def test_evaluate_passes(self):
        ev = Evaluator()
        result = asyncio.get_event_loop().run_until_complete(ev.evaluate({}))
        assert result.accepted

    def test_evaluate_fails_on_violation(self):
        ev = Evaluator()
        ctx = {"test_result": {"passed": False, "failures": 1}}
        result = asyncio.get_event_loop().run_until_complete(ev.evaluate(ctx))
        assert not result.accepted

    def test_compute_delta(self):
        delta = Evaluator.compute_delta(
            {"coverage": 80.0, "tests": 10.0},
            {"coverage": 85.0, "tests": 12.0},
        )
        assert delta["coverage"] == 5.0
        assert delta["tests"] == 2.0

    def test_should_accept(self):
        good = EvaluationResult(accepted=True, confidence=0.9)
        bad = EvaluationResult(accepted=False, confidence=0.1)
        assert Evaluator.should_accept(good)
        assert not Evaluator.should_accept(bad)


class TestRollbackManager:
    @pytest.fixture
    def repo_with_commits(self, tmp_path):
        repo = pygit2.init_repository(str(tmp_path), bare=False)
        (tmp_path / "file.txt").write_text("v1")
        index = repo.index
        index.add("file.txt")
        index.write()
        tree = index.write_tree()
        sig = pygit2.Signature("Test", "test@test.com")
        repo.create_commit("HEAD", sig, sig, "Commit 1", tree, [])
        return repo

    def test_create_savepoint(self, repo_with_commits):
        rm = RollbackManager(repo_with_commits)
        sp = rm.create_savepoint("before-refactor")
        assert sp.label == "before-refactor"
        assert sp.commit_sha

    def test_list_savepoints(self, repo_with_commits):
        rm = RollbackManager(repo_with_commits)
        rm.create_savepoint("sp1")
        rm.create_savepoint("sp2")
        sps = rm.list_savepoints()
        labels = [s.label for s in sps]
        assert "sp1" in labels
        assert "sp2" in labels

    def test_rollback_to(self, repo_with_commits):
        rm = RollbackManager(repo_with_commits)
        sp = rm.create_savepoint("stable")
        # Make another commit
        repo = repo_with_commits
        workdir = Path(repo.workdir)
        (workdir / "file.txt").write_text("v2")
        index = repo.index
        index.add("file.txt")
        index.write()
        tree = index.write_tree()
        sig = pygit2.Signature("Test", "test@test.com")
        repo.create_commit("HEAD", sig, sig, "Commit 2", tree, [repo.head.target])
        # Rollback
        sha = rm.rollback_to("stable")
        assert sha == sp.commit_sha

    def test_rollback_nonexistent(self, repo_with_commits):
        rm = RollbackManager(repo_with_commits)
        with pytest.raises(ValueError):
            rm.rollback_to("nonexistent")


class TestSafetyBoundary:
    def test_check_file_access_protected_write(self):
        sb = SafetyBoundary()
        assert sb.check_file_access("src/evolutor/kernel/safety.py", write=True) == RiskLevel.critical

    def test_check_file_access_protected_read(self):
        sb = SafetyBoundary()
        assert sb.check_file_access("src/evolutor/kernel/safety.py", write=False) == RiskLevel.moderate

    def test_check_file_access_safe(self):
        sb = SafetyBoundary()
        assert sb.check_file_access("src/evolutor/memory/foo.py") == RiskLevel.safe

    def test_check_command_dangerous(self):
        sb = SafetyBoundary()
        assert sb.check_command("rm -rf /") == RiskLevel.critical
        assert sb.check_command("git push --force") == RiskLevel.critical

    def test_check_command_safe(self):
        sb = SafetyBoundary()
        assert sb.check_command("ls -la") == RiskLevel.safe

    def test_validate_diff(self):
        sb = SafetyBoundary()
        assert sb.validate_diff(["src/evolutor/kernel/trust.py"]) == RiskLevel.critical
        assert sb.validate_diff(["src/evolutor/memory/foo.py"]) == RiskLevel.safe

    def test_get_risk_level(self):
        sb = SafetyBoundary()
        assert sb.get_risk_level(command="rm -rf /") == RiskLevel.critical
        assert sb.get_risk_level(file_path="safe.py") == RiskLevel.safe


class TestTrustScorer:
    def test_initial_trust(self):
        ts = TrustScorer()
        assert ts.compute_trust("new-agent") == TrustLevel.L1

    def test_trust_grows_with_success(self):
        ts = TrustScorer()
        for _ in range(5):
            ts.update_trust("agent", True)
        assert ts.compute_trust("agent") == TrustLevel.L2

    def test_trust_decreases_with_failure(self):
        ts = TrustScorer()
        for _ in range(5):
            ts.update_trust("agent", True)
        assert ts.compute_trust("agent") == TrustLevel.L2
        for _ in range(3):
            ts.update_trust("agent", False)
        assert ts.compute_trust("agent") == TrustLevel.L1

    def test_should_require_review(self):
        ts = TrustScorer()
        assert ts.should_require_review("untrusted")
        for _ in range(15):
            ts.update_trust("trusted", True)
        assert not ts.should_require_review("trusted")

    def test_high_trust(self):
        ts = TrustScorer()
        for _ in range(60):
            ts.update_trust("super", True)
        assert ts.compute_trust("super") == TrustLevel.L5


# Need Path import for TestRollbackManager
from pathlib import Path
