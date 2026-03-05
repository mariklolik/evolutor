"""Evolution tree — HGM-style node and tree for agent variant tracking.

Stores agent variants as nodes in a tree. Each node holds the full agent code,
binary utility measures per task, and lineage information.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

import numpy as np


@dataclass
class EvolutionNode:
    """One agent variant in the evolution tree."""
    id: str
    code: str                         # Full seed_agent.py content
    parent_id: str | None
    children: list[str]               # Child node IDs
    utility_measures: list[int]       # Binary 0/1 per task evaluation
    evaluated_tasks: list[str]        # Instance IDs already evaluated
    mutation_type: str
    mutation_description: str
    created_at: float

    @property
    def num_evals(self) -> int:
        return len(self.utility_measures)

    @property
    def mean_utility(self) -> float:
        if not self.utility_measures:
            return 0.5  # Unexplored nodes get neutral prior
        return sum(self.utility_measures) / len(self.utility_measures)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "parent_id": self.parent_id,
            "children": list(self.children),
            "utility_measures": list(self.utility_measures),
            "evaluated_tasks": list(self.evaluated_tasks),
            "mutation_type": self.mutation_type,
            "mutation_description": self.mutation_description,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvolutionNode":
        return cls(
            id=data["id"],
            code=data["code"],
            parent_id=data.get("parent_id"),
            children=list(data.get("children", [])),
            utility_measures=list(data.get("utility_measures", [])),
            evaluated_tasks=list(data.get("evaluated_tasks", [])),
            mutation_type=data.get("mutation_type", ""),
            mutation_description=data.get("mutation_description", ""),
            created_at=data.get("created_at", 0.0),
        )


class EvolutionTree:
    """Tree of agent variants for HGM-style Thompson sampling and expansion."""

    def __init__(self, seed_code: str, tasks: list[dict], eval_budget: int):
        self.tasks = tasks
        self.eval_budget = eval_budget
        self.nodes: dict[str, EvolutionNode] = {}

        root = EvolutionNode(
            id="root",
            code=seed_code,
            parent_id=None,
            children=[],
            utility_measures=[],
            evaluated_tasks=[],
            mutation_type="seed",
            mutation_description="initial seed agent",
            created_at=time.time(),
        )
        self.nodes["root"] = root

    @property
    def n_evals(self) -> int:
        return sum(node.num_evals for node in self.nodes.values())

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    def add_child(
        self,
        parent_id: str,
        child_code: str,
        mutation_type: str,
        mutation_description: str,
    ) -> str:
        """Create a child node and attach it to parent. Returns new node id."""
        child_id = uuid.uuid4().hex[:8]
        child = EvolutionNode(
            id=child_id,
            code=child_code,
            parent_id=parent_id,
            children=[],
            utility_measures=[],
            evaluated_tasks=[],
            mutation_type=mutation_type,
            mutation_description=mutation_description,
            created_at=time.time(),
        )
        self.nodes[child_id] = child
        self.nodes[parent_id].children.append(child_id)
        return child_id

    def record_eval(self, node_id: str, task_id: str, passed: bool) -> None:
        """Record a binary task evaluation result for a node."""
        node = self.nodes[node_id]
        node.utility_measures.append(1 if passed else 0)
        node.evaluated_tasks.append(task_id)

    def select_unevaluated_task(self, node_id: str) -> dict | None:
        """Return first task not yet evaluated by this node, or None."""
        node = self.nodes[node_id]
        evaluated = set(node.evaluated_tasks)
        for task in self.tasks:
            if task["instance_id"] not in evaluated:
                return task
        return None

    def get_descendant_evals(self, node_id: str, num_pseudo: int = 10) -> list[float]:
        """HGM CMP: recursively collect descendant utility measures.

        For the current node:
          - 0 evals: contribute empty list
          - 1..num_pseudo-1 evals: contribute [mean_utility]*num_pseudo (pseudo-counts)
          - >= num_pseudo evals: contribute raw utility_measures
        Then recurse into all children and extend with their raw utility_measures.
        """
        node = self.nodes[node_id]
        if node.num_evals == 0:
            evals: list[float] = []
        elif node.num_evals < num_pseudo:
            evals = [node.mean_utility] * num_pseudo
        else:
            evals = list(node.utility_measures)

        for child_id in node.children:
            child = self.nodes[child_id]
            evals.extend(child.utility_measures)
            # Recurse into grandchildren
            for grandchild_id in child.children:
                evals.extend(self.get_descendant_evals(grandchild_id, num_pseudo))

        return evals

    def thompson_sample(self, for_expansion: bool = True) -> str:
        """Select node via Thompson sampling (HGM CMP with tau cooling).

        tau = eval_budget / max(1, eval_budget - n_evals)
        For expansion: use CMP descendant evals.
        For measurement: use node's own utility_measures.
        """
        tau = self.eval_budget / max(1, self.eval_budget - self.n_evals)
        best_theta = -1.0
        best_id = "root"

        for node_id, node in self.nodes.items():
            if for_expansion:
                evals = self.get_descendant_evals(node_id)
            else:
                evals = list(node.utility_measures)

            successes = sum(evals)
            failures = len(evals) - successes
            alpha = tau * (1 + successes)
            beta_param = tau * (1 + failures)
            theta = float(np.random.beta(max(alpha, 0.01), max(beta_param, 0.01)))
            if theta > best_theta:
                best_theta = theta
                best_id = node_id

        return best_id

    def should_expand(self, alpha: float = 0.6) -> bool:
        """HGM expansion rule: n_evals^alpha >= n_nodes (excluding root)."""
        n_nodes = len(self.nodes) - 1
        return self.n_evals ** alpha >= n_nodes

    def get_best_agent(self) -> EvolutionNode:
        """Return node with highest mean_utility among nodes with >=3 evals."""
        candidates = [
            node for node in self.nodes.values()
            if node.num_evals >= 3
        ]
        if not candidates:
            return self.nodes["root"]
        return max(candidates, key=lambda n: n.mean_utility)

    def save_state(self, path: str) -> None:
        """Serialize tree to JSON file."""
        state = {
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "tasks": self.tasks,
            "eval_budget": self.eval_budget,
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    @classmethod
    def load_state(cls, path: str) -> "EvolutionTree":
        """Reconstruct tree from JSON file."""
        with open(path) as f:
            state = json.load(f)

        tree = cls.__new__(cls)
        tree.tasks = state["tasks"]
        tree.eval_budget = state["eval_budget"]
        tree.nodes = {
            nid: EvolutionNode.from_dict(data)
            for nid, data in state["nodes"].items()
        }
        return tree
