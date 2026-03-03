"""Benchmarks for evolution engine."""

from __future__ import annotations

from evolutor.evolution.archive import EvolutionArchive
from evolutor.evolution.fitness import FitnessEvaluator
from evolutor.evolution.mutator import Mutator
from evolutor.evolution.plateau import PlateauDetector
from evolutor.types.metrics import FitnessVector


def test_archive_add(benchmark):
    archive = EvolutionArchive()
    benchmark(archive.add, "sol-1", 0.8, [0.5, 0.5])


def test_fitness_compare(benchmark):
    fe = FitnessEvaluator()
    a = FitnessVector(test_pass_rate=1.0, coverage=0.9, complexity=0.2, security_score=1.0)
    b = FitnessVector(test_pass_rate=0.8, coverage=0.7, complexity=0.5, security_score=0.8)
    benchmark(fe.compare, a, b)


def test_mutation_selection(benchmark):
    m = Mutator()
    benchmark(m.select_mutation_type, "slow performance code")


def test_plateau_detection(benchmark):
    pd = PlateauDetector(window_size=20)
    for i in range(100):
        pd.record(1.0)

    def detect():
        pd.record(1.0)
        return pd.detect()

    benchmark(detect)
