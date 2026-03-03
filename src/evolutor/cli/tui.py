"""Full-screen TUI dashboard using Textual."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def launch_tui() -> None:
    """Launch the TUI dashboard."""
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer, Static, Log

        class TaskPanel(Static):
            def compose(self) -> ComposeResult:
                yield Static("Active Tasks: 0\nCompleted: 0\nFailed: 0", id="tasks")

        class EvolutionPanel(Static):
            def compose(self) -> ComposeResult:
                yield Static("Generation: 0\nCoverage: 0%\nBest Fitness: 0.0", id="evolution")

        class LogPanel(Log):
            pass

        class MemoryPanel(Static):
            def compose(self) -> ComposeResult:
                yield Static("Knowledge Graph: 0 nodes\nPlaybooks: 0\nScratchpad: 0", id="memory")

        class EvolutorTUI(App):
            CSS = """
            Screen {
                layout: grid;
                grid-size: 2;
                grid-gutter: 1;
            }
            """

            def compose(self) -> ComposeResult:
                yield Header()
                yield TaskPanel(id="task-panel")
                yield EvolutionPanel(id="evo-panel")
                yield LogPanel(id="log-panel")
                yield MemoryPanel(id="mem-panel")
                yield Footer()

        app = EvolutorTUI()
        app.run()
    except ImportError:
        logger.warning("textual_not_available")
        print("TUI requires 'textual' package. Install with: pip install textual")
