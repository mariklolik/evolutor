"""Critic node — LLM-based accept/revise/reject reviewer."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import structlog

from evolutor.orchestrator.models import OrchestratorState
from evolutor.types.task import TaskResult

logger = structlog.get_logger()

_SYSTEM = (
    "You are a senior code reviewer. Given a task description and the git diff/status, "
    "decide if the implementation is acceptable.\n\n"
    "Respond with ONLY a JSON object: "
    '{"decision": "accept"|"revise"|"reject", "reason": "brief explanation"}\n\n'
    '- "accept": task correctly implemented\n'
    '- "revise": fixable issues (wrong logic, missing files, incomplete implementation)\n'
    '- "reject": fundamentally wrong, harmful, or impossible to fix by revision\n\n'
    "Be pragmatic: accept if the core work is done even if minor polish is missing."
)


def _client():
    import anthropic

    return anthropic.Anthropic(
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )


def _model() -> str:
    return os.environ.get("EVOLUTOR_MODEL", "anthropic/claude-sonnet-4.6")


def _get_git_status(root: Path) -> str:
    try:
        # Try diff first (staged + unstaged)
        result = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, cwd=root, timeout=10,
        )
        diff = result.stdout.strip()
        if not diff:
            # Fall back to status
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, cwd=root, timeout=10,
            )
            diff = result.stdout.strip()
        return diff[:4000] if diff else "No uncommitted changes detected"
    except Exception as e:
        return f"Could not get git status: {e}"


def _review(
    task_title: str,
    task_description: str,
    worker_summary: str,
    last_result: TaskResult,
) -> tuple[str, str]:
    """Returns (decision, reason). decision is one of: accept, revise, reject."""
    if not last_result.success:
        return "revise", f"Worker reported failure: {last_result.error}"

    root = Path(os.environ.get("EVOLUTOR_PROJECT_ROOT", ".")).resolve()
    diff = _get_git_status(root)
    client = _client()

    prompt = (
        f"Task: {task_title}\n\n"
        f"Description: {task_description}\n\n"
        f"Worker summary: {worker_summary or '(none)'}\n\n"
        f"Files changed: {', '.join(last_result.files_changed) or 'none'}\n\n"
        f"Git status:\n{diff}\n\n"
        "Was this task successfully implemented?"
    )

    resp = client.messages.create(
        model=_model(),
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.content[0].text.strip()
    try:
        parsed = json.loads(text)
        return parsed.get("decision", "accept"), parsed.get("reason", "")
    except json.JSONDecodeError:
        # Best-effort text extraction
        lower = text.lower()
        if "reject" in lower:
            return "reject", text
        if "revise" in lower:
            return "revise", text
        return "accept", text


class CriticNode:
    """Reviews worker output using LLM and makes accept/revise/reject decisions."""

    async def __call__(self, state: OrchestratorState) -> OrchestratorState:
        results = state.get("results", [])
        if not results:
            state["should_continue"] = False
            return state

        last_result = results[-1]
        plan = state.get("plan", [])
        idx = state.get("current_subtask_index", 1)  # already incremented by worker

        # Identify the subtask that was just executed
        subtask_idx = idx - 1
        if subtask_idx >= 0 and subtask_idx < len(plan):
            subtask = plan[subtask_idx]
            task_title = subtask.title
            task_description = subtask.description
        else:
            root_task = state.get("task")
            task_title = root_task.title if root_task else "Unknown"
            task_description = root_task.description if root_task else ""

        worker_summary = (last_result.metrics or {}).get("summary", "")

        try:
            decision, reason = await asyncio.to_thread(
                _review, task_title, task_description, worker_summary, last_result
            )
            logger.info("critic_decision", decision=decision, reason=reason[:120])

            if decision == "accept":
                if idx >= len(plan):
                    state["should_continue"] = False
                    state["final_result"] = last_result
                else:
                    state["should_continue"] = True

            elif decision == "revise":
                state["current_subtask_index"] = max(0, idx - 1)
                iteration = state.get("iteration", 0) + 1
                state["iteration"] = iteration
                state["should_continue"] = iteration < state.get("max_iterations", 10)

            else:  # reject
                state["should_continue"] = False
                state["final_result"] = TaskResult(
                    task_id=last_result.task_id,
                    success=False,
                    error=f"Rejected by critic: {reason}",
                )

        except Exception as e:
            logger.error("critic_error", error=str(e), exc_info=True)
            # On critic error, accept to avoid stalling
            if idx >= len(plan):
                state["should_continue"] = False
                state["final_result"] = last_result
            else:
                state["should_continue"] = True

        return state
