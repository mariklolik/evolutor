from pydantic import BaseModel, Field


class CodeMetrics(BaseModel):
    test_count: int = 0
    test_pass_rate: float = 0.0
    coverage_percent: float = 0.0
    cyclomatic_complexity: float = 0.0
    maintainability_index: float = 0.0
    security_issues: int = 0
    type_errors: int = 0
    lint_errors: int = 0
    lines_of_code: int = 0
    benchmark_score: float = 0.0


class FitnessVector(BaseModel):
    test_pass_rate: float = 0.0
    coverage: float = 0.0
    complexity: float = 0.0
    security_score: float = 0.0

    def to_minimize(self) -> list[float]:
        return [
            -self.test_pass_rate,
            -self.coverage,
            self.complexity,
            -self.security_score,
        ]


class BehaviorDescriptor(BaseModel):
    complexity: float = Field(ge=0.0, le=1.0, default=0.0)
    novelty: float = Field(ge=0.0, le=1.0, default=0.0)

    def to_array(self) -> list[float]:
        return [self.complexity, self.novelty]
