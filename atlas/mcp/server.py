"""MCP server — exposes a set of capabilities over a transport.

The :class:`MCPServer` is the server-side of the MCP protocol. It owns a
set of :class:`~atlas.mcp.models.MCPCapability` items, performs
handshakes with connecting clients, and dispatches incoming
:class:`~atlas.mcp.models.MCPRequest` objects to a handler callable.

The current implementation is **in-process and synchronous**: there is
no real network listener. The :meth:`handle` method is called directly
by a :class:`~atlas.mcp.client.MCPClient` (or a test). Future versions
can layer a real transport on top without changing the contract.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from atlas.core.logger import get_logger
from atlas.mcp.exceptions import MCPHandshakeError, MCPProtocolError
from atlas.mcp.models import (
    MCPCapability,
    MCPRequest,
    MCPResponse,
    MCPServer,
    MCPStatus,
    MCPTransport,
    TransportKind,
)
from atlas.mcp.protocol import (
    HandshakeRequest,
    HandshakeResponse,
    perform_handshake,
)


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


Handler = Callable[[MCPRequest], MCPResponse]


class MCPServerInstance:
    """A running MCP server instance.

    Wraps an :class:`MCPServer` descriptor with runtime state
    (handler, connected clients, request count).

    Parameters:
        name: Server name.
        description: Human-readable description.
        capabilities: Capabilities the server exposes.
        transport: Transport configuration (informational).
        handler: Callable ``(MCPRequest) -> MCPResponse`` that handles
            incoming requests.
        auth_required: Whether authentication is required for handshakes.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        capabilities: tuple[MCPCapability, ...] = (),
        transport: MCPTransport | None = None,
        handler: Handler | None = None,
        auth_required: bool = False,
    ) -> None:
        self.descriptor = MCPServer(
            name=name,
            description=description,
            transport=transport or MCPTransport(kind=TransportKind.IN_PROCESS),
            capabilities=capabilities,
            status=MCPStatus.DISCONNECTED,
        )
        self._handler: Handler | None = handler
        self.auth_required = auth_required
        self._clients: set[str] = set()
        self._request_count: int = 0
        self._error_count: int = 0
        self._started_at: datetime | None = None
        self.logger = get_logger(f"mcp.server.{name}")

    @property
    def name(self) -> str:
        """Return the server name."""
        return self.descriptor.name

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the server is started."""
        return self.descriptor.status is MCPStatus.CONNECTED

    @property
    def request_count(self) -> int:
        """Return the total number of requests handled."""
        return self._request_count

    @property
    def client_count(self) -> int:
        """Return the number of connected clients."""
        return len(self._clients)

    def set_handler(self, handler: Handler) -> None:
        """Set the request handler."""
        if not callable(handler):
            raise TypeError("handler must be callable")
        self._handler = handler

    def start(self) -> None:
        """Start the server."""
        self._started_at = _utcnow()
        self.descriptor = _replace_status(self.descriptor, MCPStatus.CONNECTED)
        self.logger.info("Started server %s", self.name)

    def stop(self) -> None:
        """Stop the server."""
        self.descriptor = _replace_status(self.descriptor, MCPStatus.DISCONNECTED)
        self._clients.clear()
        self.logger.info("Stopped server %s", self.name)

    def handshake(self, request: HandshakeRequest) -> HandshakeResponse:
        """Perform a handshake with a connecting client.

        Raises:
            MCPHandshakeError: If the client's protocol version is not
                supported.
        """
        if not self.is_running:
            raise MCPHandshakeError(
                f"server {self.name!r} is not running",
                connector=self.name,
            )
        response = perform_handshake(
            request,
            server_name=self.name,
            server_capabilities=tuple(c.name for c in self.descriptor.capabilities),
            auth_required=self.auth_required,
        )
        if not response.success:
            raise MCPHandshakeError(
                response.error or "handshake failed",
                connector=self.name,
            )
        self._clients.add(request.client_id)
        return response

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Handle an incoming :class:`MCPRequest`."""
        if not self.is_running:
            return MCPResponse(
                request_id=request.id,
                connector=self.name,
                success=False,
                error=f"server {self.name!r} is not running",
            )
        # Validate capability.
        cap_names = {c.name for c in self.descriptor.capabilities}
        if request.capability and request.capability not in cap_names:
            raise MCPProtocolError(
                f"capability {request.capability!r} not exposed"
                f" by server {self.name!r}",
                connector=self.name,
            )
        self._request_count += 1
        if self._handler is None:
            return MCPResponse(
                request_id=request.id,
                connector=self.name,
                success=False,
                error="no handler configured",
            )
        try:
            response = self._handler(request)
        except Exception as exc:  # noqa: BLE001
            self._error_count += 1
            return MCPResponse(
                request_id=request.id,
                connector=self.name,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        if not response.success:
            self._error_count += 1
        return response

    def __repr__(self) -> str:
        return (
            f"<MCPServerInstance name={self.name!r} "
            f"running={self.is_running} clients={self.client_count}>"
        )


def _replace_status(server: MCPServer, status: MCPStatus) -> MCPServer:
    """Return a copy of ``server`` with ``status`` updated."""
    import dataclasses

    return dataclasses.replace(server, status=status)


__all__ = ["MCPServerInstance"]
