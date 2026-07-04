"""MCP registry — catalogs every registered connector.

The :class:`MCPRegistry` is the in-memory catalog of registered
:class:`~atlas.mcp.base.BaseConnector` instances. Connectors are keyed
by their unique ``name``. Registration is explicit so that connectors
are only available when deliberately added.

The registry supports lookup by name, by capability, and by tag. It
also exposes a :meth:`statistics` method that returns a
:class:`~atlas.mcp.models.MCPStatistics` snapshot.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.base import BaseConnector
from atlas.mcp.exceptions import MCPNotFoundError, MCPRegistryError
from atlas.mcp.models import (
    HealthLevel,
    MCPStatistics,
    MCPStatus,
)


class MCPRegistry:
    """In-memory catalog of registered MCP connectors.

    Connectors are keyed by their unique ``name``. Registering a
    duplicate name raises :class:`MCPRegistryError`.
    """

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}
        self._tags: dict[str, set[str]] = {}
        self.logger = get_logger("mcp.registry")

    def register(
        self,
        connector: BaseConnector,
        tags: list[str] | None = None,
    ) -> MCPRegistry:
        """Register ``connector``. Returns self for chaining.

        Raises:
            MCPRegistryError: If a connector with the same name is
                already registered.
        """
        if connector.name in self._connectors:
            raise MCPRegistryError(f"connector already registered: {connector.name!r}")
        self._connectors[connector.name] = connector
        for tag in tags or []:
            self._tags.setdefault(tag, set()).add(connector.name)
        self.logger.info("Registered connector: %s", connector.name)
        return self

    def unregister(self, name: str) -> bool:
        """Remove a connector by name. Return ``True`` if it existed."""
        connector = self._connectors.pop(name, None)
        if connector is None:
            return False
        for tag_names in self._tags.values():
            tag_names.discard(name)
        # Try to disconnect on unregister.
        try:
            if connector.is_connected:
                connector.disconnect()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Error disconnecting %s on unregister: %s", name, exc)
        self.logger.info("Unregistered connector: %s", name)
        return True

    def get(self, name: str) -> BaseConnector:
        """Look up a connector by name.

        Raises:
            MCPNotFoundError: If ``name`` is not registered.
        """
        connector = self._connectors.get(name)
        if connector is None:
            raise MCPNotFoundError(f"connector not registered: {name!r}", resource=name)
        return connector

    def get_optional(self, name: str) -> BaseConnector | None:
        """Look up a connector by name, returning ``None`` if not found."""
        return self._connectors.get(name)

    def contains(self, name: str) -> bool:
        """Return ``True`` if a connector with ``name`` is registered."""
        return name in self._connectors

    def find(self, predicate: Any) -> list[BaseConnector]:
        """Return every connector for which ``predicate(connector)`` is truthy."""
        if not callable(predicate):
            raise TypeError("predicate must be callable")
        return [c for c in self._connectors.values() if predicate(c)]

    def find_by_capability(self, capability: str) -> list[BaseConnector]:
        """Return every connector that exposes ``capability``."""
        result: list[BaseConnector] = []
        for connector in self._connectors.values():
            caps = connector.capabilities()
            if any(c.name == capability for c in caps):
                result.append(connector)
        return result

    def find_by_tag(self, tag: str) -> list[BaseConnector]:
        """Return every connector tagged with ``tag``."""
        names = self._tags.get(tag, set())
        return [self._connectors[n] for n in sorted(names)]

    def list(self) -> list[BaseConnector]:
        """Return every registered connector, ordered by name."""
        return [self._connectors[name] for name in sorted(self._connectors)]

    def names(self) -> list[str]:
        """Return a sorted list of every registered connector name."""
        return sorted(self._connectors)

    def tags(self) -> list[str]:
        """Return a sorted list of every tag that has at least one connector."""
        return sorted(tag for tag, names in self._tags.items() if names)

    def all_capabilities(self) -> dict[str, list[str]]:
        """Return a ``{connector_name: [capability_name, ...]}`` map."""
        return {
            name: [c.name for c in connector.capabilities()]
            for name, connector in self._connectors.items()
        }

    def statistics(self) -> MCPStatistics:
        """Return a :class:`MCPStatistics` snapshot."""
        connectors = list(self._connectors.values())
        connected = sum(1 for c in connectors if c.status is MCPStatus.CONNECTED)
        degraded = sum(1 for c in connectors if c.status is MCPStatus.DEGRADED)
        offline = sum(
            1
            for c in connectors
            if c.status in (MCPStatus.DISCONNECTED, MCPStatus.FAILED)
        )
        if not connectors:
            overall = HealthLevel.UNKNOWN
        elif offline == len(connectors):
            overall = HealthLevel.OFFLINE
        elif offline > 0:
            overall = HealthLevel.CRITICAL
        elif degraded > 0:
            overall = HealthLevel.WARNING
        else:
            overall = HealthLevel.HEALTHY
        return MCPStatistics(
            connectors_total=len(connectors),
            connectors_connected=connected,
            connectors_degraded=degraded,
            connectors_offline=offline,
            overall_health=overall,
        )

    def __iter__(self) -> Iterator[BaseConnector]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self._connectors)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._connectors

    def __repr__(self) -> str:
        return f"<MCPRegistry connectors={len(self)}>"


__all__ = ["MCPRegistry"]
