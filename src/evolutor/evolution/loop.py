"""Evolution loop — HGM tree + MAP-Elites + cascading eval for seed_agent.py."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from pydantic import BaseModel

from evolutor.evolution.archive import EvolutionArchive
from evolutor.evolution.cascade import CascadingEvaluator
from evolutor.evolution.mutator import Mutator
from evolutor.evolution.plateau import PlateauDetector
from evolutor.evolution.tree import EvolutionTree
from evolutor.kernel.invariants import KernelIntegrityChecker
from evolutor.swebench.harness import eval_agent_code_docker

logger = structlog.get_logger()

SEED_AGENT_PATH = "src/evolutor/swebench/seed_agent.py"
EVOLUTION_STATE_PATH = "results/evolution_state.json"


@dataclass
class EvolutionConfig:
    eval_budget: int = 100
    expansion_alpha: float = 0.6
    max_steps_per_task: int = 50
    task_timeout: int = 600
    mutation_timeout: int = 120
    plateau_window: int = 40
    cascade_max_stage: int = 1


class EvolutionReport(BaseModel):
    evals_completed: int = 0
    tree_nodes: int = 1
    best_fitness: float = 0.0
    best_agent_id: str = "root"
    archive_coverage: float = 0.0
    plateaus_detected: int = 0
    cascade_rejections: int = 0
    mutations_attempted: int = 0
    mutations_accepted: int = 0
    eval_log: list = []


def get_failure_logs(node, tree) -> str:
    """Build failure context string from a node's failed evaluations."""
    if not node.evaluated_tasks or not node.utility_measures:
        return "(no evaluations yet)"
    failures = []
    for task_id, passed in zip(node.evaluated_tasks, node.utility_measures):
        if not passed:
            failures.append(f"- {task_id}: FAILED")
    if not failures:
        return "(all evaluated tasks passed)"
    return "\n".join(failures[:10])


def run_evolution(
    config: EvolutionConfig,
    seed_code: str,
    tasks: list,
    project_root: str,
) -> EvolutionReport:
    """Main HGM evolution loop: tree expansion + measurement + cascading eval.

    NOTE: For future scaling, consider MLflow for experiment tracking,
    TensorBoard for real-time fitness curves, and Ray for distributed
    parallel evaluation across GPUs.
    """
    project_root = Path(project_root)
    os.makedirs(project_root / "results", exist_ok=True)

    # Initialize components
    tree = EvolutionTree(seed_code, tasks, config.eval_budget)
    archive = EvolutionArchive()
    mutator = Mutator()
    cascade = CascadingEvaluator(tasks, project_root)
    plateau = PlateauDetector()
    kernel = KernelIntegrityChecker(project_root)

    report = EvolutionReport()

    while tree.n_evals < config.eval_budget:
        # Kernel integrity check
        try:
            kernel.check()
        except Exception as e:
            logger.warning("kernel_tamper_detected", error=str(e))

        if tree.should_expand(config.expansion_alpha):
            # EXPAND: mutate a parent to create a child
            report.mutations_attempted += 1
            parent_id = tree.thompson_sample(for_expansion=True)
            parent = tree.nodes[parent_id]
            failed_logs = get_failure_logs(parent, tree)

            try:
                child_code, mut_type, description = mutator.diagnose_and_mutate(
                    parent.code, failed_logs
                )
            except Exception as e:
                logger.error("mutation_error", error=str(e))
                continue

            # Cascade evaluation: reject bad mutations early
            cascade_result = cascade.evaluate(child_code, max_stage=config.cascade_max_stage)
            if not cascade_result.passed:
                report.cascade_rejections += 1
                logger.info("cascade_reject", stage=cascade_result.stage_reached,
                            reason=cascade_result.rejection_reason)
                continue

            # Accept child into tree and archive
            child_id = tree.add_child(parent_id, child_code, mut_type, description)
            archive.add_with_behavior(child_id, cascade_result.pass_rate, child_code)
            report.mutations_accepted += 1
            logger.info("mutation_accepted", parent=parent_id, child=child_id,
                        mut_type=mut_type, stage=cascade_result.stage_reached)

        else:
            # MEASURE: evaluate existing node on a new task
            node_id = tree.thompson_sample(for_expansion=False)
            task = tree.select_unevaluated_task(node_id)
            if task is None:
                continue  # All tasks evaluated for this node

            node = tree.nodes[node_id]
            task_id = task["instance_id"]
            try:
                result = eval_agent_code_docker(
                    agent_code=node.code,
                    task=task,
                    project_root=project_root,
                    model=os.environ.get("EVOLUTOR_MODEL", "claude-sonnet-4-6"),
                    timeout=config.task_timeout,
                )
                passed = result.passed
            except Exception as e:
                logger.error("eval_error", node=node_id, task=task_id, error=str(e))
                passed = False

            tree.record_eval(node_id, task_id, passed)
            archive.add_with_behavior(node_id, node.mean_utility, node.code)

            status = "PASS" if passed else "FAIL"
            log_entry = f"eval {tree.n_evals}: node={node_id} task={task_id} {status}"
            report.eval_log.append(log_entry)
            logger.info("eval_result", n_evals=tree.n_evals, node=node_id,
                        task=task_id, passed=passed, mean=round(node.mean_utility, 3))

            # Plateau detection every 20 evals
            plateau.record(node.mean_utility)
            if tree.n_evals % 20 == 0 and plateau.should_diversify(config.plateau_window):
                report.plateaus_detected += 1
                logger.info("plateau_detected", n_evals=tree.n_evals)

        # Persist state
        try:
            tree.save_state(str(project_root / EVOLUTION_STATE_PATH))
        except Exception:
            pass

    # Build final report
    best_node = tree.get_best_agent()
    report.evals_completed = tree.n_evals
    report.tree_nodes = tree.n_nodes
    report.best_fitness = best_node.mean_utility
    report.best_agent_id = best_node.id
    report.archive_coverage = len(archive.get_underexplored_cells()) / 100.0
    logger.info("evolution_complete", **report.model_dump(exclude={"eval_log"}))
    return report
