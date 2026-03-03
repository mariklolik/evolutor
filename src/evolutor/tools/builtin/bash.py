"""Bash execution tool."""

from __future__ import annotations

import asyncio
import subprocess

import structlog

logger = structlog.get_logger()


class BashTool:
    """Execute bash commands, optionally in a sandbox."""

    def __init__(self, sandbox_manager=None) -> None:
        self.sandbox = sandbox_manager

    async def execute(self, command: str, timeout: int = 60) -> dict:
        if self.sandbox:
            instances = await self.sandbox.list_active()
            if instances:
                result = await self.sandbox.execute(instances[0].id, command, timeout)
                return {
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
        # Direct execution fallback
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=timeout,
                ),
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Command timed out"}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}

    @staticmethod
    def get_schema() -> dict:
        return {
            "name": "bash",
            "description": "Execute shell commands",
            "functions": {
                "execute": {
                    "params": {"command": "str", "timeout": "int"},
                    "returns": "dict with exit_code, stdout, stderr",
                },
            },
        }
