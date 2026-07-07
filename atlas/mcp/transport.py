"""Transport abstraction for the Atlas MCP Layer.

This module defines the abstract :class:`BaseTransport` contract and a
set of deterministic placeholder transports. No real networking is
performed — every transport is in-process and synchronous. The
abstraction exists so that future real transports (stdio subprocesses,
HTTP clients, WebSocket clients, named pipes) can be slotted in
without changing the connector contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.exceptions import MCPTransportError
from atlas.mcp.models import MCPRequest, MCPResponse, MCPTransport, TransportKind


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class BaseTransport(ABC):
    """Abstract contract for MCP transports.

    A transport is responsible for carrying :class:`MCPRequest` objects
    to a connector backend and returning :class:`MCPResponse` objects.
    Transports never interpret request content — they are pure pipes.

    Parameters:
        config: The :class:`MCPTransport` configuration.
    """

    kind: TransportKind = TransportKind.IN_PROCESS

    def __init__(self, config: MCPTransport | None = None) -> None:
        self.config = config if config is not None else MCPTransport(kind=self.kind)
        self._connected: bool = False
        self._logger = get_logger(f"mcp.transport.{self.kind.value}")

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the transport is open."""
        return self._connected

    def open(self) -> None:
        """Open the transport for sending."""
        if self._connected:
            return
        try:
            self._do_open()
        except Exception as exc:  # noqa: BLE001
            raise MCPTransportError(
                f"failed to open {self.kind.value} transport: {exc}",
                transport=self.kind.value,
            ) from exc
        self._connected = True

    def close(self) -> None:
        """Close the transport."""
        if not self._connected:
            return
        try:
            self._do_close()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Error closing %s transport: %s", self.kind.value, exc)
        self._connected = False

    def send(self, request: MCPRequest) -> MCPResponse:
        """Send ``request`` and return the :class:`MCPResponse`."""
        if not self._connected:
            self.open()
        try:
            return self._do_send(request)
        except Exception as exc:  # noqa: BLE001
            raise MCPTransportError(
                f"send failed on {self.kind.value} transport: {exc}",
                transport=self.kind.value,
            ) from exc

    @abstractmethod
    def _do_open(self) -> None:
        """Actually open the transport."""

    @abstractmethod
    def _do_close(self) -> None:
        """Actually close the transport."""

    @abstractmethod
    def _do_send(self, request: MCPRequest) -> MCPResponse:
        """Actually send ``request`` and return the response."""

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} kind={self.kind.value} "
            f"connected={self._connected}>"
        )


# ---------------------------------------------------------------------------
# Placeholder transports
# ---------------------------------------------------------------------------


class InProcessTransport(BaseTransport):
    """In-process transport — calls a handler callable directly.

    Parameters:
        handler: A callable ``(MCPRequest) -> MCPResponse`` that
            simulates the connector backend.
        config: Transport configuration (ignored for in-process).
    """

    kind = TransportKind.IN_PROCESS

    def __init__(
        self,
        handler: Any = None,
        config: MCPTransport | None = None,
    ) -> None:
        super().__init__(config=config)
        self._handler = handler

    def set_handler(self, handler: Any) -> None:
        """Set the callable that simulates the connector backend."""
        self._handler = handler

    def _do_open(self) -> None:
        return None

    def _do_close(self) -> None:
        return None

    def _do_send(self, request: MCPRequest) -> MCPResponse:
        if self._handler is None:
            return MCPResponse(
                request_id=request.id,
                success=False,
                error="no handler configured",
            )
        if callable(self._handler):
            return self._handler(request)
        return MCPResponse(
            request_id=request.id,
            success=False,
            error="handler is not callable",
        )


