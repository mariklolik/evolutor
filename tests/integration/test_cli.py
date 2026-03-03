"""CLI integration tests using Typer CliRunner."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from evolutor.cli.app import app

runner = CliRunner()


class TestCLI:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "evolutor" in result.output.lower() or "Self-driving" in result.output

    def test_init(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "Initialized" in result.output

    def test_status(self):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Status" in result.output

    def test_history(self):
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "audit" in result.output.lower() or "history" in result.output.lower()

    def test_task(self):
        result = runner.invoke(app, ["task", "Add a feature"])
        assert result.exit_code == 0

    def test_evolve(self):
        result = runner.invoke(app, ["evolve", "--generations", "1"])
        assert result.exit_code == 0
