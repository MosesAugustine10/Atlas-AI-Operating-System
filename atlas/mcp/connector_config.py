"""Connector configuration loader.

Reads per-connector settings from ``atlas/configs/connectors.yaml`` and
resolves secret references (``token_env``, ``api_key_env``,
``env_base_url``, ``env_root``) against environment variables.

This module is a *leaf* in the MCP package dependency graph: it depends
only on the standard library + PyYAML. It does NOT import any other
atlas module, so connectors can import it without creating circular
dependencies.

Usage::

    from atlas.mcp.connector_config import get_connector_config

    cfg = get_connector_config("ollama")
    base_url = cfg.get("base_url", "http://localhost:11434")
    timeout = cfg.get("timeout_seconds", 60)
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "connectors.yaml"


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    """Load the raw YAML config (cached)."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — never crash over config
        return {}


def _resolve_secrets(section: dict[str, Any]) -> dict[str, Any]:
    """Resolve secret references in a config section.

    Recognises these keys:
    * ``token_env`` / ``api_key_env`` / ``env_base_url`` / ``env_root``:
      The value names an environment variable. The resolved value is
      stored under the corresponding key (``token``, ``api_key``,
      ``base_url``, ``root`` respectively).
    """
    resolved = dict(section)
    # Map of (env-key-name) -> (resolved-key-name)
    mappings = [
        ("token_env", "token"),
        ("api_key_env", "api_key"),
        ("env_base_url", "base_url"),
        ("env_root", "root"),
    ]
    for env_key, resolved_key in mappings:
        env_name = section.get(env_key)
        if isinstance(env_name, str) and env_name:
            env_value = os.environ.get(env_name)
            if env_value is not None:
                # Only override if the env var is set; otherwise keep
                # the YAML default (if any).
                resolved[resolved_key] = env_value
    return resolved


def get_connector_config(name: str) -> dict[str, Any]:
    """Return the resolved config section for ``name``.

    Returns an empty dict if the connector has no config section or the
    config file is missing. Secret references (``token_env``, etc.) are
    resolved against environment variables.
    """
    raw = _load_raw()
    section = raw.get(name, {})
    if not isinstance(section, dict):
        return {}
    return _resolve_secrets(section)


def reload_config() -> None:
    """Force a reload of the config file (clears the cache)."""
    _load_raw.cache_clear()


def get_config_path() -> Path:
    """Return the path to the connectors config file."""
    return _CONFIG_PATH


__all__ = [
    "get_config_path",
    "get_connector_config",
    "reload_config",
]
