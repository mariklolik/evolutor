"""Git operations tool."""

from __future__ import annotations

import structlog

from evolutor.git.ops import GitOps

logger = structlog.get_logger()


class GitTool:
    """Tool wrapper for git operations."""

    def __init__(self, repo_path: str = ".") -> None:
        self.ops = GitOps(repo_path)

    def status(self) -> dict:
        repo = self.ops.repo
        status_dict = {}
        for path, flags in repo.status().items():
            status_dict[path] = flags
        return {
            "branch": self.ops.current_branch(),
            "files": status_dict,
        }

    def diff(self, ref_a: str | None = None, ref_b: str | None = None) -> str:
        return self.ops.get_diff(ref_a, ref_b)

    def commit(self, message: str) -> str:
        self.ops.stage_files()
        return self.ops.commit(message)

    def create_branch(self, name: str) -> str:
        branch = self.ops.create_branch(name)
        return branch.branch_name

    def log(self, max_count: int = 10) -> list[dict]:
        return self.ops.get_log(max_count)

    @staticmethod
    def get_schema() -> dict:
        return {
            "name": "git",
            "description": "Git operations",
            "functions": {
                "status": {"params": {}, "returns": "dict"},
                "diff": {"params": {"ref_a": "str|None", "ref_b": "str|None"}, "returns": "str"},
                "commit": {"params": {"message": "str"}, "returns": "str (sha)"},
                "create_branch": {"params": {"name": "str"}, "returns": "str"},
                "log": {"params": {"max_count": "int"}, "returns": "list[dict]"},
            },
        }
