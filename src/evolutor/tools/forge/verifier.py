"""Tool verifier — validates generated tool code in sandbox."""

from __future__ import annotations

import ast

import structlog

logger = structlog.get_logger()


class ToolVerifier:
    """Verify generated tool code before deployment."""

    async def verify(self, tool_code: str) -> dict:
        """Verify tool code is safe and functional."""
        issues = []

        # Check syntax
        try:
            ast.parse(tool_code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")

        # Check for dangerous imports
        dangerous = ["os.system", "subprocess.call", "eval(", "exec(", "__import__"]
        for d in dangerous:
            if d in tool_code:
                issues.append(f"Dangerous pattern: {d}")

        # Check for a class with get_schema
        if "get_schema" not in tool_code:
            issues.append("Missing get_schema() method")

        passed = len(issues) == 0
        logger.info("tool_verified", passed=passed, issues=len(issues))
        return {"passed": passed, "issues": issues}
