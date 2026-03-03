"""Unit tests for git operations modules."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pygit2
import pytest

from evolutor.git.ops import GitOps
from evolutor.git.branching import BranchStrategy
from evolutor.git.audit import AuditLog, AuditEntry


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repository with an initial commit."""
    repo = pygit2.init_repository(str(tmp_path), bare=False)
    # Create initial file and commit
    file_path = tmp_path / "README.md"
    file_path.write_text("# Test repo\n")
    index = repo.index
    index.add("README.md")
    index.write()
    tree = index.write_tree()
    sig = pygit2.Signature("Test", "test@test.com")
    repo.create_commit("HEAD", sig, sig, "Initial commit", tree, [])
    return tmp_path


@pytest.fixture
def git_ops(tmp_repo):
    return GitOps(tmp_repo)


class TestGitOps:
    def test_current_branch(self, git_ops):
        assert git_ops.current_branch() == "master"

    def test_create_branch(self, git_ops):
        git_ops.create_branch("test-branch")
        assert "test-branch" in git_ops.repo.branches

    def test_checkout(self, git_ops):
        git_ops.create_branch("feature")
        git_ops.checkout("feature")
        assert git_ops.current_branch() == "feature"

    def test_stage_and_commit(self, git_ops, tmp_repo):
        (tmp_repo / "new_file.txt").write_text("hello")
        git_ops.stage_files(["new_file.txt"])
        sha = git_ops.commit("Add new file")
        assert sha
        log = git_ops.get_log(max_count=1)
        assert log[0]["message"] == "Add new file"

    def test_get_log(self, git_ops):
        log = git_ops.get_log()
        assert len(log) >= 1
        assert log[0]["message"] == "Initial commit"

    def test_get_diff_empty(self, git_ops):
        diff = git_ops.get_diff()
        assert isinstance(diff, str)

    def test_get_file_at_ref(self, git_ops):
        content = git_ops.get_file_at_ref("README.md", "HEAD")
        assert "# Test repo" in content

    def test_merge(self, git_ops, tmp_repo):
        git_ops.create_branch("to-merge")
        git_ops.checkout("to-merge")
        (tmp_repo / "merge_file.txt").write_text("merge content")
        git_ops.stage_files(["merge_file.txt"])
        git_ops.commit("Merge branch commit")
        git_ops.checkout("master")
        git_ops.merge("to-merge")


class TestBranchStrategy:
    def test_generate_branch_name(self):
        name = BranchStrategy.generate_branch_name("feat/", "T-001", "Add login page")
        assert name.startswith("feat/T-001/")
        assert "add-login-page" in name

    def test_parse_branch_name(self):
        parsed = BranchStrategy.parse_branch_name("feat/T-001/add-login")
        assert parsed is not None
        assert parsed.prefix == "feat/"
        assert parsed.task_id == "T-001"

    def test_parse_branch_name_invalid(self):
        parsed = BranchStrategy.parse_branch_name("main")
        assert parsed is None

    def test_invalid_prefix(self):
        with pytest.raises(ValueError):
            BranchStrategy.generate_branch_name("bad/", "T-001", "test")

    def test_get_evolution_branches(self, tmp_repo):
        repo = pygit2.Repository(str(tmp_repo))
        commit = repo.head.peel(pygit2.Commit)
        repo.branches.create("evo/gen-1", commit)
        repo.branches.create("feat/something", commit)
        bs = BranchStrategy(repo)
        evo_branches = bs.get_evolution_branches()
        assert "evo/gen-1" in evo_branches
        assert "feat/something" not in evo_branches

    def test_get_merge_candidates(self, tmp_repo):
        repo = pygit2.Repository(str(tmp_repo))
        commit = repo.head.peel(pygit2.Commit)
        repo.branches.create("feat/new", commit)
        bs = BranchStrategy(repo)
        candidates = bs.get_merge_candidates("master")
        assert "feat/new" in candidates


class TestAuditLog:
    def test_record_and_get_history(self, tmp_repo):
        repo = pygit2.Repository(str(tmp_repo))
        audit = AuditLog(repo)
        sha = str(repo.head.peel(pygit2.Commit).id)
        entry = AuditEntry(action="test_action", details="test details")
        audit.record_action(sha, entry)
        history = audit.get_history()
        assert len(history) >= 1
        assert history[0].action == "test_action"

    def test_get_actions_for_commit(self, tmp_repo):
        repo = pygit2.Repository(str(tmp_repo))
        audit = AuditLog(repo)
        sha = str(repo.head.peel(pygit2.Commit).id)
        entry = AuditEntry(action="specific_action")
        audit.record_action(sha, entry)
        actions = audit.get_actions_for_commit(sha)
        assert any(a.action == "specific_action" for a in actions)
