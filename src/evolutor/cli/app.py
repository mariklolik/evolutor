from __future__ import annotations

import typer

app = typer.Typer(name="evolutor", help="Self-driving, self-improving codebase framework")


@app.command()
def init(path: str = typer.Argument(".", help="Path to project root")) -> None:
    """Initialize Evolutor in a project directory."""
    import os
    config_path = os.path.join(path, ".evolutor.toml")
    with open(config_path, "w") as f:
        f.write('[project]\nroot = "."\n')
    typer.echo(f"Initialized Evolutor in {path}")


@app.command()
def task(description: str = typer.Argument(..., help="Task description")) -> None:
    """Submit a task to the orchestrator."""
    typer.echo(f"Submitting task: {description}")
    typer.echo("Orchestrator not yet connected in this build.")


@app.command()
def evolve(
    generations: int = typer.Option(10, "--generations", "-g", help="Number of generations"),
    target: str = typer.Option("src/", "--target", "-t", help="Target directory"),
) -> None:
    """Run the evolution loop."""
    typer.echo(f"Starting evolution: {generations} generations on {target}")
    typer.echo("Evolution engine not yet connected in this build.")


@app.command()
def status() -> None:
    """Show active tasks, evolution stats, and memory usage."""
    typer.echo("Evolutor Status")
    typer.echo("  Active tasks: 0")
    typer.echo("  Archive coverage: 0%")
    typer.echo("  Memory entries: 0")


@app.command()
def rollback(ref: str = typer.Argument(..., help="Git ref or savepoint label")) -> None:
    """Rollback to a savepoint."""
    typer.echo(f"Rolling back to: {ref}")


@app.command()
def history(n: int = typer.Option(10, "--count", "-n", help="Number of entries")) -> None:
    """Show audit history."""
    typer.echo(f"Last {n} audit entries:")
    typer.echo("  (no history yet)")


@app.command()
def chat() -> None:
    """Start interactive chat interface."""
    typer.echo("Chat interface not yet available.")


@app.command()
def tui() -> None:
    """Launch full-screen TUI dashboard."""
    typer.echo("TUI not yet available.")


def main() -> None:
    app()
