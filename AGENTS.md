# AGENTS.md — Instructions for AI Agents

This file provides guidance for AI agents (including Evolutor itself) working in this codebase.

## Repository Layout

```
src/evolutor/           # Main package (src layout)
  cli/                  # Typer CLI + Textual TUI
  kernel/               # Safety invariants + evaluation
  orchestrator/         # LangGraph planner/worker/critic
  memory/               # Knowledge graph + playbooks + persistent memory
  evolution/            # MAP-Elites archive + fitness + mutation
  verification/         # Static analysis + property tests + consensus
  git/                  # pygit2 wrappers + worktrees + audit
  sandbox/              # Docker container management
  tools/                # Built-in, MCP, and ToolForge tools
  types/                # Shared Pydantic v2 models
tests/
  unit/                 # Fast unit tests (mock external deps)
  integration/          # End-to-end tests
  benchmarks/           # pytest-benchmark suites
configs/                # TOML configuration files
playbooks/              # Coding convention guides
prompts/                # Jinja2 LLM prompt templates
```

## Coding Rules

- Python 3.11+ only
- All cross-module data uses Pydantic v2 models from `src/evolutor/types/`
- All I/O-bound code is `async def`
- Use `structlog` for all logging
- No docstrings/comments beyond what's needed for correctness
- Run `ruff check src/` and `mypy src/evolutor/types/` before committing

## Protected Files

The kernel (`src/evolutor/kernel/`) must never be modified by evolutionary agents.
The `pyproject.toml` is also protected.

## Before Committing

```bash
ruff check src/
mypy src/evolutor/types/
pytest tests/ -x
```
