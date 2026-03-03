# Python Playbook

## Code Style
- Use type hints for all function signatures
- Prefer `pathlib.Path` over `os.path`
- Use `f-strings` for string formatting
- Follow PEP 8 with 100 char line length

## Testing
- Use pytest with fixtures
- Use `tmp_path` fixture for file operations
- Mock external services (Docker, APIs)
- Use `hypothesis` for property-based tests on pure functions

## Error Handling
- Use specific exception types
- Log errors with structlog
- Use context managers for resource cleanup

## Async
- Use `async/await` for I/O operations
- Use `asyncio.gather` for parallel tasks
- Use `asyncio.get_event_loop().run_in_executor` for blocking calls

## Dependencies
- Pydantic v2 for data models
- structlog for logging
- httpx for HTTP requests
