"""Configuration management — load from TOML, env, CLI."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

from evolutor.types.config import EvolutorConfig

logger = structlog.get_logger()


class ConfigManager:
    """Load and merge configuration from multiple sources."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path or self.get_default_config_path()
        self._config: EvolutorConfig | None = None

    @staticmethod
    def get_default_config_path() -> str:
        candidates = [
            ".evolutor.toml",
            "configs/default.toml",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        return "configs/default.toml"

    def load(self) -> EvolutorConfig:
        config_dict = {}
        # Load from TOML file
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                if hasattr(__builtins__, "__import__"):
                    import tomllib
            except ImportError:
                import tomli as tomllib
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    tomllib = None
            if tomllib:
                try:
                    with open(config_file, "rb") as f:
                        config_dict = tomllib.load(f)
                except Exception as e:
                    logger.warning("config_load_failed", path=str(config_file), error=str(e))

        # Merge env overrides
        if os.environ.get("ANTHROPIC_API_KEY"):
            config_dict["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
        if os.environ.get("EVOLUTOR_LOG_LEVEL"):
            config_dict["log_level"] = os.environ["EVOLUTOR_LOG_LEVEL"]
        if os.environ.get("REDIS_URL"):
            config_dict.setdefault("orchestrator", {})["redis_url"] = os.environ["REDIS_URL"]

        self._config = EvolutorConfig(**config_dict)
        return self._config

    def save(self, config: EvolutorConfig, path: str | None = None) -> None:
        save_path = Path(path or self.config_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        # Convert to TOML-like format
        data = config.model_dump()
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"\n[{key}]")
                for k, v in value.items():
                    lines.append(f"{k} = {_toml_value(v)}")
            else:
                lines.append(f"{key} = {_toml_value(value)}")
        save_path.write_text("\n".join(lines) + "\n")

    def merge_cli_overrides(self, **overrides) -> EvolutorConfig:
        config = self._config or self.load()
        data = config.model_dump()
        for key, value in overrides.items():
            if value is not None:
                if "." in key:
                    parts = key.split(".", 1)
                    if parts[0] in data and isinstance(data[parts[0]], dict):
                        data[parts[0]][parts[1]] = value
                else:
                    data[key] = value
        self._config = EvolutorConfig(**data)
        return self._config


def _toml_value(v) -> str:
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return str(v)
    return str(v)
