"""Comprehensive scenario tests for end-to-end validation."""

from __future__ import annotations

import asyncio

import pytest

from evolutor.orchestrator.engine import OrchestratorEngine
from evolutor.orchestrator.parallelism import ParallelRunner
from evolutor.evolution.loop import EvolutionLoop
from evolutor.evolution.plateau import PlateauDetector
from evolutor.evolution.canary import CanaryDeployer
from evolutor.kernel.invariants import InvariantRegistry
from evolutor.kernel.rollback import RollbackManager
from evolutor.memory.playbooks import PlaybookManager
from evolutor.memory.scratchpad import Scratchpad
from evolutor.tools.forge.creator import ToolCreator
from evolutor.tools.forge.verifier import ToolVerifier
from evolutor.tools.forge.store import ToolStore
from evolutor.types.task import Task
from evolutor.types.metrics import FitnessVector


class TestMultiFileTask:
    """Scenario: orchestrator handles a multi-file task end-to-end."""

    def test_multi_subtask_pipeline(self):
        engine = OrchestratorEngine()
        task = Task(
            title="Refactor logging across 3 modules",
            description="Replace print statements with structlog in file_ops, bash, and git_tool",
        )
        result = asyncio.get_event_loop().run_until_complete(engine.run(task, max_iterations=5))
        assert result.success
        assert result.task_id  # Has a valid task_id


class TestPlateauAndDiversify:
    """Scenario: evolution detects plateau and suggests diversification."""

    def test_plateau_triggers_diversify(self):
        pd = PlateauDetector(window_size=10, variance_threshold=0.001)
        # Feed identical fitness values to trigger plateau (need >3x window for diversify)
        for _ in range(40):
            pd.record(1.5)
        assert pd.detect()
        action = pd.suggest_action()
        assert action in ("diversify", "increase_mutation_rate")

    def test_evolution_loop_with_plateau(self):
        loop = EvolutionLoop()
        report = asyncio.get_event_loop().run_until_complete(loop.run(generations=10))
        assert report.generations_completed == 10
        assert report.total_mutations == 10


class TestConcurrentWorkers:
    """Scenario: multiple tasks run in parallel via ParallelRunner."""

    def test_parallel_execution(self):
        runner = ParallelRunner(max_workers=3)
        tasks = [
            Task(title=f"Task {i}", description=f"Parallel task {i}")
            for i in range(5)
        ]
        results = asyncio.get_event_loop().run_until_complete(runner.run_tasks(tasks))
        assert len(results) == 5
        assert all(r.success for r in results)


class TestRollbackScenario:
    """Scenario: create savepoint, make changes, rollback."""

    def test_rollback_flow(self, tmp_path):
        import pygit2
        # Setup repo with initial commit
        repo = pygit2.init_repository(str(tmp_path), bare=False)
        (tmp_path / "main.py").write_text("# v1")
        index = repo.index
        index.add("main.py")
        index.write()
        tree = index.write_tree()
        sig = pygit2.Signature("Test", "test@test.com")
        repo.create_commit("HEAD", sig, sig, "Initial", tree, [])

        rm = RollbackManager(repo)
        sp = rm.create_savepoint("before-experiment")

        # Make a new commit (simulating a bad change)
        (tmp_path / "main.py").write_text("# v2 - broken")
        index.add("main.py")
        index.write()
        tree = index.write_tree()
        repo.create_commit("HEAD", sig, sig, "Bad change", tree, [repo.head.target])

        # Rollback
        sha = rm.rollback_to("before-experiment")
        assert sha == sp.commit_sha

        # Verify invariants still pass
        reg = InvariantRegistry()
        report = reg.check_all({})
        assert report.passed


class TestPlaybookEvolution:
    """Scenario: playbook records outcomes and prunes harmful ones."""

    def test_playbook_outcome_tracking(self, tmp_path):
        pm = PlaybookManager(playbooks_dir=str(tmp_path))
        # Create a playbook file
        pb_path = tmp_path / "test.md"
        pb_path.write_text("# Test Playbook\n\nA test strategy.")

        pm.load_all()
        playbooks = pm.search("test")
        assert len(playbooks) >= 1

        pb = playbooks[0]
        # Record outcomes using the playbook's id (1 helpful, 6 harmful)
        pm.record_outcome(pb.id, helpful=True)
        for _ in range(6):
            pm.record_outcome(pb.id, helpful=False)

        # Score = 1/7 ≈ 0.14
        assert pb.score() < 0.3
        # Prune harmful playbooks (threshold 0.3, need > 5 interactions: 7 > 5)
        pruned = pm.prune_harmful(threshold=0.3)
        assert pruned >= 1


