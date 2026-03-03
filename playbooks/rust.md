# Rust Playbook

## Code Style
- Use `clippy` lints
- Prefer `Result<T, E>` over panics
- Use `thiserror` for error types
- Derive `Debug`, `Clone` where appropriate

## Testing
- Use `#[cfg(test)]` module
- Use `assert_eq!` and `assert!` macros
- Use `proptest` for property-based testing

## Error Handling
- Use `?` operator for propagation
- Define custom error enums with `thiserror`
- Use `anyhow` in applications, `thiserror` in libraries

## Performance
- Avoid unnecessary allocations
- Prefer `&str` over `String` in function signatures
- Use iterators over indexing
