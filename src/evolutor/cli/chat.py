"""Interactive chat interface using Rich."""

from __future__ import annotations

import asyncio

import structlog
from rich.console import Console
from rich.markdown import Markdown

logger = structlog.get_logger()


class ChatInterface:
    """Async REPL chat interface."""

    def __init__(self) -> None:
        self.console = Console()
        self._running = False

    async def run(self) -> None:
        self._running = True
        self.console.print("[bold]Evolutor Chat[/bold] (type 'exit' to quit)\n")

        while self._running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("you> "),
                )
            except (EOFError, KeyboardInterrupt):
                break

            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                break

            response = await self._dispatch(user_input)
            self.console.print(Markdown(response))
            self.console.print()

        self.console.print("[dim]Goodbye![/dim]")

    async def _dispatch(self, message: str) -> str:
        """Dispatch user message. In production, this calls the orchestrator."""
        if message.startswith("/"):
            return self._handle_command(message)
        # Placeholder response
        return f"**Received:** {message}\n\nOrchestrator not yet connected."

    def _handle_command(self, command: str) -> str:
        parts = command.split()
        cmd = parts[0].lower()
        if cmd == "/status":
            return "**Status:** No active tasks."
        if cmd == "/help":
            return "**Commands:** /status, /help, /exit"
        return f"Unknown command: {cmd}"