class TestCanaryDeployment:
    """Scenario: canary deploy, monitor, and promote/rollback."""

    def test_canary_promote_flow(self):
        cd = CanaryDeployer(threshold_pass_rate=0.95)
        canary_id = asyncio.get_event_loop().run_until_complete(
            cd.deploy_canary("feat/optimize-queries")
        )
        assert canary_id

        metrics = asyncio.get_event_loop().run_until_complete(cd.monitor(canary_id))
        assert metrics.test_pass_rate >= 0.95

        result = asyncio.get_event_loop().run_until_complete(cd.promote(canary_id))
        assert result.promoted

    def test_canary_rollback_flow(self):
        cd = CanaryDeployer(threshold_pass_rate=0.99)
        canary_id = asyncio.get_event_loop().run_until_complete(
            cd.deploy_canary("feat/risky-change")
        )

        metrics = asyncio.get_event_loop().run_until_complete(cd.monitor(canary_id))
        if metrics.test_pass_rate < cd.threshold_pass_rate:
            result = asyncio.get_event_loop().run_until_complete(cd.rollback_canary(canary_id))
            assert result.rolled_back


class TestToolForge:
    """Scenario: create, verify, store, and use a forged tool."""

    def test_forge_and_store_tool(self, tmp_path):
        store = ToolStore(store_dir=str(tmp_path / "tools"))

        # Create a simple tool
        tool_code = '''
def get_schema():
    return {"name": "formatter", "description": "Format code"}

def execute(code: str) -> str:
    return code.strip()
'''

        # Verify the tool
        verifier = ToolVerifier()
        report = asyncio.get_event_loop().run_until_complete(verifier.verify(tool_code))
        assert report["passed"]
        assert len(report["issues"]) == 0

        # Store the tool
        store.save("formatter", tool_code, version=1)
        loaded = store.load("formatter")
        assert loaded is not None
        assert "get_schema" in loaded

        # List tools
        tools = store.list_tools()
        assert "formatter" in tools

        # Version history
        history = store.get_version_history("formatter")
        assert len(history) >= 1


class TestInvariantEnforcement:
    """Scenario: invariants enforce safety during evolution."""

    def test_all_invariants_pass_clean_context(self):
        reg = InvariantRegistry()
        report = reg.check_all({
            "test_result": {"passed": True, "failures": 0},
            "security_issues_before": 0,
            "security_issues_after": 0,
            "changed_files": ["src/evolutor/memory/foo.py"],
            "test_count_before": 100,
            "test_count_after": 105,
            "coverage_percent": 85.0,
            "coverage_floor": 60.0,
            "type_check_errors": 0,
        })
        assert report.passed

    def test_multiple_violations_detected(self):
        reg = InvariantRegistry()
        report = reg.check_all({
            "test_result": {"passed": False, "failures": 3},
            "security_issues_before": 0,
            "security_issues_after": 5,
            "coverage_percent": 30.0,
            "coverage_floor": 60.0,
            "type_check_errors": 10,
            "deleted_public_symbols": ["MyClass"],
        })
        assert not report.passed
        assert len(report.violations) >= 4


class TestScratchpadWorkflow:
    """Scenario: scratchpad used as working memory during task execution."""

    def test_scratchpad_task_flow(self):
        sp = Scratchpad(max_entries=50)
        sp.set("task", "Optimize database queries")
        sp.set("context", "PostgreSQL, SQLAlchemy ORM")
        sp.append("findings", "N+1 query in user_list endpoint")
        sp.append("findings", "Missing index on created_at")

        assert sp.get("task") == "Optimize database queries"
        findings = sp.get("findings")
        assert "N+1 query" in findings
        assert "Missing index" in findings

        recent = sp.get_recent(3)
        assert len(recent) == 3

        summary = sp.summarize()
        assert "task" in summary
