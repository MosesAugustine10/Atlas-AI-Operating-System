"""Abstract base class for every MCP connector.

The :class:`BaseConnector` is the contract that every concrete connector
(filesystem, github, browser, blender, ollama, etc.) implements. It
defines the lifecycle methods that the :class:`~atlas.mcp.manager.MCPManager`
calls:

* :meth:`connect` — establish a connection.
* :meth:`disconnect` — close the connection.
* :meth:`health` — return a health snapshot.
* :meth:`capabilities` — return the capabilities this connector exposes.
* :meth:`execute` — run a single :class:`~atlas.mcp.models.MCPRequest`.
* :meth:`discover` — return a description of what this connector can do.

Concrete connectors override :meth:`_do_connect`, :meth:`_do_disconnect`,
:meth:`_do_health`, and :meth:`_do_execute`. The base class handles
state transitions, error wrapping, and bookkeeping.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.exceptions import (
    MCPConnectionError,
)
from atlas.mcp.models import (
    HealthLevel,
    MCPCapability,
    MCPHealth,
    MCPRequest,
    MCPResponse,
    MCPStatus,
    MCPTransport,
    TransportKind,
)
from atlas.mcp.permissions import PermissionLevel


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class BaseConnector(ABC):
    """Abstract base class for every MCP connector.

    Concrete connectors must implement :meth:`_do_connect`,
    :meth:`_do_disconnect`, :meth:`_do_health`, :meth:`_do_execute`,
    and :meth:`_do_capabilities`. The base class handles state
    transitions and error wrapping.

    Parameters:
        name: Unique connector name.
        description: Human-readable description.
        supported_transports: Tuple of :class:`TransportKind` values
            this connector can use. Defaults to
            ``(TransportKind.IN_PROCESS,)``.
        default_transport: The transport to use when none is specified.
        required_permission: The minimum :class:`PermissionLevel`
            required to invoke any capability on this connector.
        capabilities: Tuple of :class:`MCPCapability` items this
            connector exposes.
        metadata: Free-form connector metadata.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        supported_transports: tuple[TransportKind, ...] = (TransportKind.IN_PROCESS,),
        default_transport: TransportKind = TransportKind.IN_PROCESS,
        required_permission: PermissionLevel = PermissionLevel.READ,
        capabilities: tuple[MCPCapability, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("Connector name must be non-empty.")
        self.name = name
        self.description = description
        self.supported_transports = tuple(supported_transports)
        self.default_transport = default_transport
        self.required_permission = required_permission
        self._capabilities: tuple[MCPCapability, ...] = tuple(capabilities)
        self.metadata: dict[str, Any] = dict(metadata or {})
        self._status: MCPStatus = MCPStatus.DISCONNECTED
        self._connected_at: datetime | None = None
        self._disconnected_at: datetime | None = None
        self._last_error: str | None = None
        self._logger = get_logger(f"mcp.connector.{name}")

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> MCPStatus:
        """The current :class:`MCPStatus` of this connector."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the connector is connected or degraded."""
        return self._status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)

    @property
    def connected_at(self) -> datetime | None:
        """When the connector was last connected."""
        return self._connected_at

    @property
    def last_error(self) -> str | None:
        """The most recent error message (``None`` if healthy)."""
        return self._last_error

    @property
    def uptime_seconds(self) -> float:
        """Seconds since the connector was connected."""
        if self._connected_at is None:
            return 0.0
        return (_utcnow() - self._connected_at).total_seconds()

    # ------------------------------------------------------------------
    # Public lifecycle methods (final — do not override)
    # ------------------------------------------------------------------

    def connect(self, transport: MCPTransport | None = None) -> None:
        """Establish a connection to the connector's backend.

        Subclasses implement :meth:`_do_connect` for the actual work.
        """
        if self.is_connected:
            return
        self._status = MCPStatus.CONNECTING
        self._last_error = None
        try:
            self._do_connect(transport or MCPTransport(kind=self.default_transport))
        except Exception as exc:  # noqa: BLE001
            self._status = MCPStatus.FAILED
            self._last_error = str(exc)
            self._logger.error("Failed to connect %s: %s", self.name, exc)
            raise MCPConnectionError(
                f"failed to connect {self.name!r}: {exc}",
                connector=self.name,
            ) from exc
        self._status = MCPStatus.CONNECTED
        self._connected_at = _utcnow()
        self._disconnected_at = None
        self._logger.info("Connected %s", self.name)

    def disconnect(self) -> None:
        """Close the connection.

        Subclasses implement :meth:`_do_disconnect` for the actual work.
        """
        if not self.is_connected:
            self._status = MCPStatus.DISCONNECTED
            return
        self._status = MCPStatus.DISCONNECTING
        try:
            self._do_disconnect()
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            self._logger.warning("Error while disconnecting %s: %s", self.name, exc)
        self._status = MCPStatus.DISCONNECTED
        self._disconnected_at = _utcnow()
        self._logger.info("Disconnected %s", self.name)

    def health(self) -> MCPHealth:
        """Return a :class:`MCPHealth` snapshot for this connector."""
        try:
            snapshot = self._do_health()
        except Exception as exc:  # noqa: BLE001
            snapshot = MCPHealth(
                connector=self.name,
                status=MCPStatus.FAILED,
                level=HealthLevel.CRITICAL,
                last_error=str(exc),
                last_check_at=_utcnow(),
            )
        # Always reconcile the snapshot's status with the base-class
        # status. If the connector is not connected, the health snapshot
        # must reflect that — even if the subclass implementation reported
        # CONNECTED.
        if self._status is not MCPStatus.CONNECTED:
            snapshot = MCPHealth(
                connector=self.name,
                status=self._status,
                level=self._status_to_level(self._status),
                latency_ms=snapshot.latency_ms,
                last_check_at=_utcnow(),
                last_error=self._last_error,
                uptime_seconds=0.0,
                metadata=snapshot.metadata,
            )
        elif snapshot.connector == "":
            snapshot = MCPHealth(
                connector=self.name,
                status=self._status,
                level=self._status_to_level(self._status),
                latency_ms=snapshot.latency_ms,
                last_check_at=_utcnow(),
                last_error=self._last_error,
                uptime_seconds=self.uptime_seconds,
                metadata=snapshot.metadata,
            )
        return snapshot

    def capabilities(self) -> tuple[MCPCapability, ...]:
        """Return the capabilities this connector exposes."""
        return self._do_capabilities()

    def execute(self, request: MCPRequest) -> MCPResponse:
        """Execute ``request`` and return an :class:`MCPResponse`.

        Subclasses implement :meth:`_do_execute` for the actual work.
        """
        if not self.is_connected:
            return MCPResponse(
                request_id=request.id,
                connector=self.name,
                success=False,
                error=f"connector {self.name!r} is not connected",
            )
        started = _utcnow()
        try:
            output = self._do_execute(request)
            latency = (_utcnow() - started).total_seconds() * 1000.0
            return MCPResponse(
                request_id=request.id,
                connector=self.name,
                success=True,
                output=output,
                latency_ms=latency,
            )
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            latency = (_utcnow() - started).total_seconds() * 1000.0
            self._logger.warning("Execute failed on %s: %s", self.name, exc)
            return MCPResponse(
                request_id=request.id,
                connector=self.name,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=latency,
            )

    def discover(self) -> dict[str, Any]:
        """Return a discovery descriptor for this connector."""
        return {
            "name": self.name,
            "description": self.description,
            "status": self._status.value,
            "supported_transports": [t.value for t in self.supported_transports],
            "default_transport": self.default_transport.value,
            "required_permission": self.required_permission.name,
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "permissions": list(c.permissions),
                }
                for c in self.capabilities()
            ],
            "metadata": dict(self.metadata),
        }

    # ------------------------------------------------------------------
    # Abstract methods (subclasses must implement)
    # ------------------------------------------------------------------

    @abstractmethod
    def _do_connect(self, transport: MCPTransport) -> None:
        """Actually establish the connection."""

    @abstractmethod
    def _do_disconnect(self) -> None:
        """Actually close the connection."""

    @abstractmethod
    def _do_health(self) -> MCPHealth:
        """Actually probe the connector's health."""

    @abstractmethod
    def _do_execute(self, request: MCPRequest) -> Any:
        """Actually execute ``request`` and return its output."""

    def _do_capabilities(self) -> tuple[MCPCapability, ...]:
        """Return the capabilities this connector exposes.

        Default implementation returns the capabilities passed to the
        constructor. Override to compute dynamically.
        """
        return self._capabilities

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_to_level(status: MCPStatus) -> HealthLevel:
        """Map a :class:`MCPStatus` to a :class:`HealthLevel`."""
        if status is MCPStatus.CONNECTED:
            return HealthLevel.HEALTHY
        if status is MCPStatus.DEGRADED:
            return HealthLevel.WARNING
        if status in (MCPStatus.DISCONNECTED, MCPStatus.FAILED):
            return HealthLevel.CRITICAL
        if status is MCPStatus.DISCONNECTING:
            return HealthLevel.WARNING
        return HealthLevel.UNKNOWN

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.name!r} "
            f"status={self._status.value}>"
        )


