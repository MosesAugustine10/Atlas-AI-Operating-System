"""MCP client — talks to an MCP server.

The :class:`MCPClientInstance` is the client-side of the MCP protocol.
It performs a handshake with a :class:`~atlas.mcp.server.MCPServerInstance`,
then sends :class:`~atlas.mcp.models.MCPRequest` objects and receives
:class:`~atlas.mcp.models.MCPResponse` objects.

The current implementation is **in-process and synchronous**: the
client holds a direct reference to the server. Future versions can
layer a real transport on top without changing the contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.exceptions import (
    MCPConnectionError,
    MCPHandshakeError,
)
from atlas.mcp.models import (
    MCPClient,
    MCPRequest,
    MCPResponse,
    MCPStatus,
)
from atlas.mcp.protocol import (
    LATEST_VERSION,
    HandshakeRequest,
    HandshakeResponse,
)


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class MCPClientInstance:
    """A client that talks to an MCP server.

    Parameters:
        name: Client name.
        server: The :class:`~atlas.mcp.server.MCPServerInstance` to talk to.
        client_versions: Protocol versions the client supports.
        permissions: Permissions the client holds.
    """

    def __init__(
        self,
        name: str,
        server: Any,
        client_versions: tuple[str, ...] = (LATEST_VERSION.value,),
        permissions: tuple[str, ...] = (),
    ) -> None:
        self.descriptor = MCPClient(
            name=name,
            status=MCPStatus.DISCONNECTED,
            permissions=permissions,
        )
        self._server = server
        self._client_versions = client_versions
        self._handshake_response: HandshakeResponse | None = None
        self._request_count: int = 0
        self._error_count: int = 0
        self.logger = get_logger(f"mcp.client.{name}")

    @property
    def name(self) -> str:
        """Return the client name."""
        return self.descriptor.name

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the client is connected to its server."""
        return self.descriptor.status is MCPStatus.CONNECTED

    @property
    def request_count(self) -> int:
        """Return the total number of requests sent."""
        return self._request_count

    def connect(self, capabilities: list[str] | None = None) -> HandshakeResponse:
        """Perform a handshake with the server.

        Raises:
            MCPConnectionError: If the server is not running.
            MCPHandshakeError: If the handshake fails.
        """
        if self._server is None:
            raise MCPConnectionError("no server configured", connector=self.name)
        if not getattr(self._server, "is_running", False):
            raise MCPConnectionError(
                f"server {self._server.name!r} is not running",
                connector=self.name,
            )
        request = HandshakeRequest(
            client_id=self.descriptor.id,
            client_name=self.name,
            client_versions=self._client_versions,
            capabilities=tuple(capabilities or ()),
        )
        try:
            response = self._server.handshake(request)
        except MCPHandshakeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MCPConnectionError(
                f"handshake failed: {exc}", connector=self.name
            ) from exc
        if not response.success:
            raise MCPHandshakeError(
                response.error or "handshake failed", connector=self.name
            )
        self._handshake_response = response
        import dataclasses

        self.descriptor = dataclasses.replace(
            self.descriptor,
            status=MCPStatus.CONNECTED,
            server_id=response.server_id,
            last_active_at=_utcnow(),
        )
        self.logger.info(
            "Client %s connected to server %s (version=%s)",
            self.name,
            self._server.name,
            response.agreed_version,
        )
        return response

    def disconnect(self) -> None:
        """Disconnect from the server."""
        import dataclasses

        self.descriptor = dataclasses.replace(
            self.descriptor, status=MCPStatus.DISCONNECTED
        )
        self._handshake_response = None
        self.logger.info("Client %s disconnected", self.name)

    def send(self, request: MCPRequest) -> MCPResponse:
        """Send ``request`` to the server and return the response.

        Raises:
            MCPConnectionError: If the client is not connected.
        """
        if not self.is_connected:
            raise MCPConnectionError(
                f"client {self.name!r} is not connected",
                connector=self.name,
            )
        self._request_count += 1
        try:
            response = self._server.handle(request)
        except Exception as exc:  # noqa: BLE001
            self._error_count += 1
            raise MCPConnectionError(
                f"send failed: {exc}", connector=self.name
            ) from exc
        if not response.success:
            self._error_count += 1
        return response

    def call(
        self,
        capability: str,
        params: dict[str, Any] | None = None,
    ) -> MCPResponse:
        """Convenience wrapper for :meth:`send` that builds the request."""
        request = MCPRequest(
            connector=self._server.name if self._server else "",
            capability=capability,
            params=dict(params or {}),
        )
        return self.send(request)

    @property
    def handshake(self) -> HandshakeResponse | None:
        """Return the handshake response (``None`` if not connected)."""
        return self._handshake_response

    def __repr__(self) -> str:
        return (
            f"<MCPClientInstance name={self.name!r} "
            f"connected={self.is_connected} requests={self._request_count}>"
        )


__all__ = ["MCPClientInstance"]
