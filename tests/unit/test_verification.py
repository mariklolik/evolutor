"""Unit tests for verification modules."""

from __future__ import annotations

import pytest

from evolutor.verification.consensus import ConsensusVerifier, ConsensusResult, Vote
from evolutor.verification.metrics import MetricsCollector, TestResult
from evolutor.verification.adversarial import AdversarialTester, AdversarialReport
from evolutor.verification.static import StaticAnalysisReport, SecurityIssue
from evolutor.types.metrics import CodeMetrics, FitnessVector


class TestStaticAnalysisReport:
    def test_report_passed(self):
        report = StaticAnalysisReport(ruff_errors=0, mypy_errors=0, passed=True)
        assert report.passed

    def test_report_failed(self):
        report = StaticAnalysisReport(ruff_errors=5, passed=False)
        assert not report.passed

    def test_security_issue_model(self):
        issue = SecurityIssue(
            file="test.py", line=10, severity="HIGH",
            message="Use of exec", test_id="B102",
        )
        assert issue.severity == "HIGH"


class TestMetricsCollector:
    def test_compute_fitness(self):
        mc = MetricsCollector()
        metrics = CodeMetrics(
            test_pass_rate=0.95,
            coverage_percent=80.0,
            cyclomatic_complexity=5.0,
            security_issues=0,
        )
        fitness = mc.compute_fitness(metrics)
        assert fitness.test_pass_rate == 0.95
        assert fitness.coverage == 0.8
        assert fitness.security_score == 1.0

    def test_compute_behavior(self):
        mc = MetricsCollector()
        metrics = CodeMetrics(cyclomatic_complexity=10.0)
        behavior = mc.compute_behavior(metrics)
        assert behavior.complexity == 0.5

    def test_fitness_to_minimize(self):
        fv = FitnessVector(test_pass_rate=1.0, coverage=0.8, complexity=0.3, security_score=0.9)
        minimized = fv.to_minimize()
        assert minimized[0] == -1.0  # test_pass_rate negated
        assert minimized[2] == 0.3  # complexity not negated

    def test_test_result_pass_rate(self):
        tr = TestResult(total=10, passed=8, failed=2)
        assert tr.pass_rate == 0.8

    def test_test_result_empty(self):
        tr = TestResult()
        assert tr.pass_rate == 1.0


class TestConsensusVerifier:
    def test_vote_accept(self):
        cv = ConsensusVerifier(threshold=0.7)
        result = ConsensusResult(threshold=0.7)
        votes = [
            Vote(voter_id="a1", accept=True, confidence=1.0),
            Vote(voter_id="a2", accept=True, confidence=1.0),
            Vote(voter_id="a3", accept=True, confidence=1.0),
            Vote(voter_id="a4", accept=False, confidence=1.0),
        ]
        result = cv.vote(result, votes)
        assert result.accepted  # 3/4 = 0.75 > 0.7

    def test_vote_reject(self):
        cv = ConsensusVerifier(threshold=0.7)
        result = ConsensusResult(threshold=0.7)
        votes = [
            Vote(voter_id="a1", accept=True, confidence=1.0),
            Vote(voter_id="a2", accept=False, confidence=1.0),
            Vote(voter_id="a3", accept=False, confidence=1.0),
        ]
        result = cv.vote(result, votes)
        assert not result.accepted

    def test_vote_with_confidence(self):
        cv = ConsensusVerifier(threshold=0.7)
        result = ConsensusResult(threshold=0.7)
        votes = [
            Vote(voter_id="a1", accept=True, confidence=0.9),
            Vote(voter_id="a2", accept=True, confidence=0.8),
            Vote(voter_id="a3", accept=False, confidence=0.3),
        ]
        result = cv.vote(result, votes)
        # weighted: 1.7/2.0 = 0.85 > 0.7
        assert result.accepted

    def test_empty_votes(self):
        cv = ConsensusVerifier()
        result = ConsensusResult()
        result = cv.vote(result, [])
        assert not result.accepted


class TestAdversarialTester:
    def test_generate_inputs(self):
        at = AdversarialTester()
        inputs = at.generate_adversarial_inputs("string")
        assert len(inputs) > 0
        assert all(isinstance(i, str) for i in inputs)

    def test_run_suite_safe_function(self):
        at = AdversarialTester()
        report = at.run_adversarial_suite(lambda x: len(x))
        assert report.cases_passed > 0

    def test_run_suite_crashing_function(self):
        def crash_on_empty(x):
            if x == "":
                raise ValueError("empty!")
            return x

        at = AdversarialTester()
        report = at.run_adversarial_suite(crash_on_empty)
        assert report.cases_failed >= 1

    def test_fuzz(self):
        at = AdversarialTester()
        result = at.fuzz(lambda x: x.upper(), iterations=50)
        assert result.iterations == 50
