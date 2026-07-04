"""The Atlas MCP Layer.

The MCP (Model Context Protocol) Layer is the universal communication
backbone of the Atlas AI Operating System. It exposes a single,
capability-based API through which Atlas can talk to filesystems,
browsers, GitHub, Blender, Ollama, Windows, OpenRouter, Surpac,
AutoCAD, QGIS, Photoshop, Canva, Google Forms, Excel, Word, and
PowerPoint — and any future connector — without changing the
architecture.

The layer is **personal** (one operator), **offline-first** (every
default is deterministic), **provider-agnostic**, **tool-agnostic**,
**agent-agnostic**, **workflow-agnostic**, and **runtime-agnostic**.
Every concrete concern is dependency-injected.

Dependency graph (acyclic):

* ``exceptions`` — leaf (exception hierarchy).
* ``models`` — leaf (frozen dataclasses + enums).
* ``protocol`` — leaf (handshake, versioning, capability negotiation).
* ``permissions`` — leaf (permission levels + validator).
* ``base`` — depends on ``models``, ``exceptions``, ``permissions``.
* ``transport`` — depends on ``models``, ``exceptions``.
* ``registry`` — depends on ``base``, ``models``, ``exceptions``.
* ``session`` — depends on ``models``, ``exceptions``.
* ``heartbeat`` — depends on ``models``, ``registry``.
* ``health`` — depends on ``models``, ``registry``.
* ``discovery`` — depends on ``base``, ``models``, ``exceptions``.
* ``router`` — depends on ``registry``, ``models``, ``exceptions``.
* ``manager`` — depends on ``registry``, ``session``, ``router``,
  ``health``, ``heartbeat``, ``permissions``, ``models``, ``exceptions``.
* ``server`` — depends on ``models``, ``protocol``, ``exceptions``.
* ``client`` — depends on ``models``, ``protocol``, ``exceptions``.
* ``connectors/*`` — depend on ``base``, ``models``, ``permissions``.
"""

from __future__ import annotations

from atlas.mcp.base import BaseConnector, PlaceholderConnector
from atlas.mcp.client import MCPClientInstance
from atlas.mcp.connectors import (
    ALL_CONNECTORS,
    AutoCADConnector,
    BlenderConnector,
    BrowserConnector,
    CanvaConnector,
    ExcelConnector,
    FilesystemConnector,
    GitHubConnector,
    GoogleFormsConnector,
    OllamaConnector,
    OpenRouterConnector,
    PhotoshopConnector,
    PlaywrightConnector,
    PowerPointConnector,
    QGISConnector,
    SurpacConnector,
    WindowsConnector,
    WordConnector,
    all_connector_classes,
    connector_class_for,
    instantiate_all,
)
from atlas.mcp.discovery import ConnectorDescriptor, ConnectorDiscovery
from atlas.mcp.exceptions import (
    MCPCapabilityError,
    MCPConnectionError,
    MCPDiscoveryError,
    MCPError,
    MCPExecutionError,
    MCPHandshakeError,
    MCPNotFoundError,
    MCPPermissionError,
    MCPProtocolError,
    MCPRegistryError,
    MCPSessionError,
    MCPTimeoutError,
    MCPTransportError,
    is_mcp_error,
)
from atlas.mcp.health import MCPHealthMonitor
from atlas.mcp.heartbeat import HeartbeatMonitor, HeartbeatSample
from atlas.mcp.manager import MCPManager
from atlas.mcp.models import (
    OFFLINE_TRANSPORTS,
    HealthLevel,
    MCPCapability,
    MCPClient,
    MCPConnection,
    MCPHealth,
    MCPMetrics,
    MCPPermission,
    MCPRequest,
    MCPResponse,
    MCPServer,
    MCPSession,
    MCPStatistics,
    MCPStatus,
    MCPTransport,
    TransportKind,
)
from atlas.mcp.permissions import (
    BUILTIN_PERMISSIONS,
    PermissionGrant,
    PermissionLevel,
    PermissionRegistry,
    PermissionValidator,
)
from atlas.mcp.protocol import (
    LATEST_VERSION,
    SUPPORTED_VERSIONS,
    CapabilityNegotiation,
    HandshakeRequest,
    HandshakeResponse,
    ProtocolVersion,
    check_compatibility,
    is_supported,
    negotiate_capabilities,
    negotiate_version,
    perform_handshake,
)
from atlas.mcp.registry import MCPRegistry
from atlas.mcp.router import MCPRouter
from atlas.mcp.server import MCPServerInstance
from atlas.mcp.session import SessionManager
from atlas.mcp.transport import (
    BaseTransport,
    HTTPTransport,
    InProcessTransport,
    NamedPipeTransport,
    StdioTransport,
    WebSocketTransport,
    create_transport,
    supported_kinds,
)

__all__ = [
    "ALL_CONNECTORS",
    "AutoCADConnector",
    "BaseConnector",
    "BaseTransport",
    "BUILTIN_PERMISSIONS",
    "BrowserConnector",
    "BlenderConnector",
    "CanvaConnector",
    "CapabilityNegotiation",
    "ConnectorDescriptor",
    "ConnectorDiscovery",
    "ExcelConnector",
    "FilesystemConnector",
    "GitHubConnector",
    "GoogleFormsConnector",
    "HandshakeRequest",
    "HandshakeResponse",
    "HeartbeatMonitor",
    "HeartbeatSample",
    "HTTPTransport",
    "HealthLevel",
    "InProcessTransport",
    "LATEST_VERSION",
    "MCPCapability",
    "MCPCapabilityError",
    "MCPClient",
    "MCPClientInstance",
    "MCPConnection",
    "MCPConnectionError",
    "MCPDiscoveryError",
    "MCPError",
    "MCPExecutionError",
    "MCPHandshakeError",
    "MCPHealth",
    "MCPHealthMonitor",
    "MCPManager",
    "MCPMetrics",
    "MCPNotFoundError",
    "MCPPermission",
    "MCPPermissionError",
    "MCPProtocolError",
    "MCPRegistry",
    "MCPRegistryError",
    "MCPRequest",
    "MCPResponse",
    "MCPRouter",
    "MCPServer",
    "MCPServerInstance",
    "MCPSession",
    "MCPSessionError",
    "MCPStatistics",
    "MCPStatus",
    "MCPTimeoutError",
    "MCPTransport",
    "MCPTransportError",
    "NamedPipeTransport",
    "OllamaConnector",
    "OpenRouterConnector",
    "OFFLINE_TRANSPORTS",
    "PermissionGrant",
    "PermissionLevel",
    "PermissionRegistry",
    "PermissionValidator",
    "PhotoshopConnector",
    "PlaceholderConnector",
    "PlaywrightConnector",
    "PowerPointConnector",
    "ProtocolVersion",
    "QGISConnector",
    "SUPPORTED_VERSIONS",
    "SessionManager",
    "StdioTransport",
    "SurpacConnector",
    "TransportKind",
    "WebSocketTransport",
    "WindowsConnector",
    "WordConnector",
    "all_connector_classes",
    "check_compatibility",
    "connector_class_for",
    "create_transport",
    "instantiate_all",
    "is_mcp_error",
    "is_supported",
    "negotiate_capabilities",
    "negotiate_version",
    "perform_handshake",
    "supported_kinds",
]
