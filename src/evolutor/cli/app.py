from __future__ import annotations

import os

import typer

app = typer.Typer(name="evolutor", help="Self-driving, self-improving codebase framework")


@app.command()
def init(path: str = typer.Argument(".", help="Path to project root")) -> None:
    """Initialize Evolutor in a project directory."""
    config_path = os.path.join(path, ".evolutor.toml")
    with open(config_path, "w") as f:
        f.write('[project]\nroot = "."\n')
    typer.echo(f"Initialized Evolutor in {path}")


@app.command()
def task(
    description: str = typer.Argument(..., help="Task description"),
    project: str = typer.Option(
        "", "--project", "-p", help="Project root (default: EVOLUTOR_PROJECT_ROOT or cwd)"
    ),
    max_iterations: int = typer.Option(10, "--max-iter", "-m", help="Max critic iterations"),
) -> None:
    """Submit a task to the orchestrator."""
    import asyncio

    from evolutor.orchestrator.engine import OrchestratorEngine
    from evolutor.types.task import Task

    root = project or os.environ.get("EVOLUTOR_PROJECT_ROOT", "") or os.getcwd()
    os.environ["EVOLUTOR_PROJECT_ROOT"] = root

    typer.echo(f"Submitting task: {description}")
    typer.echo(f"Project root: {root}")

    engine = OrchestratorEngine()
    t = Task(title=description, description=description)

    try:
        result = asyncio.run(engine.run(t, max_iterations=max_iterations))
        if result.success:
            typer.echo("[OK] Task completed successfully")
            if result.files_changed:
                typer.echo(f"Files changed: {', '.join(result.files_changed)}")
        else:
            typer.echo(f"[FAIL] Task failed: {result.error}", err=True)
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def evolve(
    generations: int = typer.Option(10, "--generations", "-g", help="Number of generations"),
    target: str = typer.Option("src/", "--target", "-t", help="Target directory"),
    project: str = typer.Option(
        "", "--project", "-p", help="Project root (default: EVOLUTOR_PROJECT_ROOT or cwd)"
    ),
) -> None:
    """Run the evolution loop."""
    import asyncio

    from evolutor.evolution.loop import EvolutionLoop

    root = project or os.environ.get("EVOLUTOR_PROJECT_ROOT", "") or os.getcwd()
    os.environ["EVOLUTOR_PROJECT_ROOT"] = root

    typer.echo(f"Starting evolution: {generations} generations on {target}")
    typer.echo(f"Project root: {root}")

    loop = EvolutionLoop()
    try:
        report = asyncio.run(loop.run(generations=generations))
        typer.echo(f"[OK] Evolution complete: {report.generations_completed} generations")
        typer.echo(f"  Best fitness:      {report.best_fitness:.3f}")
        typer.echo(f"  Archive coverage:  {report.archive_coverage:.1%}")
        typer.echo(f"  Mutations:         {report.total_mutations}")
        typer.echo(f"  Plateaus detected: {report.plateaus_detected}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def status(
    project: str = typer.Option(
        "", "--project", "-p", help="Project root (default: cwd)"
    ),
) -> None:
    """Show active tasks, evolution stats, and memory usage."""
    root = project or os.environ.get("EVOLUTOR_PROJECT_ROOT", "") or os.getcwd()
    typer.echo("Evolutor Status")
    typer.echo(f"  Project root: {root}")
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
    import asyncio

    from evolutor.cli.chat import ChatInterface

    ci = ChatInterface()
    asyncio.run(ci.run())


@app.command()
def tui() -> None:
    """Launch full-screen TUI dashboard."""
    from evolutor.cli.tui import launch_tui

    launch_tui()


def main() -> None:
    app()
