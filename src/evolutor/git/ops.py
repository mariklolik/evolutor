"""Core git operations using pygit2."""

from __future__ import annotations

from pathlib import Path

import pygit2
import structlog

logger = structlog.get_logger()


class GitOps:
    """Low-level git operations using pygit2."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)
        self.repo = pygit2.Repository(str(self.repo_path))

    def current_branch(self) -> str:
        if self.repo.head_is_unborn:
            return "HEAD"
        return self.repo.head.shorthand

    def create_branch(self, name: str, ref: str | None = None) -> pygit2.Branch:
        if ref:
            target = self.repo.revparse_single(ref)
            commit = target.peel(pygit2.Commit)
        else:
            commit = self.repo.head.peel(pygit2.Commit)
        return self.repo.branches.create(name, commit)

    def checkout(self, branch_name: str) -> None:
        branch = self.repo.branches.get(branch_name)
        if branch is None:
            raise ValueError(f"Branch {branch_name} not found")
        self.repo.checkout(branch)

    def stage_files(self, paths: list[str] | None = None) -> None:
        index = self.repo.index
        if paths:
            for p in paths:
                index.add(p)
        else:
            index.add_all()
        index.write()

    def commit(self, message: str, author_name: str = "Evolutor", author_email: str = "evolutor@localhost") -> str:
        index = self.repo.index
        tree_oid = index.write_tree()
        sig = pygit2.Signature(author_name, author_email)
        parents = [] if self.repo.head_is_unborn else [self.repo.head.target]
        oid = self.repo.create_commit("HEAD", sig, sig, message, tree_oid, parents)
        return str(oid)

    def get_diff(self, ref_a: str | None = None, ref_b: str | None = None) -> str:
        if ref_a is None and ref_b is None:
            diff = self.repo.diff()
            return diff.patch or ""
        commit_a = self.repo.revparse_single(ref_a).peel(pygit2.Commit) if ref_a else None
        commit_b = self.repo.revparse_single(ref_b).peel(pygit2.Commit) if ref_b else None
        if commit_a and commit_b:
            diff = self.repo.diff(commit_a, commit_b)
        elif commit_a:
            diff = commit_a.tree.diff_to_workdir()
        else:
            diff = self.repo.diff()
        return diff.patch or ""

    def get_log(self, max_count: int = 20, ref: str | None = None) -> list[dict]:
        if self.repo.head_is_unborn:
            return []
        start = self.repo.revparse_single(ref).id if ref else self.repo.head.target
        entries = []
        for commit in self.repo.walk(start, pygit2.GIT_SORT_TIME):
            entries.append({
                "sha": str(commit.id),
                "message": commit.message.strip(),
                "author": commit.author.name,
                "time": commit.commit_time,
            })
            if len(entries) >= max_count:
                break
        return entries

    def get_file_at_ref(self, file_path: str, ref: str) -> str:
        commit = self.repo.revparse_single(ref).peel(pygit2.Commit)
        blob = commit.tree / file_path
        return blob.data.decode("utf-8")

    def merge(self, branch_name: str) -> pygit2.MergeResult | None:
        branch = self.repo.branches.get(branch_name)
        if branch is None:
            raise ValueError(f"Branch {branch_name} not found")
        result = self.repo.merge(branch.target)
        return result

    def cherry_pick(self, commit_sha: str) -> None:
        commit = self.repo.get(pygit2.Oid(hex=commit_sha))
        if commit is None:
            raise ValueError(f"Commit {commit_sha} not found")
        self.repo.cherrypick(commit.id)
