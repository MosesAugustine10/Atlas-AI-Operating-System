"""Capability-based request routing for the Atlas MCP Layer.

The :class:`MCPRouter` receives an :class:`~atlas.mcp.models.MCPRequest`
and selects the best :class:`~atlas.mcp.base.BaseConnector` to handle
it. Selection is **capability-based**: the router never hardcodes
connector names. Instead, it queries the
:class:`~atlas.mcp.registry.MCPRegistry` for every connector that
exposes the request's capability and picks the first one that is
connected.

If no connected connector exposes the capability, the router raises
:class:`~atlas.mcp.exceptions.MCPCapabilityError`.
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.mcp.base import BaseConnector
from atlas.mcp.exceptions import MCPCapabilityError, MCPNotFoundError
from atlas.mcp.models import MCPRequest
from atlas.mcp.registry import MCPRegistry


class MCPRouter:
    """Routes :class:`MCPRequest` objects to the right connector.

    Parameters:
        registry: The :class:`MCPRegistry` to query for connectors.
    """

    def __init__(self, registry: MCPRegistry) -> None:
        self.registry = registry
        self.logger = get_logger("mcp.router")

    def route(self, request: MCPRequest) -> BaseConnector:
        """Select a connector for ``request``.

        Selection order:
        1. If ``request.connector`` is set and that connector is
           registered and connected, use it.
        2. Otherwise, find every connector that exposes
           ``request.capability`` and pick the first connected one.
        3. If no connected connector is found, raise
           :class:`MCPCapabilityError`.

        Raises:
            MCPCapabilityError: If no connector can handle the request.
            MCPNotFoundError: If ``request.connector`` is set but not
                registered.
        """
        # 1. Explicit connector preference.
        if request.connector:
            connector = self.registry.get_optional(request.connector)
            if connector is None:
                raise MCPNotFoundError(
                    f"connector not registered: {request.connector!r}",
                    resource=request.connector,
                )
            if connector.is_connected:
                return connector
            # Fall through to capability search.

        # 2. Capability-based search.
        candidates = self.registry.find_by_capability(request.capability)
        connected = [c for c in candidates if c.is_connected]
        if connected:
            chosen = connected[0]
            self.logger.debug(
                "Routed request %s to %s (capability=%s)",
                request.id,
                chosen.name,
                request.capability,
            )
            return chosen

        # 3. Nothing found.
        available = [c.name for c in candidates]
        raise (
            MCPCapabilityError(
                f"no connected connector exposes capability {request.capability!r}",
                capability=request.capability,
                connector=request.connector or None,
            )
            if not available
            else MCPCapabilityError(
                f"capability {request.capability!r} exists but no connector is "
                f"connected (available: {available})",
                capability=request.capability,
            )
        )

    def can_route(self, request: MCPRequest) -> bool:
        """Return ``True`` if a connected connector can handle ``request``."""
        try:
            self.route(request)
        except (MCPCapabilityError, MCPNotFoundError):
            return False
        return True

    def available_connectors(self, capability: str) -> list[BaseConnector]:
        """Return every connected connector that exposes ``capability``."""
        return [
            c for c in self.registry.find_by_capability(capability) if c.is_connected
        ]

    def __repr__(self) -> str:
        return f"<MCPRouter registry={len(self.registry)}>"


__all__ = ["MCPRouter"]
