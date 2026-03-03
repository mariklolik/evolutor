"""Safety boundaries for file access and command execution."""

from __future__ import annotations

import re
from enum import Enum

import structlog

logger = structlog.get_logger()

PROTECTED_PATHS = [
    "src/evolutor/kernel/",
    "pyproject.toml",
    ".git/",
]


class RiskLevel(str, Enum):
    safe = "safe"
    moderate = "moderate"
    high = "high"
    critical = "critical"


DANGEROUS_COMMANDS = {
    "rm -rf": RiskLevel.critical,
    "git push --force": RiskLevel.critical,
    "git reset --hard": RiskLevel.high,
    "DROP TABLE": RiskLevel.critical,
    "sudo": RiskLevel.high,
    "chmod 777": RiskLevel.high,
    "curl | sh": RiskLevel.critical,
    "wget | sh": RiskLevel.critical,
}


class SafetyBoundary:
    """Enforce safety boundaries on file access and commands."""

    def __init__(self, protected_paths: list[str] | None = None) -> None:
        self.protected_paths = protected_paths or PROTECTED_PATHS

    def check_file_access(self, file_path: str, write: bool = False) -> RiskLevel:
        for protected in self.protected_paths:
            if file_path.startswith(protected):
                if write:
                    logger.warning("protected_file_write", path=file_path)
                    return RiskLevel.critical
                return RiskLevel.moderate
        return RiskLevel.safe

    def check_command(self, command: str) -> RiskLevel:
        worst = RiskLevel.safe
        for pattern, level in DANGEROUS_COMMANDS.items():
            if pattern.lower() in command.lower():
                if _risk_order(level) > _risk_order(worst):
                    worst = level
        return worst

    def validate_diff(self, changed_files: list[str]) -> RiskLevel:
        worst = RiskLevel.safe
        for f in changed_files:
            level = self.check_file_access(f, write=True)
            if _risk_order(level) > _risk_order(worst):
                worst = level
        return worst

    def get_risk_level(self, file_path: str | None = None, command: str | None = None) -> RiskLevel:
        levels = []
        if file_path:
            levels.append(self.check_file_access(file_path, write=True))
        if command:
            levels.append(self.check_command(command))
        if not levels:
            return RiskLevel.safe
        return max(levels, key=_risk_order)


def _risk_order(level: RiskLevel) -> int:
    return {"safe": 0, "moderate": 1, "high": 2, "critical": 3}[level.value]
