# General Playbook

## Principles
- Keep functions small and focused (< 30 lines)
- Write self-documenting code; add comments only for "why"
- Follow the principle of least surprise
- Prefer composition over inheritance

## Git Workflow
- Use conventional commits: feat:, fix:, refactor:, test:, docs:
- Keep commits atomic — one logical change per commit
- Write descriptive branch names

## Testing Strategy
- Unit tests for logic, integration tests for workflows
- Mock external dependencies
- Aim for >80% coverage on critical paths

## Security
- Never hardcode secrets
- Validate all external inputs
- Use parameterized queries for databases
- Apply principle of least privilege

## Code Review
- Check for correctness first, style second
- Look for edge cases and error handling
- Verify test coverage for new code
