"""Unit tests for evolution system — tree, mutator, cascade."""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from evolutor.evolution.tree import EvolutionNode, EvolutionTree
from evolutor.evolution.mutator import MutationType, Mutator, DIAGNOSIS_PROMPT
from evolutor.evolution.cascade import CascadeResult, CascadingEvaluator


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_tasks(n: int = 5) -> list[dict]:
    return [{"instance_id": f"task_{i}"} for i in range(n)]


# ─── Tree tests ──────────────────────────────────────────────────────────────

def test_tree_creation():
    t = EvolutionTree("# code", make_tasks(), 100)
    assert "root" in t.nodes
    assert t.n_nodes == 1
    assert t.n_evals == 0
    assert t.nodes["root"].code == "# code"


def test_add_child():
    t = EvolutionTree("# code", make_tasks(), 100)
    cid = t.add_child("root", "# child", "improve_system_prompt", "test mutation")
    assert cid in t.nodes
    assert cid in t.nodes["root"].children
    assert t.n_nodes == 2
    assert t.nodes[cid].parent_id == "root"


def test_record_eval():
    t = EvolutionTree("# code", make_tasks(), 100)
    assert t.n_evals == 0
    t.record_eval("root", "task_0", True)
    assert t.n_evals == 1
    assert t.nodes["root"].utility_measures == [1]
    assert "task_0" in t.nodes["root"].evaluated_tasks
    t.record_eval("root", "task_1", False)
    assert t.n_evals == 2
    assert t.nodes["root"].utility_measures == [1, 0]


def test_descendant_evals_recursive():
    t = EvolutionTree("# root", make_tasks(10), 100)
    cid = t.add_child("root", "# child", "improve_system_prompt", "child")
    gcid = t.add_child(cid, "# grand", "add_tool_template", "grand")
    t.record_eval("root", "task_0", True)
    t.record_eval(cid, "task_1", True)
    t.record_eval(gcid, "task_2", False)
    evals = t.get_descendant_evals("root")
    assert len(evals) > 0


def test_thompson_sample_returns_valid_node():
    t = EvolutionTree("# code", make_tasks(), 100)
    t.record_eval("root", "task_0", True)
    t.add_child("root", "# child", "improve_system_prompt", "x")
    np.random.seed(99)
    for _ in range(10):
        selected = t.thompson_sample()
        assert selected in t.nodes


def test_expansion_rule():
    t = EvolutionTree("# code", make_tasks(10), 100)
    for i in range(5):
        t.record_eval("root", f"task_{i}", True)
    # 5**0.6 ≈ 2.63 >= 0 non-root nodes → should expand
    assert t.should_expand()
    # Add 3 children: 5**0.6 ≈ 2.63 < 3 → should NOT expand
    for i in range(3):
        t.add_child("root", f"# child {i}", "improve_system_prompt", f"c{i}")
    assert not t.should_expand()


def test_json_persistence_roundtrip():
    t = EvolutionTree("# seed", make_tasks(), 50)
    t.record_eval("root", "task_0", True)
    t.record_eval("root", "task_1", False)
    cid = t.add_child("root", "# child", "add_tool_template", "desc")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        t.save_state(path)
        t2 = EvolutionTree.load_state(path)
        assert t2.n_evals == t.n_evals
        assert t2.n_nodes == t.n_nodes
        assert cid in t2.nodes
        assert t2.nodes["root"].utility_measures == [1, 0]
    finally:
        os.unlink(path)


def test_get_best_agent_min_evals():
    t = EvolutionTree("# seed", make_tasks(10), 100)
    # Root gets only 2 evals (below min 3)
    t.record_eval("root", "task_0", True)
    t.record_eval("root", "task_1", True)
    # Child gets 3 evals (qualifies)
    cid = t.add_child("root", "# child", "improve_system_prompt", "x")
    t.record_eval(cid, "task_2", True)
    t.record_eval(cid, "task_3", True)
    t.record_eval(cid, "task_4", True)
    best = t.get_best_agent()
    # Only child qualifies (3 evals) — should return child
    assert best.id == cid


def test_mean_utility_default():
    n = EvolutionNode(
        id="x", code="y", parent_id=None, children=[],
        utility_measures=[], evaluated_tasks=[],
        mutation_type="seed", mutation_description="", created_at=0.0,
    )
    assert n.mean_utility == 0.5  # neutral prior for unexplored


# ─── Mutator tests ───────────────────────────────────────────────────────────

def test_mutation_types_exactly_five():
    types = set(m.value for m in MutationType)
    expected = {
        "improve_system_prompt", "add_tool_template", "improve_reflection",
        "add_workflow_hint", "optimize_parameters",
    }
    assert types == expected


def test_extract_code_marker_format():
    m = Mutator()
    text = "===FILE: seed_agent.py===\nimport os\ndef solve_task(): pass\n===END==="
    code = m.extract_code_from_response(text)
    assert "import os" in code
    assert "def solve_task" in code


def test_extract_code_markdown_format():
    m = Mutator()
    text = "Some analysis...\n```python\nimport os\ndef f(): pass\n```\nDone."
    code = m.extract_code_from_response(text)
    assert "import os" in code


def test_extract_code_fallback_not_empty():
    m = Mutator()
    fallback = "# fallback"
    result = m.extract_code_from_response("nothing useful here", fallback_code=fallback)
    assert result  # Never empty


def test_diagnosis_prompt_has_placeholders():
    assert "{agent_code}" in DIAGNOSIS_PROMPT or "{parent_code}" in DIAGNOSIS_PROMPT
    assert "MUTATION_TYPE" in DIAGNOSIS_PROMPT
    assert "CODE" in DIAGNOSIS_PROMPT
    assert "{failed_task_logs}" in DIAGNOSIS_PROMPT


# ─── Cascade tests ───────────────────────────────────────────────────────────

def test_stage0_rejects_syntax_errors():
    e = CascadingEvaluator.__new__(CascadingEvaluator)
    assert not e._stage0_syntax("def foo( invalid")
    assert not e._stage0_syntax("x = [unclosed")


def test_stage0_accepts_valid():
    e = CascadingEvaluator.__new__(CascadingEvaluator)
    assert e._stage0_syntax("x = 1")
    assert e._stage0_syntax("import os\ndef foo(): pass")
    assert e._stage0_syntax("")  # Empty is valid Python


def test_cascade_result_fields():
    r = CascadeResult(
        passed=False,
        stage_reached="stage0_syntax",
        pass_rate=0.0,
        tasks_passed=0,
        tasks_total=0,
        rejection_reason="syntax error",
        agent_logs="",
    )
    assert r.passed is False
    assert r.stage_reached == "stage0_syntax"
    assert r.rejection_reason == "syntax error"
    assert r.tasks_passed == 0
