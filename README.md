# Evolutor

A self-driving, self-improving codebase framework combining multi-agent LLM orchestration with MAP-Elites evolutionary optimization.

## Installation

```bash
pip install -e ".[dev]"
```

## Quickstart

```bash
evolutor init /path/to/project
evolutor task "Add type hints to all functions"
evolutor evolve --generations 10
evolutor status
```

## Architecture

Evolutor runs a planner/worker/critic hierarchy (via LangGraph) on isolated git worktrees inside Docker sandboxes. An immutable kernel enforces safety invariants before any change is merged. A MAP-Elites archive retains the best diverse solutions across the behavior space.

## Development

```bash
pip install -e ".[dev]"
pytest tests/
ruff check src/
mypy src/evolutor/
```
