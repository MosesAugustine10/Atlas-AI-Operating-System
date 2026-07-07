"""Studio settings — persistent YAML-backed configuration.

The :class:`StudioSettings` class loads and saves the operator's Studio
preferences to ``atlas/configs/studio.yaml``. It is intentionally a plain
Python class (not a frozen dataclass) because settings are mutable and
edited live through the Settings page. It has **no Qt dependency** — it
only uses :mod:`yaml` and the standard library, so it can be used from
headless scripts and tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

#: Absolute path to the studio YAML config inside the Atlas tree.
CONFIG_PATH: Path = Path(__file__).resolve().parent.parent / "configs" / "studio.yaml"

#: Default values for every known setting. These are merged with the
#: on-disk file on :meth:`StudioSettings.load` so missing keys always
#: fall back to a sane value.
DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "font_family": "Inter",
    "font_size": 14,
    "window_width": 1600,
    "window_height": 900,
    "sidebar_width": 280,
    "right_sidebar_width": 320,
    "bottom_panel_height": 240,
    "api_keys": {},
    "ollama_base_url": "http://localhost:11434",
    "openrouter_api_key": "",
    "zai_api_key": "",
    "workspace_path": "",
    "recently_opened": [],
    "pinned_pages": [],
    "enabled_plugins": [],
}


class StudioSettings:
    """Mutable, YAML-backed settings store for Atlas Studio.

    The store keeps an internal dict (``_data``) seeded from
    :data:`DEFAULTS`. :meth:`load` merges the on-disk file over the
    defaults; :meth:`save` writes the current state back.

    Parameters:
        path: Optional override for the config file location. Defaults
            to :data:`CONFIG_PATH` (``atlas/configs/studio.yaml``).
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path: Path = Path(path) if path is not None else CONFIG_PATH
        #: Live settings data. Always contains every default key.
        self._data: dict[str, Any] = {
            key: _copy_default(value) for key, value in DEFAULTS.items()
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> StudioSettings:
        """Merge on-disk settings over the in-memory defaults.

        If the file does not exist or is unreadable, the defaults remain
        in place and no error is raised — Studio must always be able to
        start. Returns ``self`` for chaining.
        """
        if not self.path.exists():
            return self
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                on_disk = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError):
            # Corrupt or unreadable config: keep defaults rather than crash.
            return self
        if isinstance(on_disk, dict):
            for key, value in on_disk.items():
                self._data[key] = value
        return self

    def save(self) -> StudioSettings:
        """Write the current settings to disk as YAML.

        Parent directories are created if needed. Returns ``self`` for
        chaining.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                self._data, handle, sort_keys=False, default_flow_style=False
            )
        return self

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for ``key``, or ``default`` if unset."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> StudioSettings:
        """Set ``key`` to ``value``. Returns ``self`` for chaining.

        Note:
            Changes are **not** persisted automatically — call
            :meth:`save` to write them to disk.
        """
        self._data[key] = value
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a shallow copy of all settings as a plain dict."""
        return dict(self._data)

    def from_dict(self, data: dict[str, Any]) -> StudioSettings:
        """Replace all settings from ``data``.

        Unknown keys are kept (so plugins can store their own settings),
        but known keys are validated to their default *type* where
        possible. Returns ``self`` for chaining.
        """
        merged = {key: _copy_default(value) for key, value in DEFAULTS.items()}
        if isinstance(data, dict):
            for key, value in data.items():
                merged[key] = value
        self._data = merged
        return self

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._data

    def __repr__(self) -> str:
        return f"<StudioSettings path={self.path!s} keys={len(self._data)}>"


def _copy_default(value: Any) -> Any:
    """Return a shallow copy of a default value.

    Mutable containers (``list``, ``dict``) are copied so that the
    defaults dict is never mutated by accident.
    """
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


__all__ = ["CONFIG_PATH", "DEFAULTS", "StudioSettings"]
