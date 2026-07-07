"""MCP controller — wraps the MCPManager for the Studio UI.

The :class:`MCPController` adapts the
:class:`~atlas.mcp.manager.MCPManager` (or any duck-typed equivalent)
into a list of :class:`~atlas.studio.models.ConnectorStatus` snapshots
for the MCP page. All access is defensive: a ``None`` manager yields an
empty list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.studio.models.studio_models import ConnectorStatus


class MCPController:
    """ViewModel for the MCP page.

    Parameters:
        manager: Optional :class:`~atlas.mcp.manager.MCPManager`-like
            object. Expected duck-typed surface: ``list_connectors()``,
            ``health()``, ``all_capabilities()``, ``metrics(name)``.
            Any subset works.
    """

    def __init__(self, manager: Any = None) -> None:
        self._manager = manager
        self._statuses: list[ConnectorStatus] = []
        self._last_refresh: datetime | None = None
        self.refresh()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def connectors(self) -> list[ConnectorStatus]:
        """Return the cached connector status snapshots (a copy)."""
        return list(self._statuses)

    def refresh(self) -> list[ConnectorStatus]:
        """Re-read statuses from the wrapped manager and cache them."""
        self._statuses = self._collect()
        self._last_refresh = datetime.now(UTC)
        return list(self._statuses)

    def health(self) -> dict[str, bool]:
        """Return a ``{connector_name: healthy}`` map from the manager."""
        if self._manager is None:
            return {}
        method = getattr(self._manager, "health", None)
        if not callable(method):
            return {}
        try:
            result = method()
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(result, dict):
            return {}
        # Values may be MCPHealth dataclasses with a `healthy` flag, or bools.
        healthy: dict[str, bool] = {}
        for key, value in result.items():
            healthy[str(key)] = _coerce_bool(value)
        return healthy

    def capabilities(self) -> dict[str, list[str]]:
        """Return a ``{connector_name: [capability, ...]}`` map."""
        if self._manager is None:
            return {}
        method = getattr(self._manager, "all_capabilities", None)
        if not callable(method):
            return {}
        try:
            result = method()
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(result, dict):
            return {}
        return {str(k): list(v) for k, v in result.items()}

    @property
    def last_refresh(self) -> datetime | None:
        """When :meth:`refresh` last ran (UTC), or ``None``."""
        return self._last_refresh

    def __len__(self) -> int:
        return len(self._statuses)

    def __repr__(self) -> str:
        return f"<MCPController connectors={len(self._statuses)}>"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect(self) -> list[ConnectorStatus]:
        """Build :class:`ConnectorStatus` objects for every connector."""
        if self._manager is None:
            return []
        connectors = _call(self._manager, "list_connectors", default=[])
        health_map = self.health()
        caps_map = self.capabilities()
        statuses: list[ConnectorStatus] = []
        for connector in connectors:
            name = getattr(connector, "name", None) or repr(connector)
            connected = bool(getattr(connector, "is_connected", False))
            caps = caps_map.get(str(name), []) or _connector_capabilities(connector)
            latency = self._latency_for(str(name))
            health_level = _health_level(health_map.get(str(name), None), connected)
            statuses.append(
                ConnectorStatus(
                    name=str(name),
                    connected=connected,
                    capabilities=list(caps),
                    latency_ms=latency,
                    health_level=health_level,
                )
            )
        return statuses

    def _latency_for(self, name: str) -> float:
        """Return the average latency (ms) for ``name`` if tracked."""
        if self._manager is None:
            return 0.0
        method = getattr(self._manager, "metrics", None)
        if not callable(method):
            return 0.0
        try:
            metrics = method(name)
        except Exception:  # noqa: BLE001
            return 0.0
        for attr in ("avg_latency_ms", "latency_ms"):
            value = getattr(metrics, attr, None)
            if isinstance(value, int | float):
                return float(value)
        return 0.0


def _call(obj: Any, method_name: str, default: Any) -> Any:
    """Call ``obj.method_name()`` and return the result, or ``default``."""
    method = getattr(obj, method_name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:  # noqa: BLE001
        return default


def _connector_capabilities(connector: Any) -> list[str]:
    """Return the capability names a connector exposes, if any."""
    for method_name in ("capabilities", "available_capabilities", "list_capabilities"):
        method = getattr(connector, method_name, None)
        if callable(method):
            try:
                result = method()
            except Exception:  # noqa: BLE001
                continue
            if isinstance(result, list):
                return [str(c) for c in result]
            if isinstance(result, dict):
                return [str(c) for c in result]
    caps_attr = getattr(connector, "capabilities", None)
    if isinstance(caps_attr, list):
        return [str(c) for c in caps_attr]
    return []


def _coerce_bool(value: Any) -> bool:
    """Coerce a health value (bool or dataclass with ``healthy``) to bool."""
    if isinstance(value, bool):
        return value
    healthy = getattr(value, "healthy", None)
    if isinstance(healthy, bool):
        return healthy
    level = getattr(value, "level", None)
    if isinstance(level, str):
        return level.lower() in {"healthy", "ok", "up"}
    return bool(value)


def _health_level(value: Any, connected: bool) -> str:
    """Map a health value to a human-readable level string."""
    if value is None:
        return "healthy" if connected else "unknown"
    if isinstance(value, bool):
        return "healthy" if value else "unhealthy"
    level = getattr(value, "level", None)
    if isinstance(level, str):
        return level.lower()
    healthy = getattr(value, "healthy", None)
    if isinstance(healthy, bool):
        return "healthy" if healthy else "unhealthy"
    return "unknown"


__all__ = ["MCPController"]
