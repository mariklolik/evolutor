"""Evolution knowledge extraction and playbook updates."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class EvolutionKnowledge:
    """Extract patterns from evolution results and update playbooks."""

    def extract_successful_patterns(self, results: list[dict]) -> list[str]:
        patterns = []
        for r in results:
            if r.get("success", False):
                mutation_type = r.get("mutation_type", "unknown")
                patterns.append(f"Successful {mutation_type}")
        return patterns

    def extract_failure_patterns(self, results: list[dict]) -> list[str]:
        patterns = []
        for r in results:
            if not r.get("success", False):
                error = r.get("error", "unknown")
                patterns.append(f"Failed: {error}")
        return patterns

    def update_playbooks(self, successful_patterns: list[str], failure_patterns: list[str]) -> dict:
        return {
            "successful_count": len(successful_patterns),
            "failure_count": len(failure_patterns),
            "recommendations": [
                f"Prefer {p}" for p in successful_patterns[:3]
            ],
        }

    def generate_meta_insights(self, evolution_history: list[dict]) -> str:
        total = len(evolution_history)
        successes = sum(1 for r in evolution_history if r.get("success", False))
        rate = successes / total if total > 0 else 0
        return f"Evolution insight: {successes}/{total} successful ({rate:.1%})"
