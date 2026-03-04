"""Evolution loop — ask, evaluate, tell cycle."""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from evolutor.evolution.archive import EvolutionArchive
from evolutor.evolution.fitness import FitnessEvaluator
from evolutor.evolution.mutator import Mutator
from evolutor.evolution.plateau import PlateauDetector
from evolutor.types.metrics import FitnessVector

logger = structlog.get_logger()


class EvolutionReport(BaseModel):
    generations_completed: int = 0
    best_fitness: float = 0.0
    archive_coverage: float = 0.0
    plateaus_detected: int = 0
    total_mutations: int = 0


class EvolutionLoop:
    """Main evolution loop: ask -> evaluate -> tell."""

    def __init__(
        self,
        archive: EvolutionArchive | None = None,
        evaluator: FitnessEvaluator | None = None,
        mutator: Mutator | None = None,
    ) -> None:
        self.archive = archive or EvolutionArchive()
        self.evaluator = evaluator or FitnessEvaluator()
        self.mutator = mutator or Mutator()
        self.plateau_detector = PlateauDetector()

    async def run(self, generations: int = 10) -> EvolutionReport:
        import os
        import re
        import shutil
        import subprocess
        import tempfile
        import random
        from pathlib import Path

        report = EvolutionReport()
        project_root = Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()

        # Files the evolution loop targets (rotating)
        EVOLVABLE_FILES = [
            "src/evolutor/evolution/plateau.py",
            "src/evolutor/memory/playbooks.py",
            "src/evolutor/kernel/evaluator.py",
            "src/evolutor/orchestrator/worker.py",
        ]

        for gen in range(generations):
            try:
                target = EVOLVABLE_FILES[gen % len(EVOLVABLE_FILES)]
                logger.info("evolution_gen_start", gen=gen, target=target)

                # Step 1: Generate mutation via LLM
                report.total_mutations += 1
                context = f"gen {gen}: improve agent quality, efficiency, or robustness"
                modified_files = await self.mutator.apply_mutation(
                    target_files=[target],
                    project_root=project_root,
                    context=context,
                )

                if not modified_files:
                    logger.warning("mutation_empty_skipping", gen=gen, target=target)
                    report.generations_completed = gen + 1
                    continue

                # Step 2: Evaluate in isolated temp copy (cascade evaluation)
                accepted = False
                pass_rate = 0.0

                with tempfile.TemporaryDirectory() as tmpdir:
                    child_root = Path(tmpdir) / "child"
                    shutil.copytree(
                        project_root, child_root,
                        ignore=shutil.ignore_patterns(
                            "__pycache__", "*.pyc", ".git",
                            ".venv", "node_modules", "*.egg-info", "dist", ".pytest_cache"
                        ),
                    )

                    # Apply mutations to temp copy
                    for filepath, new_content in modified_files.items():
                        dest = child_root / filepath
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(new_content)

                    # CASCADE STAGE 0: Syntax check (ruff) — fast reject
                    ruff_result = subprocess.run(
                        ["python", "-m", "ruff", "check", "--select=E9,F"] +
                        [str(child_root / f) for f in modified_files],
                        capture_output=True, text=True, timeout=15,
                    )
                    if ruff_result.returncode != 0:
                        logger.info(
                            "cascade_stage0_syntax_reject",
                            gen=gen, error=ruff_result.stdout[:300]
                        )
                        self.archive.update_clade_stats(f"gen-{gen}", None, success=False)
                        report.generations_completed = gen + 1
                        continue

                    # CASCADE STAGE 1: Unit tests — reject if tests regress
                    test_result = subprocess.run(
                        [
                            "python", "-m", "pytest", "tests/unit/",
                            "-x", "-q", "--tb=short",
                            "--timeout=30", "-p", "no:warnings",
                        ],
                        capture_output=True, text=True,
                        cwd=child_root, timeout=120,
                        env={**os.environ, "PYTHONPATH": str(child_root / "src")},
                    )
                    output = test_result.stdout + test_result.stderr
                    passed_m = re.search(r"(\d+) passed", output)
                    failed_m = re.search(r"(\d+) failed", output)
                    passed = int(passed_m.group(1)) if passed_m else 0
                    failed = int(failed_m.group(1)) if failed_m else 0
                    total = passed + failed
                    pass_rate = passed / max(total, 1)

                    logger.info(
                        "cascade_stage1_result",
                        gen=gen, pass_rate=f"{pass_rate:.2f}",
                        passed=passed, failed=failed, target=target
                    )

                    if pass_rate < 0.85 or (failed > 0 and total > 5):
                        logger.info("cascade_stage1_reject", gen=gen, pass_rate=pass_rate)
                        self.archive.update_clade_stats(f"gen-{gen}", None, success=False)
                        report.generations_completed = gen + 1
                        continue

                    # ACCEPT: Tests pass — apply to real codebase
                    for filepath, new_content in modified_files.items():
                        (project_root / filepath).write_text(new_content)
                    accepted = True

                fitness = FitnessVector(
                    test_pass_rate=pass_rate,
                    coverage=0.65,
                    complexity=0.5,
                    security_score=1.0,
                )

                # Step 3: Add to archive with CMP tracking
                behavior = [min(fitness.test_pass_rate, 1.0), 0.5]
                parent_id = self.archive.select_parent_by_cmp()
                self.archive.add(
                    solution_id=f"gen-{gen}",
                    fitness=fitness.test_pass_rate + fitness.coverage,
                    behavior=behavior,
                    metadata={"files": list(modified_files.keys()), "gen": gen, "accepted": accepted}
                )
                self.archive.update_clade_stats(f"gen-{gen}", parent_id, success=True)

                # Step 4: Plateau detection
                self.plateau_detector.record(fitness.test_pass_rate)
                if self.plateau_detector.detect():
                    report.plateaus_detected += 1
                    logger.info("plateau_detected", gen=gen, action="diversify_next")

                # Step 5: Commit accepted improvement
                if accepted:
                    subprocess.run(
                        f'git add -A && git commit -m "feat(evolution): gen-{gen} {target} pass_rate={pass_rate:.2f}"',
                        shell=True, cwd=project_root, capture_output=True
                    )
                    logger.info("evolution_gen_accepted_committed", gen=gen, pass_rate=pass_rate)

                report.generations_completed = gen + 1

            except Exception as e:
                logger.error("evolution_gen_error", gen=gen, error=str(e), exc_info=True)
                report.generations_completed = gen + 1

        try:
            stats = self.archive.get_stats()
            report.best_fitness = stats.best_fitness
            report.archive_coverage = stats.coverage
        except Exception:
            pass

        logger.info("evolution_complete", report=report.model_dump())
        return report
