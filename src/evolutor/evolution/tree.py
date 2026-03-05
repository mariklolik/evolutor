"""Evolution tree — HGM-style node and tree for agent variant tracking.

Stores agent variants as nodes in a tree. Each node holds the full agent code,
binary utility measures per task, and lineage information.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field


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
