"""Immutable data models for the Atlas MCP Layer.

Every model in this module is a frozen dataclass: once constructed, the
instance cannot be mutated in place. Updates are performed by producing
a new copy via :func:`dataclasses.replace`.

The module is a *leaf* in the MCP package dependency graph: it depends
only on the standard library.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "mcp") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MCPStatus(enum.StrEnum):
    """Lifecycle states for connectors, sessions, and connections.

    Attributes:
        DISCONNECTED: Not connected.
        CONNECTING: Connection in progress.
        CONNECTED: Connection established and healthy.
        DEGRADED: Connected but with warnings (high latency, errors).
        DISCONNECTING: Shutdown in progress.
        FAILED: Connection failed terminally.
        UNKNOWN: State has not been determined yet.
    """

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTING = "disconnecting"
    FAILED = "failed"
    UNKNOWN = "unknown"


class HealthLevel(enum.StrEnum):
    """Aggregate health levels.

    Attributes:
        HEALTHY: All connectors healthy.
        WARNING: At least one connector degraded; none offline.
        CRITICAL: At least one connector offline.
        OFFLINE: Every connector offline.
        UNKNOWN: No connectors registered.
    """

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class TransportKind(enum.StrEnum):
    """Supported transport kinds.

    Attributes:
        STDIO: Standard input/output (local subprocess).
        HTTP: HTTP / REST.
        WEBSOCKET: WebSocket.
        NAMED_PIPE: OS named pipe.
        IN_PROCESS: In-process direct call (testing / placeholders).
    """

    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"
    NAMED_PIPE = "named_pipe"
    IN_PROCESS = "in_process"


#: Transports that do not require any networking.
OFFLINE_TRANSPORTS: frozenset[TransportKind] = frozenset(
    {TransportKind.IN_PROCESS, TransportKind.STDIO}
)


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPCapability:
    """A single capability exposed by a connector.

    Attributes:
        name: Capability identifier (e.g. ``"file.read"``, ``"git.commit"``).
        description: Human-readable description.
        permissions: Permissions required to invoke this capability.
        metadata: Free-form capability metadata (e.g. rate limits).
    """

    name: str
    description: str = ""
    permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPPermission:
    """A permission grant for a connector or capability.

    Attributes:
        name: Permission identifier (e.g. ``"read"``, ``"write"``).
        level: Numeric privilege level (higher = more powerful).
        description: Human-readable description.
    """

    name: str
    level: int = 0
    description: str = ""


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPTransport:
    """Transport configuration for a connector.

    Attributes:
        kind: The :class:`TransportKind`.
        address: Transport-specific address (URL, pipe name, subprocess
            command, etc.).
        options: Free-form transport options (headers, timeouts, etc.).
    """

    kind: TransportKind = TransportKind.IN_PROCESS
    address: str = ""
    options: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPHealth:
    """Health snapshot for a single connector.

    Attributes:
        connector: Name of the connector this health describes.
        status: The :class:`MCPStatus`.
        level: The :class:`HealthLevel`.
        latency_ms: Last measured round-trip latency in milliseconds.
            ``None`` if not measured.
        last_check_at: When the last health check ran.
        last_error: Last error message (``None`` if healthy).
        uptime_seconds: How long the connector has been connected.
        metadata: Free-form health metadata.
    """

    connector: str
    status: MCPStatus = MCPStatus.UNKNOWN
    level: HealthLevel = HealthLevel.UNKNOWN
    latency_ms: float | None = None
    last_check_at: datetime | None = None
    last_error: str | None = None
    uptime_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPConnection:
    """An established connection to a connector.

    Attributes:
        id: Unique connection identifier.
        connector: Name of the connector this connection uses.
        transport: The :class:`MCPTransport` in use.
        status: The :class:`MCPStatus` of the connection.
        connected_at: When the connection was established.
        disconnected_at: When the connection was closed (``None`` if
            still open).
        session_id: Optional session identifier associated with this
            connection.
        metadata: Free-form connection metadata.
    """

    id: str = field(default_factory=lambda: _new_id("conn"))
    connector: str = ""
    transport: MCPTransport = field(default_factory=MCPTransport)
    status: MCPStatus = MCPStatus.DISCONNECTED
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPRequest:
    """A request sent to a connector.

    Attributes:
        id: Unique request identifier.
        connector: Name of the target connector.
        capability: The capability to invoke.
        params: Parameters for the capability.
        permission: The permission level the caller holds.
        timeout_seconds: Maximum time to wait for a response.
        created_at: When the request was created.
        metadata: Free-form request metadata.
    """

    id: str = field(default_factory=lambda: _new_id("req"))
    connector: str = ""
    capability: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    permission: str = "read"
    timeout_seconds: float = 30.0
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPResponse:
    """A response returned by a connector.

    Attributes:
        request_id: The id of the :class:`MCPRequest` this responds to.
        connector: Name of the connector that produced the response.
        success: Whether the request succeeded.
        output: The response payload (any picklable object).
        error: Error message if ``success`` is ``False``.
        latency_ms: Round-trip latency in milliseconds.
        completed_at: When the response was produced.
        metadata: Free-form response metadata.
    """

    request_id: str
    connector: str = ""
    success: bool = True
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    completed_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPSession:
    """An MCP session — a logical conversation with one or more connectors.

    Attributes:
        id: Unique session identifier.
        connector: Name of the primary connector for this session.
        status: The :class:`MCPStatus` of the session.
        created_at: When the session was opened.
        last_active_at: When the session was last used.
        closed_at: When the session was closed (``None`` if open).
        permissions: Permissions granted to this session.
        metadata: Free-form session metadata.
        request_count: Number of requests sent on this session.
        error_count: Number of errors encountered on this session.
    """

    id: str = field(default_factory=lambda: _new_id("session"))
    connector: str = ""
    status: MCPStatus = MCPStatus.DISCONNECTED
    created_at: datetime = field(default_factory=_utcnow)
    last_active_at: datetime = field(default_factory=_utcnow)
    closed_at: datetime | None = None
    permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    request_count: int = 0
    error_count: int = 0

    def is_open(self) -> bool:
        """Return ``True`` if the session is currently open."""
        return (
            self.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)
            and self.closed_at is None
        )


# ---------------------------------------------------------------------------
# Server / Client
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPServer:
    """A registered MCP server (a connector exposed over a transport).

    Attributes:
        id: Unique server identifier.
        name: Human-readable server name.
        description: Free-form description.
        transport: The :class:`MCPTransport` the server listens on.
        capabilities: Capabilities the server exposes.
        status: The :class:`MCPStatus` of the server.
        created_at: When the server was registered.
        metadata: Free-form server metadata.
    """

    id: str = field(default_factory=lambda: _new_id("server"))
    name: str = ""
    description: str = ""
    transport: MCPTransport = field(default_factory=MCPTransport)
    capabilities: tuple[MCPCapability, ...] = ()
    status: MCPStatus = MCPStatus.DISCONNECTED
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPClient:
    """A client that talks to MCP servers.

    Attributes:
        id: Unique client identifier.
        name: Human-readable client name.
        server_id: The id of the :class:`MCPServer` this client talks to.
        status: The :class:`MCPStatus` of the client.
        permissions: Permissions granted to this client.
        created_at: When the client was created.
        last_active_at: When the client was last active.
        metadata: Free-form client metadata.
    """

    id: str = field(default_factory=lambda: _new_id("client"))
    name: str = ""
    server_id: str = ""
    status: MCPStatus = MCPStatus.DISCONNECTED
    permissions: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    last_active_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Metrics / Statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPMetrics:
    """Per-connector metrics.

    Attributes:
        connector: Name of the connector these metrics describe.
        requests_total: Total number of requests sent.
        requests_succeeded: Number of successful requests.
        requests_failed: Number of failed requests.
        avg_latency_ms: Average round-trip latency in milliseconds.
        max_latency_ms: Maximum observed latency in milliseconds.
        min_latency_ms: Minimum observed latency in milliseconds.
        bytes_sent: Total bytes sent (estimated).
        bytes_received: Total bytes received (estimated).
        uptime_seconds: Total connected uptime.
        last_error: Most recent error message.
        last_request_at: When the last request was sent.
    """

    connector: str = ""
    requests_total: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0
    uptime_seconds: float = 0.0
    last_error: str | None = None
    last_request_at: datetime | None = None


@dataclass(frozen=True)
class MCPStatistics:
    """Aggregate statistics across every connector.

    Attributes:
        connectors_total: Total registered connectors.
        connectors_connected: Number currently connected.
        connectors_degraded: Number currently degraded.
        connectors_offline: Number currently offline.
        sessions_total: Total sessions opened.
        sessions_active: Number currently active.
        requests_total: Total requests across every connector.
        requests_succeeded: Total successful requests.
        requests_failed: Total failed requests.
        overall_health: The :class:`HealthLevel` roll-up.
        collected_at: When these statistics were computed.
    """

    connectors_total: int = 0
    connectors_connected: int = 0
    connectors_degraded: int = 0
    connectors_offline: int = 0
    sessions_total: int = 0
    sessions_active: int = 0
    requests_total: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    overall_health: HealthLevel = HealthLevel.UNKNOWN
    collected_at: datetime = field(default_factory=_utcnow)


__all__ = [
    "HealthLevel",
    "MCPCapability",
    "MCPClient",
    "MCPConnection",
    "MCPHealth",
    "MCPMetrics",
    "MCPPermission",
    "MCPRequest",
    "MCPResponse",
    "MCPServer",
    "MCPSession",
    "MCPStatistics",
    "MCPStatus",
    "MCPTransport",
    "OFFLINE_TRANSPORTS",
    "TransportKind",
]
