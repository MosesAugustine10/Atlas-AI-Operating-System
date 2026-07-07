"""Custom exception hierarchy for the Atlas MCP Layer.

This module is a *leaf* in the MCP package dependency graph: it depends
only on the standard library. Every MCP-specific exception inherits
from :class:`MCPError` so callers can catch the entire family with a
single ``except MCPError`` clause.
"""

from __future__ import annotations

from typing import Any


class MCPError(RuntimeError):
    """Base exception for every MCP-layer failure.

    Attributes:
        connector: Optional name of the connector that raised the error.
        detail: Optional machine-readable detail string.
    """

    def __init__(
        self,
        message: str = "",
        *,
        connector: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.connector = connector
        self.detail = detail

    def __str__(self) -> str:
        parts: list[str] = []
        if self.connector:
            parts.append(f"[{self.connector}]")
        if self.message:
            parts.append(self.message)
        if self.detail:
            parts.append(f"({self.detail})")
        return " ".join(parts) if parts else self.__class__.__name__


class MCPConnectionError(MCPError):
    """Raised when a connector cannot establish or maintain a connection."""


class MCPCapabilityError(MCPError):
    """Raised when a requested capability is not supported.

    Attributes:
        capability: The capability that was requested but not found.
    """

    def __init__(
        self,
        message: str = "capability not supported",
        *,
        capability: str | None = None,
        connector: str | None = None,
    ) -> None:
        super().__init__(message, connector=connector, detail=capability)
        self.capability = capability


class MCPPermissionError(MCPError):
    """Raised when a request lacks the required permissions.

    Attributes:
        required: The permission level that was required.
        actual: The permission level that was held.
    """

    def __init__(
        self,
        message: str = "permission denied",
        *,
        required: str | None = None,
        actual: str | None = None,
        connector: str | None = None,
    ) -> None:
        super().__init__(
            message,
            connector=connector,
            detail=f"required={required} actual={actual}",
        )
        self.required = required
        self.actual = actual


class MCPTimeoutError(MCPError):
    """Raised when an operation exceeds its timeout.

    Attributes:
        timeout_seconds: The timeout that was exceeded.
    """

    def __init__(
        self,
        message: str = "operation timed out",
        *,
        timeout_seconds: float | None = None,
        connector: str | None = None,
    ) -> None:
        super().__init__(
            message,
            connector=connector,
            detail=f"timeout={timeout_seconds}s" if timeout_seconds else None,
        )
        self.timeout_seconds = timeout_seconds


class MCPTransportError(MCPError):
    """Raised when a transport-level failure occurs.

    Attributes:
        transport: The transport kind that failed.
    """

    def __init__(
        self,
        message: str = "transport error",
        *,
        transport: str | None = None,
        connector: str | None = None,
    ) -> None:
        super().__init__(message, connector=connector, detail=transport)
        self.transport = transport


class MCPExecutionError(MCPError):
    """Raised when a connector fails to execute a request.

    Attributes:
        request_id: The id of the request that failed.
    """

    def __init__(
        self,
        message: str = "execution failed",
        *,
        request_id: str | None = None,
        connector: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, connector=connector, detail=request_id)
        self.request_id = request_id
        self.cause = cause


class MCPHandshakeError(MCPError):
    """Raised when protocol handshake fails."""


class MCPProtocolError(MCPError):
    """Raised when a protocol-level violation occurs.

    Attributes:
        version: The protocol version that caused the violation.
    """

    def __init__(
        self,
        message: str = "protocol error",
        *,
        version: str | None = None,
        connector: str | None = None,
    ) -> None:
        super().__init__(message, connector=connector, detail=version)
        self.version = version


class MCPRegistryError(MCPError):
    """Raised when a registry operation fails (e.g. duplicate registration)."""


class MCPNotFoundError(MCPError):
    """Raised when a referenced connector or session is not found.

    Attributes:
        resource: The name/id of the missing resource.
    """

    def __init__(
        self,
        message: str = "not found",
        *,
        resource: str | None = None,
    ) -> None:
        super().__init__(message, detail=resource)
        self.resource = resource


class MCPSessionError(MCPError):
    """Raised when a session-level operation fails."""


class MCPDiscoveryError(MCPError):
    """Raised when connector discovery fails."""


def is_mcp_error(exc: Any) -> bool:
    """Return ``True`` if ``exc`` is an :class:`MCPError` instance."""
    return isinstance(exc, MCPError)


__all__ = [
    "MCPCapabilityError",
    "MCPConnectionError",
    "MCPDiscoveryError",
    "MCPError",
    "MCPExecutionError",
    "MCPHandshakeError",
    "MCPNotFoundError",
    "MCPPermissionError",
    "MCPProtocolError",
    "MCPRegistryError",
    "MCPSessionError",
    "MCPTimeoutError",
    "MCPTransportError",
    "is_mcp_error",
]
