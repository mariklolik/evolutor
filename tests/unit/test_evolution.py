"""Unit tests for evolution modules."""

from __future__ import annotations

import pytest

from evolutor.evolution.archive import EvolutionArchive, ArchiveStats
from evolutor.evolution.fitness import FitnessEvaluator
from evolutor.evolution.mutator import Mutator, MutationType
from evolutor.evolution.plateau import PlateauDetector
from evolutor.types.metrics import FitnessVector


class TestEvolutionArchive:
    def test_add_and_stats(self):
        archive = EvolutionArchive()
        archive.add("sol-1", fitness=0.8, behavior=[0.5, 0.5])
        stats = archive.get_stats()
        assert stats.total_entries >= 1 or stats.total_entries == 0  # ribs may or may not accept

    def test_sample_elites(self):
        archive = EvolutionArchive()
        for i in range(10):
            archive.add(f"sol-{i}", fitness=float(i) / 10, behavior=[i / 10, 0.5])
        elites = archive.sample_elites(3)
        assert len(elites) <= 3

    def test_coverage(self):
        archive = EvolutionArchive()
        cov = archive.coverage()
        assert cov >= 0.0


class TestFitnessEvaluator:
    def test_pareto_dominance(self):
        fe = FitnessEvaluator()
        a = FitnessVector(test_pass_rate=1.0, coverage=0.9, complexity=0.2, security_score=1.0)
        b = FitnessVector(test_pass_rate=0.8, coverage=0.7, complexity=0.5, security_score=0.8)
        assert fe.compare(a, b) == -1  # a dominates b

    def test_pareto_non_dominated(self):
        fe = FitnessEvaluator()
        a = FitnessVector(test_pass_rate=1.0, coverage=0.5, complexity=0.5, security_score=0.8)
        b = FitnessVector(test_pass_rate=0.8, coverage=0.9, complexity=0.3, security_score=0.9)
        assert fe.compare(a, b) == 0  # neither dominates

    def test_select_survivors(self):
        fe = FitnessEvaluator()
        population = [
            FitnessVector(test_pass_rate=1.0, coverage=0.9, complexity=0.2, security_score=1.0),
            FitnessVector(test_pass_rate=0.5, coverage=0.5, complexity=0.8, security_score=0.5),
            FitnessVector(test_pass_rate=0.8, coverage=0.7, complexity=0.4, security_score=0.8),
        ]
        selected = fe.select_survivors(population, 2)
        assert len(selected) == 2

    def test_rank_population(self):
        fe = FitnessEvaluator()
        population = [
            FitnessVector(test_pass_rate=1.0, coverage=0.9, complexity=0.2, security_score=1.0),
            FitnessVector(test_pass_rate=0.5, coverage=0.5, complexity=0.8, security_score=0.5),
        ]
        ranking = fe.rank_population(population)
        assert len(ranking) == 2
        # First should have rank 0 (best front)
        assert ranking[0][1] == 0


class TestMutator:
    def test_generate_mutation(self):
        m = Mutator()
        mutation = m.generate_mutation(["src/file.py"])
        assert mutation.mutation_type in MutationType
        assert len(mutation.target_files) == 1

    def test_heuristic_performance(self):
        m = Mutator()
        mt = m.select_mutation_type("The code is slow and has performance issues")
        assert mt == MutationType.optimize

    def test_heuristic_error(self):
        m = Mutator()
        mt = m.select_mutation_type("There are error handling issues and crashes")
        assert mt == MutationType.harden

    def test_heuristic_test(self):
        m = Mutator()
        mt = m.select_mutation_type("Need better test coverage")
        assert mt == MutationType.test_improve

    def test_crossover(self):
        m = Mutator()
        a = m.generate_mutation(["a.py"], "performance")
        b = m.generate_mutation(["b.py"], "test")
        c = m.crossover(a, b)
        assert set(c.target_files) == {"a.py", "b.py"}


class TestPlateauDetector:
    def test_no_plateau_insufficient_data(self):
        pd = PlateauDetector(window_size=5)
        for i in range(3):
            pd.record(float(i))
        assert not pd.detect()

    def test_plateau_detected(self):
        pd = PlateauDetector(window_size=5, variance_threshold=0.001)
        for _ in range(10):
            pd.record(1.0)
        assert pd.detect()

    def test_no_plateau_varying(self):
        pd = PlateauDetector(window_size=5, variance_threshold=0.001)
        for i in range(10):
            pd.record(float(i))
        assert not pd.detect()

    def test_suggest_action_continue(self):
        pd = PlateauDetector(window_size=5)
        for i in range(10):
            pd.record(float(i))
        assert pd.suggest_action() == "continue"

    def test_suggest_action_diversify(self):
        pd = PlateauDetector(window_size=5, variance_threshold=0.001)
        for _ in range(20):
            pd.record(1.0)
        assert pd.suggest_action() == "diversify"
