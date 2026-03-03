"""Unit tests for memory modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pygit2
import pytest

from evolutor.memory.knowledge_graph import KnowledgeGraph
from evolutor.memory.git_memory import GitMemory, ChangeRecord
from evolutor.memory.playbooks import PlaybookManager
from evolutor.memory.scratchpad import Scratchpad
from evolutor.memory.persistent import PersistentMemory
from evolutor.types.memory import Playbook


class TestKnowledgeGraph:
    def test_parse_file(self, tmp_path):
        py_file = tmp_path / "sample.py"
        py_file.write_text("""
class MyClass:
    def method(self):
        pass

def standalone_func():
    pass
""")
        kg = KnowledgeGraph()
        nodes = kg.parse_file(str(py_file))
        names = [n.name for n in nodes]
        assert "MyClass" in names
        assert "standalone_func" in names

    def test_add_and_query_by_name(self):
        from evolutor.types.memory import KnowledgeNode, NodeKind
        kg = KnowledgeGraph()
        node = KnowledgeNode(kind=NodeKind.function, name="test_fn", file_path="test.py")
        kg.add_node(node)
        results = kg.query_by_name("test_fn")
        assert len(results) == 1

    def test_query_by_file(self):
        from evolutor.types.memory import KnowledgeNode, NodeKind
        kg = KnowledgeGraph()
        kg.add_node(KnowledgeNode(kind=NodeKind.function, name="a", file_path="f1.py"))
        kg.add_node(KnowledgeNode(kind=NodeKind.function, name="b", file_path="f2.py"))
        results = kg.query_by_file("f1.py")
        assert len(results) == 1
        assert results[0].name == "a"

    def test_edges(self):
        from evolutor.types.memory import KnowledgeNode, NodeKind
        kg = KnowledgeGraph()
        n1 = KnowledgeNode(kind=NodeKind.cls, name="A", file_path="a.py")
        n2 = KnowledgeNode(kind=NodeKind.function, name="b", file_path="a.py")
        kg.add_node(n1)
        kg.add_node(n2)
        kg.add_edge(n1.id, n2.id, "contains")
        deps = kg.get_dependencies(n1.id)
        assert len(deps) == 1
        assert deps[0].name == "b"

    def test_to_context_string(self):
        from evolutor.types.memory import KnowledgeNode, NodeKind
        kg = KnowledgeGraph()
        kg.add_node(KnowledgeNode(kind=NodeKind.function, name="fn1", file_path="test.py", start_line=1))
        ctx = kg.to_context_string("test.py")
        assert "fn1" in ctx


class TestGitMemory:
    @pytest.fixture
    def git_repo(self, tmp_path):
        repo = pygit2.init_repository(str(tmp_path), bare=False)
        (tmp_path / "file.py").write_text("initial")
        index = repo.index
        index.add("file.py")
        index.write()
        tree = index.write_tree()
        sig = pygit2.Signature("Test", "test@test.com")
        repo.create_commit("HEAD", sig, sig, "feat: initial", tree, [])
        # Second commit
        (tmp_path / "file.py").write_text("updated")
        index.add("file.py")
        index.write()
        tree = index.write_tree()
        repo.create_commit("HEAD", sig, sig, "fix: update", tree, [repo.head.target])
        return tmp_path

    def test_get_recent_changes(self, git_repo):
        gm = GitMemory(git_repo)
        changes = gm.get_recent_changes()
        assert len(changes) >= 2

    def test_get_file_history(self, git_repo):
        gm = GitMemory(git_repo)
        history = gm.get_file_history("file.py")
        assert len(history) >= 1

    def test_extract_patterns(self, git_repo):
        gm = GitMemory(git_repo)
        patterns = gm.extract_patterns()
        assert "feat:" in patterns or "fix:" in patterns

    def test_summarize_branch(self, git_repo):
        gm = GitMemory(git_repo)
        summary = gm.summarize_branch()
        assert "commits" in summary.lower() or "branch" in summary.lower()


class TestPlaybooks:
    def test_load_all(self):
        pm = PlaybookManager("playbooks")
        pbs = pm.load_all()
        assert len(pbs) >= 4  # python, typescript, rust, general

    def test_get_by_language(self):
        pm = PlaybookManager("playbooks")
        pm.load_all()
        py_pbs = pm.get_by_language("python")
        assert len(py_pbs) >= 1

    def test_search(self):
        pm = PlaybookManager("playbooks")
        pm.load_all()
        results = pm.search("pytest")
        assert len(results) >= 1

    def test_record_outcome(self):
        pm = PlaybookManager("playbooks")
        pbs = pm.load_all()
        pb = pbs[0]
        pm.record_outcome(pb.id, helpful=True)
        assert pb.helpful_count == 1

    def test_prune_harmful(self):
        pm = PlaybookManager("playbooks")
        pm.load_all()
        # Add a playbook that's mostly harmful
        bad_pb = Playbook(name="bad", language="test", content="bad advice",
                         helpful_count=1, harmful_count=10)
        pm._playbooks[bad_pb.id] = bad_pb
        pruned = pm.prune_harmful(threshold=0.3)
        assert pruned >= 1


class TestScratchpad:
    def test_set_and_get(self):
        sp = Scratchpad()
        sp.set("key1", "value1")
        assert sp.get("key1") == "value1"

    def test_get_nonexistent(self):
        sp = Scratchpad()
        assert sp.get("missing") is None

    def test_append(self):
        sp = Scratchpad()
        sp.set("log", "line1\n")
        sp.append("log", "line2\n")
        assert sp.get("log") == "line1\nline2\n"

    def test_get_recent(self):
        sp = Scratchpad()
        for i in range(20):
            sp.set(f"k{i}", f"v{i}")
        recent = sp.get_recent(5)
        assert len(recent) == 5

    def test_clear(self):
        sp = Scratchpad()
        sp.set("x", "y")
        sp.clear()
        assert sp.get("x") is None

    def test_max_entries(self):
        sp = Scratchpad(max_entries=5)
        for i in range(10):
            sp.set(f"k{i}", f"v{i}")
        assert sp.get("k0") is None  # evicted
        assert sp.get("k9") == "v9"  # still there

    def test_summarize(self):
        sp = Scratchpad()
        sp.set("plan", "implement feature X")
        summary = sp.summarize()
        assert "plan" in summary


class TestPersistentMemory:
    def test_local_store_and_search(self):
        pm = PersistentMemory(use_local=True)
        pm.store("Python best practices for testing")
        pm.store("Rust memory safety patterns")
        results = pm.search("Python")
        assert len(results) >= 1

    def test_get_relevant_context(self):
        pm = PersistentMemory(use_local=True)
        pm.store("Use pytest fixtures for test setup")
        ctx = pm.get_relevant_context("pytest")
        assert "pytest" in ctx

    def test_forget(self):
        pm = PersistentMemory(use_local=True)
        mid = pm.store("temporary note")
        assert pm.forget(mid) is True
