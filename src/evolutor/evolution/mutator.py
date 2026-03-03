"""Mutation generation for code evolution."""

from __future__ import annotations

import random
from enum import Enum

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class MutationType(str, Enum):
    refactor = "refactor"
    optimize = "optimize"
    harden = "harden"
    simplify = "simplify"
    extend = "extend"
    test_improve = "test_improve"


class Mutation(BaseModel):
    mutation_type: MutationType
    description: str
    target_files: list[str] = Field(default_factory=list)
    prompt: str = ""


class Mutator:
    """Generate mutations for code evolution."""

    def generate_mutation(self, target_files: list[str], context: str = "") -> Mutation:
        mutation_type = self.select_mutation_type(context)
        prompts = {
            MutationType.refactor: "Refactor this code for better readability and maintainability.",
            MutationType.optimize: "Optimize this code for better performance.",
            MutationType.harden: "Add error handling and input validation.",
            MutationType.simplify: "Simplify this code by removing unnecessary complexity.",
            MutationType.extend: "Extend this code with useful new functionality.",
            MutationType.test_improve: "Add or improve tests for better coverage.",
        }
        return Mutation(
            mutation_type=mutation_type,
            description=f"{mutation_type.value} on {len(target_files)} file(s)",
            target_files=target_files,
            prompt=prompts[mutation_type],
        )

    def crossover(self, mutation_a: Mutation, mutation_b: Mutation) -> Mutation:
        target_files = list(set(mutation_a.target_files + mutation_b.target_files))
        return Mutation(
            mutation_type=random.choice([mutation_a.mutation_type, mutation_b.mutation_type]),
            description=f"crossover: {mutation_a.mutation_type.value} + {mutation_b.mutation_type.value}",
            target_files=target_files,
            prompt=f"{mutation_a.prompt}\n\nAdditionally: {mutation_b.prompt}",
        )

    def select_mutation_type(self, context: str = "") -> MutationType:
        """Heuristic mutation type selection based on context."""
        context_lower = context.lower()
        if "slow" in context_lower or "performance" in context_lower:
            return MutationType.optimize
        if "error" in context_lower or "crash" in context_lower:
            return MutationType.harden
        if "complex" in context_lower or "long" in context_lower:
            return MutationType.simplify
        if "coverage" in context_lower or "test" in context_lower:
            return MutationType.test_improve
        if "feature" in context_lower or "add" in context_lower:
            return MutationType.extend
        return random.choice(list(MutationType))
