# TypeScript Playbook

## Code Style
- Use strict TypeScript with `strict: true`
- Prefer `interface` over `type` for object shapes
- Use `const` by default, `let` when needed
- Use template literals for string interpolation

## Testing
- Use Jest or Vitest
- Use `describe`/`it` blocks
- Mock external modules with `jest.mock`

## Error Handling
- Use typed errors extending `Error`
- Use `Result<T, E>` pattern for expected failures
- Always handle Promise rejections

## Async
- Use `async/await` over raw Promises
- Use `Promise.all` for parallel operations
