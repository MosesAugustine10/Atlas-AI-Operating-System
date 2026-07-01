"""Configuration loading for Atlas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "atlas.yaml"


class Config:
    """Loads and exposes Atlas configuration from a YAML file.

    The configuration is read once at construction. Missing files are
    tolerated and yield an empty configuration, so the engine can boot
    even before a config file is present.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else _DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> Config:
        """Load (or reload) configuration from disk."""
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            if not isinstance(loaded, dict):
                raise TypeError(
                    f"Config root must be a mapping, got {type(loaded).__name__}"
                )
            self._data = loaded
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """Return a top-level configuration value."""
        return self._data.get(key, default)

    @property
    def data(self) -> dict[str, Any]:
        """Return the full configuration dictionary."""
        return self._data
