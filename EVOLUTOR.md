# EVOLUTOR.md — Architecture Overview

## System Architecture

Evolutor is a recursive, self-improving software development framework with five integrated layers:

### 1. Orchestrator Layer (LangGraph)

Three-agent hierarchy operating on git worktrees:
- **Planner**: Decomposes tasks into subtasks using repo map + memory context
- **Worker**: Executes subtasks using tools (file ops, bash, git) in Docker sandbox
- **Critic**: Reviews diffs and votes accept/revise/reject
- **Meta-Improver**: Analyzes evolution results and improves playbooks/prompts

### 2. Kernel Layer (Immutable Safety Core)

The kernel is read-only to all agents. It:
- Registers and checks invariants (tests pass, no security regressions, etc.)
- Gates every change before merge (EvaluationResult)
- Manages rollbacks via git savepoints
- Maintains trust scores for agents

### 3. Evolution Layer (MAP-Elites + NSGA-III)

- **Archive**: GridArchive (20×20 complexity×novelty grid) of elite solutions
- **Fitness**: 4-objective: test_pass_rate, coverage, complexity, security_score
- **Mutator**: 6 LLM-guided mutation types
- **Loop**: ask-tell evolution with plateau detection and island migration

### 4. Memory Layer

- **Knowledge Graph**: AST-parsed code structure (tree-sitter)
- **Repo Map**: PageRank-ranked file importance index
- **Git Memory**: Co-change patterns from git history
- **Playbooks**: ACE-scored coding conventions (helpful/harmful counts)
- **Persistent**: Mem0-backed cross-session memory
- **Scratchpad**: Session-scoped working state

### 5. Sandbox Layer (Docker)

- Each worker runs in a resource-limited container (512MB RAM, 1 CPU, 256 PIDs)
- Network isolated by default
- Snapshot/restore for failed executions

## Data Flow

```
Task → Planner → Subtasks → Worker (in Sandbox) → Critic → Kernel Evaluator
                                                              ↓
                                                    Accept → Git Merge
                                                    Reject → Rollback
                                                    Revise → Worker (retry)
```

## Evolution Loop

```
Archive.sample_elites() → Mutator → Worker (eval in sandbox) → Metrics → FitnessVector
                                                                           ↓
                                                              BehaviorDescriptor → Archive.add()
                                                                           ↓
                                                                 PlateauDetector → diversify?
```
