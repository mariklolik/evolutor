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
        report = EvolutionReport()

        for gen in range(generations):
            # Ask: generate mutation
            mutation = self.mutator.generate_mutation(["src/"], f"generation {gen}")
            report.total_mutations += 1

            # Evaluate: compute fitness (placeholder)
            fitness = FitnessVector(
                test_pass_rate=0.9 + (gen * 0.01),
                coverage=0.7 + (gen * 0.02),
                complexity=0.5 - (gen * 0.01),
                security_score=0.95,
            )

            # Tell: add to archive
            behavior = [min(fitness.coverage, 1.0), min(1.0 - fitness.complexity, 1.0)]
            self.archive.add(
                solution_id=f"gen-{gen}",
                fitness=fitness.test_pass_rate + fitness.coverage,
                behavior=behavior,
            )

            # Check plateau
            self.plateau_detector.record(fitness.test_pass_rate + fitness.coverage)
            if self.plateau_detector.detect():
                report.plateaus_detected += 1
                logger.info("plateau_detected", generation=gen)

            report.generations_completed = gen + 1

        stats = self.archive.get_stats()
        report.best_fitness = stats.best_fitness
        report.archive_coverage = stats.coverage
        logger.info("evolution_complete", report=report.model_dump())
        return report