class StdioTransport(BaseTransport):
    """Placeholder stdio transport.

    A real implementation would spawn a subprocess and communicate over
    stdin/stdout. The placeholder records sent requests and returns
    deterministic responses.
    """

    kind = TransportKind.STDIO

    def __init__(self, config: MCPTransport | None = None) -> None:
        super().__init__(config=config)
        self._sent: list[MCPRequest] = []

    def _do_open(self) -> None:
        return None

    def _do_close(self) -> None:
        return None

    def _do_send(self, request: MCPRequest) -> MCPResponse:
        self._sent.append(request)
        return MCPResponse(
            request_id=request.id,
            success=True,
            output={"echo": request.capability, "transport": "stdio"},
        )

    @property
    def sent_requests(self) -> list[MCPRequest]:
        """Return every request that was sent (for testing)."""
        return list(self._sent)


class HTTPTransport(BaseTransport):
    """Placeholder HTTP transport."""

    kind = TransportKind.HTTP

    def __init__(self, config: MCPTransport | None = None) -> None:
        super().__init__(config=config)
        self._sent: list[MCPRequest] = []

    def _do_open(self) -> None:
        return None

    def _do_close(self) -> None:
        return None

    def _do_send(self, request: MCPRequest) -> MCPResponse:
        self._sent.append(request)
        return MCPResponse(
            request_id=request.id,
            success=True,
            output={"echo": request.capability, "transport": "http"},
        )

    @property
    def sent_requests(self) -> list[MCPRequest]:
        """Return every request that was sent (for testing)."""
        return list(self._sent)


class WebSocketTransport(BaseTransport):
    """Placeholder WebSocket transport."""

    kind = TransportKind.WEBSOCKET

    def __init__(self, config: MCPTransport | None = None) -> None:
        super().__init__(config=config)
        self._sent: list[MCPRequest] = []

    def _do_open(self) -> None:
        return None

    def _do_close(self) -> None:
        return None

    def _do_send(self, request: MCPRequest) -> MCPResponse:
        self._sent.append(request)
        return MCPResponse(
            request_id=request.id,
            success=True,
            output={"echo": request.capability, "transport": "websocket"},
        )

    @property
    def sent_requests(self) -> list[MCPRequest]:
        """Return every request that was sent (for testing)."""
        return list(self._sent)


class NamedPipeTransport(BaseTransport):
    """Placeholder named-pipe transport."""

    kind = TransportKind.NAMED_PIPE

    def __init__(self, config: MCPTransport | None = None) -> None:
        super().__init__(config=config)
        self._sent: list[MCPRequest] = []

    def _do_open(self) -> None:
        return None

    def _do_close(self) -> None:
        return None

    def _do_send(self, request: MCPRequest) -> MCPResponse:
        self._sent.append(request)
        return MCPResponse(
            request_id=request.id,
            success=True,
            output={"echo": request.capability, "transport": "named_pipe"},
        )

    @property
    def sent_requests(self) -> list[MCPRequest]:
        """Return every request that was sent (for testing)."""
        return list(self._sent)


# ---------------------------------------------------------------------------
# Transport factory
# ---------------------------------------------------------------------------


_TRANSPORT_CLASSES: dict[TransportKind, type[BaseTransport]] = {
    TransportKind.IN_PROCESS: InProcessTransport,
    TransportKind.STDIO: StdioTransport,
    TransportKind.HTTP: HTTPTransport,
    TransportKind.WEBSOCKET: WebSocketTransport,
    TransportKind.NAMED_PIPE: NamedPipeTransport,
}


def create_transport(config: MCPTransport) -> BaseTransport:
    """Create a transport instance for ``config``.

    Raises:
        MCPTransportError: If the transport kind is not supported.
    """
    cls = _TRANSPORT_CLASSES.get(config.kind)
    if cls is None:
        raise MCPTransportError(
            f"unsupported transport kind: {config.kind}",
            transport=config.kind.value,
        )
    return cls(config=config)


def supported_kinds() -> list[TransportKind]:
    """Return every supported :class:`TransportKind`."""
    return sorted(_TRANSPORT_CLASSES, key=lambda k: k.value)


__all__ = [
    "BaseTransport",
    "HTTPTransport",
    "InProcessTransport",
    "NamedPipeTransport",
    "StdioTransport",
    "WebSocketTransport",
    "create_transport",
    "supported_kinds",
]
