"""MCP manager — the top-level orchestrator for the MCP Layer.

The :class:`MCPManager` is the single entry point through which the rest
of Atlas interacts with MCP connectors. It owns a
:class:`~atlas.mcp.registry.MCPRegistry`, a
:class:`~atlas.mcp.session.SessionManager`, a
:class:`~atlas.mcp.router.MCPRouter`, a
:class:`~atlas.mcp.health.MCPHealthMonitor`, a
:class:`~atlas.mcp.heartbeat.HeartbeatMonitor`, and a
:class:`~atlas.mcp.permissions.PermissionValidator`. Every dependency is
injectable.

Public API:

* **Connector registration**: :meth:`register_connector`,
  :meth:`unregister_connector`, :meth:`get_connector`,
  :meth:`list_connectors`.
* **Session management**: :meth:`open_session`, :meth:`close_session`,
  :meth:`get_session`.
* **Execution**: :meth:`execute` — route + permission-check + execute +
  record metrics.
* **Health**: :meth:`health`, :meth:`is_healthy`, :meth:`statistics`.
* **Heartbeat**: :meth:`heartbeat`.
* **Reconnect**: :meth:`reconnect`.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.base import BaseConnector
from atlas.mcp.exceptions import (
    MCPError,
    MCPNotFoundError,
    MCPPermissionError,
)
from atlas.mcp.health import MCPHealthMonitor
from atlas.mcp.heartbeat import HeartbeatMonitor
from atlas.mcp.models import (
    HealthLevel,
    MCPHealth,
    MCPMetrics,
    MCPRequest,
    MCPResponse,
    MCPSession,
    MCPStatistics,
)
from atlas.mcp.permissions import PermissionValidator
from atlas.mcp.registry import MCPRegistry
from atlas.mcp.router import MCPRouter
from atlas.mcp.session import SessionManager


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class MCPManager:
    """Top-level orchestrator for the Atlas MCP Layer.

    Parameters:
        registry: The :class:`MCPRegistry` to use. A new one is created
            if omitted.
        sessions: The :class:`SessionManager` to use. A new one is
            created if omitted.
        permissions: The :class:`PermissionValidator` to use. A new one
            is created if omitted.
        auto_connect: If ``True`` (default), connectors are connected
            immediately upon registration.
    """

    def __init__(
        self,
        registry: MCPRegistry | None = None,
        sessions: SessionManager | None = None,
        permissions: PermissionValidator | None = None,
        auto_connect: bool = True,
    ) -> None:
        # NOTE: explicit ``is None`` checks because some dependencies
        # define ``__len__`` and would be falsy when empty.
        self.registry = registry if registry is not None else MCPRegistry()
        self.sessions = sessions if sessions is not None else SessionManager()
        self.permissions = (
            permissions if permissions is not None else PermissionValidator()
        )
        self.router = MCPRouter(self.registry)
        self.health_monitor = MCPHealthMonitor(self.registry)
        self.heartbeat_monitor = HeartbeatMonitor(self.registry)
        self.auto_connect = auto_connect
        self.logger = get_logger("mcp.manager")
        self._metrics: dict[str, list[float]] = {}
        self._request_count: int = 0
        self._error_count: int = 0

    # ------------------------------------------------------------------
    # Connector registration
    # ------------------------------------------------------------------

    def register_connector(
        self,
        connector: BaseConnector,
        tags: list[str] | None = None,
    ) -> BaseConnector:
        """Register a connector and (optionally) connect it immediately."""
        self.registry.register(connector, tags=tags)
        if self.auto_connect and not connector.is_connected:
            try:
                connector.connect()
            except MCPError as exc:
                self.logger.warning(
                    "Auto-connect failed for %s: %s", connector.name, exc
                )
        return connector

    def unregister_connector(self, name: str) -> bool:
        """Remove a connector by name."""
        return self.registry.unregister(name)

    def get_connector(self, name: str) -> BaseConnector:
        """Look up a connector by name.

        Raises:
            MCPNotFoundError: If ``name`` is not registered.
        """
        return self.registry.get(name)

    def list_connectors(self) -> list[BaseConnector]:
        """Return every registered connector."""
        return self.registry.list()

    def connector_names(self) -> list[str]:
        """Return every registered connector name."""
        return self.registry.names()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def open_session(
        self,
        connector: str,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MCPSession:
        """Open a new session for ``connector``."""
        if not self.registry.contains(connector):
            raise MCPNotFoundError(
                f"cannot open session: connector {connector!r} not registered",
                resource=connector,
            )
        return self.sessions.open(connector, permissions=permissions, metadata=metadata)

    def close_session(self, session_id: str) -> MCPSession | None:
        """Close a session by id."""
        return self.sessions.close(session_id)

    def get_session(self, session_id: str) -> MCPSession:
        """Return the session for ``session_id``."""
        return self.sessions.get(session_id)

    def list_sessions(self, include_closed: bool = False) -> list[MCPSession]:
        """Return every session."""
        return self.sessions.list(include_closed=include_closed)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        request: MCPRequest,
        session_id: str | None = None,
    ) -> MCPResponse:
        """Route and execute ``request``.

        Args:
            request: The :class:`MCPRequest` to execute.
            session_id: Optional session id. If supplied, the session's
                permissions are used for the permission check and the
                request is recorded against the session.

        Raises:
            MCPCapabilityError: If no connector can handle the request.
            MCPPermissionError: If the session lacks the required
                permission.
            MCPExecutionError: If the connector raises during execution.
        """
        # 1. Permission check.
        permissions = self._session_permissions(session_id)
        connector = self.router.route(request)
        required = connector.required_permission
        if not self.permissions.can(permissions, required):
            raise MCPPermissionError(
                required=required.name,
                actual=str(self.permissions.effective_level(permissions)),
                connector=connector.name,
            )

        # 2. Execute.
        self._request_count += 1
        response = connector.execute(request)
        self._record_metrics(connector.name, response)

        # 3. Record against session.
        if session_id is not None:
            self.sessions.record_request(session_id, response)

        if not response.success:
            self._error_count += 1
        return response

    def execute_capability(
        self,
        capability: str,
        params: dict[str, Any] | None = None,
        connector: str | None = None,
        session_id: str | None = None,
        permission: str = "read",
    ) -> MCPResponse:
        """Convenience wrapper for :meth:`execute` that builds the request."""
        request = MCPRequest(
            connector=connector or "",
            capability=capability,
            params=dict(params or {}),
            permission=permission,
        )
        return self.execute(request, session_id=session_id)

    # ------------------------------------------------------------------
    # Health & statistics
    # ------------------------------------------------------------------

    def health(self) -> dict[str, MCPHealth]:
        """Return a ``{connector_name: MCPHealth}`` map."""
        return self.health_monitor.snapshot()

    def is_healthy(self) -> bool:
        """Return ``True`` if every connector is healthy."""
        return self.health_monitor.is_healthy()

    def overall_health(self) -> HealthLevel:
        """Return the roll-up :class:`HealthLevel`."""
        return self.health_monitor.overall()

    def statistics(self) -> MCPStatistics:
        """Return a :class:`MCPStatistics` snapshot."""
        stats = self.registry.statistics()
        return dataclasses.replace(
            stats,
            sessions_total=self.sessions.total_count(),
            sessions_active=self.sessions.active_count(),
            requests_total=self._request_count,
            requests_succeeded=self._request_count - self._error_count,
            requests_failed=self._error_count,
        )

    def metrics(self, connector_name: str) -> MCPMetrics:
        """Return :class:`MCPMetrics` for ``connector_name``."""
        latencies = self._metrics.get(connector_name, [])
        connector = self.registry.get_optional(connector_name)
        requests_total = len(latencies)
        succeeded = sum(1 for lat in latencies if lat >= 0)  # placeholder
        failed = 0  # tracked at manager level
        avg = sum(latencies) / len(latencies) if latencies else 0.0
        return MCPMetrics(
            connector=connector_name,
            requests_total=requests_total,
            requests_succeeded=succeeded,
            requests_failed=failed,
            avg_latency_ms=avg,
            max_latency_ms=max(latencies) if latencies else 0.0,
            min_latency_ms=min(latencies) if latencies else 0.0,
            uptime_seconds=connector.uptime_seconds if connector else 0.0,
        )

    # ------------------------------------------------------------------
    # Heartbeat & reconnect
    # ------------------------------------------------------------------

    def heartbeat(self) -> list[str]:
        """Probe every connector and return the names of those needing reconnect."""
        samples = self.heartbeat_monitor.beat()
        return [s.connector for s in samples if not s.success]

    def reconnect(self, connector_name: str) -> bool:
        """Attempt to reconnect ``connector_name``.

        Returns ``True`` if the connector is connected after the attempt.
        """
        connector = self.registry.get_optional(connector_name)
        if connector is None:
            return False
        if connector.is_connected:
            return True
        try:
            connector.connect()
            return connector.is_connected
        except MCPError as exc:
            self.logger.warning("Reconnect failed for %s: %s", connector_name, exc)
            return False

    def reconnect_all(self) -> dict[str, bool]:
        """Attempt to reconnect every disconnected connector."""
        results: dict[str, bool] = {}
        for connector in self.registry.list():
            if not connector.is_connected:
                results[connector.name] = self.reconnect(connector.name)
        return results

    # ------------------------------------------------------------------
    # Capability lookup
    # ------------------------------------------------------------------

    def find_by_capability(self, capability: str) -> list[BaseConnector]:
        """Return every connector that exposes ``capability``."""
        return self.registry.find_by_capability(capability)

    def all_capabilities(self) -> dict[str, list[str]]:
        """Return a ``{connector_name: [capability_name, ...]}`` map."""
        return self.registry.all_capabilities()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _session_permissions(self, session_id: str | None) -> list[str]:
        """Return the permissions for ``session_id`` (or empty list)."""
        if session_id is None:
            return []
        session = self.sessions.get_optional(session_id)
        if session is None:
            return []
        return list(session.permissions)

    def _record_metrics(self, connector_name: str, response: MCPResponse) -> None:
        """Record latency for ``connector_name``."""
        self._metrics.setdefault(connector_name, []).append(response.latency_ms)

    def __repr__(self) -> str:
        stats = self.statistics()
        return (
            f"<MCPManager connectors={stats.connectors_total} "
            f"sessions={stats.sessions_active} requests={stats.requests_total}>"
        )


__all__ = ["MCPManager"]