# ---------------------------------------------------------------------------
# Placeholder connector — used by tests and as a fallback
# ---------------------------------------------------------------------------


class PlaceholderConnector(BaseConnector):
    """A deterministic placeholder connector.

    Useful for testing and as a fallback when no real connector is
    available. Always connects successfully, reports healthy, and
    returns a deterministic response for every request.
    """

    def __init__(
        self,
        name: str = "placeholder",
        description: str = "Deterministic placeholder MCP connector",
        capabilities: tuple[MCPCapability, ...] | None = None,
        **kwargs: Any,
    ) -> None:
        if capabilities is None:
            capabilities = (
                MCPCapability(name="ping", description="Always returns pong"),
                MCPCapability(name="echo", description="Echoes the request params"),
            )
        super().__init__(
            name=name,
            description=description,
            capabilities=capabilities,
            **kwargs,
        )

    def _do_connect(self, transport: MCPTransport) -> None:  # noqa: ARG002
        """No-op connect."""
        return None

    def _do_disconnect(self) -> None:
        """No-op disconnect."""
        return None

    def _do_health(self) -> MCPHealth:
        return MCPHealth(
            connector=self.name,
            status=MCPStatus.CONNECTED,
            level=HealthLevel.HEALTHY,
            latency_ms=0.1,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "ping":
            return "pong"
        if request.capability == "echo":
            return dict(request.params)
        return {
            "status": "ok",
            "capability": request.capability,
            "params": request.params,
        }


__all__ = ["BaseConnector", "PlaceholderConnector"]
