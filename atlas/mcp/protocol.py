"""MCP protocol contracts — versioning, handshake, capabilities negotiation.

This module is a *leaf* in the MCP package dependency graph: it depends
only on the standard library. It defines the protocol-level contracts
that connectors, servers, and clients use to agree on capabilities,
versions, and authentication.

The current implementation is a **deterministic placeholder**: every
contract is in-memory and synchronous. Future protocol evolution (real
network handshakes, OAuth, JWT) can be layered on top without changing
these contracts.
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


def _new_id(prefix: str = "hs") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------


class ProtocolVersion(enum.StrEnum):
    """Supported MCP protocol versions.

    Attributes:
        V1_0: The initial MCP protocol version.
        V1_1: Minor revision (extended capability negotiation).
    """

    V1_0 = "1.0"
    V1_1 = "1.1"


#: The latest protocol version this implementation supports.
LATEST_VERSION: ProtocolVersion = ProtocolVersion.V1_1

#: Every version this implementation can speak.
SUPPORTED_VERSIONS: frozenset[ProtocolVersion] = frozenset(
    {ProtocolVersion.V1_0, ProtocolVersion.V1_1}
)


def is_supported(version: str | ProtocolVersion) -> bool:
    """Return ``True`` if ``version`` is a supported protocol version."""
    try:
        return ProtocolVersion(version) in SUPPORTED_VERSIONS
    except ValueError:
        return False


def negotiate_version(
    client_versions: list[str | ProtocolVersion],
    server_versions: list[str | ProtocolVersion] | None = None,
) -> ProtocolVersion | None:
    """Negotiate the highest mutually-supported protocol version.

    Args:
        client_versions: Versions the client can speak.
        server_versions: Versions the server can speak. Defaults to
            :data:`SUPPORTED_VERSIONS`.

    Returns:
        The highest version both sides support, or ``None`` if there is
        no overlap.
    """
    server = (
        {ProtocolVersion(v) for v in server_versions if is_supported(v)}
        if server_versions is not None
        else set(SUPPORTED_VERSIONS)
    )
    client = {ProtocolVersion(v) for v in client_versions if is_supported(v)}
    common = client & server
    if not common:
        return None
    # Pick the highest version (string compare works for "1.0" < "1.1").
    return max(common, key=lambda v: v.value)


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandshakeRequest:
    """A client's handshake request.

    Attributes:
        client_id: Unique client identifier.
        client_name: Human-readable client name.
        client_versions: Protocol versions the client supports.
        capabilities: Capabilities the client wants to use.
        auth_token: Optional authentication token (placeholder).
        created_at: When the request was created.
        metadata: Free-form metadata.
    """

    client_id: str = field(default_factory=lambda: _new_id("client"))
    client_name: str = ""
    client_versions: tuple[str, ...] = (LATEST_VERSION.value,)
    capabilities: tuple[str, ...] = ()
    auth_token: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HandshakeResponse:
    """A server's handshake response.

    Attributes:
        server_id: Unique server identifier.
        server_name: Human-readable server name.
        server_versions: Protocol versions the server supports.
        agreed_version: The version both sides agreed on (``None`` if
            negotiation failed).
        capabilities: Capabilities the server actually grants.
        auth_required: Whether authentication is required for further
            requests.
        session_id: Optional session identifier established by the
            handshake.
        success: Whether the handshake succeeded.
        error: Error message if ``success`` is ``False``.
        created_at: When the response was produced.
        metadata: Free-form metadata.
    """

    server_id: str = field(default_factory=lambda: _new_id("server"))
    server_name: str = ""
    server_versions: tuple[str, ...] = (LATEST_VERSION.value,)
    agreed_version: str | None = None
    capabilities: tuple[str, ...] = ()
    auth_required: bool = False
    session_id: str | None = None
    success: bool = True
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


def perform_handshake(
    request: HandshakeRequest,
    server_name: str = "atlas-mcp-server",
    server_capabilities: tuple[str, ...] = (),
    server_versions: list[str | ProtocolVersion] | None = None,
    auth_required: bool = False,
) -> HandshakeResponse:
    """Perform a deterministic placeholder handshake.

    The current implementation:
    1. Negotiates the highest mutually-supported protocol version.
    2. Intersects the requested capabilities with the server's.
    3. Returns a :class:`HandshakeResponse` with the results.

    No real authentication is performed — ``auth_token`` is accepted
    but never validated. Future versions can layer real auth on top.
    """
    agreed = negotiate_version(list(request.client_versions), server_versions)
    if agreed is None:
        return HandshakeResponse(
            server_name=server_name,
            agreed_version=None,
            success=False,
            error="no overlapping protocol version",
        )
    granted = (
        tuple(cap for cap in request.capabilities if cap in server_capabilities)
        if server_capabilities
        else tuple(request.capabilities)
    )
    return HandshakeResponse(
        server_name=server_name,
        server_versions=tuple(
            v.value if isinstance(v, ProtocolVersion) else v
            for v in (server_versions or list(SUPPORTED_VERSIONS))
        ),
        agreed_version=agreed.value,
        capabilities=granted,
        auth_required=auth_required,
        session_id=_new_id("session"),
        success=True,
    )


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Heartbeat:
    """A single heartbeat signal.

    Attributes:
        source: Who sent the heartbeat (connector name).
        sequence: Monotonically increasing sequence number.
        timestamp: When the heartbeat was sent.
        latency_ms: Measured round-trip latency (``None`` if not yet
            measured).
        status: ``"ok"`` or ``"degraded"``.
        metadata: Free-form metadata.
    """

    source: str
    sequence: int = 0
    timestamp: datetime = field(default_factory=_utcnow)
    latency_ms: float | None = None
    status: str = "ok"
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Capability negotiation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityNegotiation:
    """The result of capability negotiation.

    Attributes:
        requested: Capabilities the client asked for.
        available: Capabilities the server has.
        granted: Capabilities the server actually granted (intersection).
        denied: Capabilities the server refused.
        reason: Human-readable explanation.
    """

    requested: tuple[str, ...] = ()
    available: tuple[str, ...] = ()
    granted: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    reason: str = ""


def negotiate_capabilities(
    requested: list[str],
    available: list[str],
    permissions: list[str] | None = None,
) -> CapabilityNegotiation:
    """Negotiate capabilities between a client and a server.

    Args:
        requested: Capabilities the client wants.
        available: Capabilities the server has.
        permissions: Optional permission filter. If supplied, only
            capabilities whose required permission is in this list are
            granted. (The placeholder implementation does not enforce
            permissions; this is a hook for future use.)

    Returns:
        A :class:`CapabilityNegotiation` with the granted / denied sets.
    """
    requested_set = set(requested)
    available_set = set(available)
    granted = requested_set & available_set
    denied = requested_set - granted
    if permissions is not None:
        # Future: filter by per-capability required permission.
        pass
    return CapabilityNegotiation(
        requested=tuple(requested),
        available=tuple(available),
        granted=tuple(sorted(granted)),
        denied=tuple(sorted(denied)),
        reason=f"granted {len(granted)} of {len(requested_set)} requested",
    )


# ---------------------------------------------------------------------------
# Compatibility checks
# ---------------------------------------------------------------------------


def check_compatibility(
    client_versions: list[str | ProtocolVersion],
    required_capabilities: list[str],
    server_versions: list[str | ProtocolVersion] | None = None,
    server_capabilities: list[str] | None = None,
) -> tuple[bool, str]:
    """Check whether a client is compatible with a server.

    Returns a ``(compatible, reason)`` tuple. Compatible only if a
    protocol version overlaps AND every required capability is granted.
    """
    agreed = negotiate_version(client_versions, server_versions)
    if agreed is None:
        return False, "no overlapping protocol version"
    if required_capabilities:
        available = server_capabilities or []
        missing = [c for c in required_capabilities if c not in available]
        if missing:
            return False, f"missing capabilities: {missing}"
    return True, f"compatible (version={agreed.value})"


__all__ = [
    "CapabilityNegotiation",
    "HandshakeRequest",
    "HandshakeResponse",
    "Heartbeat",
    "LATEST_VERSION",
    "ProtocolVersion",
    "SUPPORTED_VERSIONS",
    "check_compatibility",
    "is_supported",
    "negotiate_capabilities",
    "negotiate_version",
    "perform_handshake",
]
