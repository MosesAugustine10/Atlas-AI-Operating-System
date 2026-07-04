"""Tests for the Atlas MCP Layer.

Covers models, protocol, permissions, base connector, transport,
registry, session, heartbeat, health, discovery, router, manager,
server, client, every connector, and end-to-end flow. All tests are
deterministic and offline — no external APIs are called.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from atlas.mcp import (
    ALL_CONNECTORS,
    BUILTIN_PERMISSIONS,
    LATEST_VERSION,
    OFFLINE_TRANSPORTS,
    SUPPORTED_VERSIONS,
    AutoCADConnector,
    BlenderConnector,
    BrowserConnector,
    CanvaConnector,
    ConnectorDescriptor,
    ConnectorDiscovery,
    ExcelConnector,
    FilesystemConnector,
    GitHubConnector,
    GoogleFormsConnector,
    HandshakeRequest,
    HandshakeResponse,
    HealthLevel,
    HTTPTransport,
    InProcessTransport,
    MCPCapability,
    MCPCapabilityError,
    MCPClient,
    MCPClientInstance,
    MCPConnection,
    MCPConnectionError,
    MCPDiscoveryError,
    MCPError,
    MCPExecutionError,
    MCPHandshakeError,
    MCPHealth,
    MCPHealthMonitor,
    MCPManager,
    MCPMetrics,
    MCPNotFoundError,
    MCPPermission,
    MCPPermissionError,
    MCPProtocolError,
    MCPRegistry,
    MCPRegistryError,
    MCPRequest,
    MCPResponse,
    MCPRouter,
    MCPServer,
    MCPServerInstance,
    MCPSession,
    MCPSessionError,
    MCPStatistics,
    MCPStatus,
    MCPTimeoutError,
    MCPTransport,
    MCPTransportError,
    NamedPipeTransport,
    OllamaConnector,
    OpenRouterConnector,
    PermissionGrant,
    PermissionLevel,
    PermissionRegistry,
    PermissionValidator,
    PhotoshopConnector,
    PlaceholderConnector,
    PlaywrightConnector,
    PowerPointConnector,
    ProtocolVersion,
    QGISConnector,
    SessionManager,
    StdioTransport,
    SurpacConnector,
    TransportKind,
    WebSocketTransport,
    WindowsConnector,
    WordConnector,
    all_connector_classes,
    check_compatibility,
    connector_class_for,
    create_transport,
    instantiate_all,
    is_mcp_error,
    is_supported,
    negotiate_capabilities,
    negotiate_version,
    perform_handshake,
    supported_kinds,
)
from atlas.mcp.heartbeat import HeartbeatMonitor, HeartbeatSample

# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    def test_mcp_status_has_seven_values(self) -> None:
        assert len(list(MCPStatus)) == 7

    def test_health_level_has_five_values(self) -> None:
        assert len(list(HealthLevel)) == 5

    def test_transport_kind_has_five_values(self) -> None:
        assert len(list(TransportKind)) == 5

    def test_offline_transports_contains_in_process_and_stdio(self) -> None:
        assert TransportKind.IN_PROCESS in OFFLINE_TRANSPORTS
        assert TransportKind.STDIO in OFFLINE_TRANSPORTS

    def test_mcp_capability_is_frozen(self) -> None:
        cap = MCPCapability(name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cap.name = "other"  # type: ignore[misc]

    def test_mcp_capability_defaults(self) -> None:
        cap = MCPCapability(name="test")
        assert cap.description == ""
        assert cap.permissions == ()
        assert cap.metadata == {}

    def test_mcp_permission_is_frozen(self) -> None:
        perm = MCPPermission(name="read", level=10)
        with pytest.raises(dataclasses.FrozenInstanceError):
            perm.name = "write"  # type: ignore[misc]

    def test_mcp_transport_is_frozen(self) -> None:
        t = MCPTransport()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.kind = TransportKind.HTTP  # type: ignore[misc]

    def test_mcp_transport_defaults(self) -> None:
        t = MCPTransport()
        assert t.kind is TransportKind.IN_PROCESS
        assert t.address == ""
        assert t.options == {}

    def test_mcp_health_is_frozen(self) -> None:
        h = MCPHealth(connector="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            h.connector = "other"  # type: ignore[misc]

    def test_mcp_connection_is_frozen(self) -> None:
        c = MCPConnection(connector="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.connector = "other"  # type: ignore[misc]

    def test_mcp_request_is_frozen(self) -> None:
        r = MCPRequest(connector="test", capability="cap")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.connector = "other"  # type: ignore[misc]

    def test_mcp_request_defaults(self) -> None:
        r = MCPRequest()
        assert r.permission == "read"
        assert r.timeout_seconds == 30.0
        assert r.params == {}

    def test_mcp_response_is_frozen(self) -> None:
        r = MCPResponse(request_id="r1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.success = False  # type: ignore[misc]

    def test_mcp_session_is_frozen(self) -> None:
        s = MCPSession(connector="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.connector = "other"  # type: ignore[misc]

    def test_mcp_session_is_open(self) -> None:
        s = MCPSession(connector="test", status=MCPStatus.CONNECTED)
        assert s.is_open() is True
        s2 = MCPSession(connector="test", status=MCPStatus.DISCONNECTED)
        assert s2.is_open() is False

    def test_mcp_server_is_frozen(self) -> None:
        s = MCPServer(name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.name = "other"  # type: ignore[misc]

    def test_mcp_client_is_frozen(self) -> None:
        c = MCPClient(name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.name = "other"  # type: ignore[misc]

    def test_mcp_metrics_is_frozen(self) -> None:
        m = MCPMetrics(connector="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.connector = "other"  # type: ignore[misc]

    def test_mcp_statistics_is_frozen(self) -> None:
        s = MCPStatistics()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.connectors_total = 99  # type: ignore[misc]


# ===========================================================================
# Protocol
# ===========================================================================


class TestProtocol:
    def test_protocol_version_has_two_values(self) -> None:
        assert len(list(ProtocolVersion)) == 2

    def test_latest_version_is_v1_1(self) -> None:
        assert LATEST_VERSION is ProtocolVersion.V1_1

    def test_supported_versions_contains_both(self) -> None:
        assert ProtocolVersion.V1_0 in SUPPORTED_VERSIONS
        assert ProtocolVersion.V1_1 in SUPPORTED_VERSIONS

    def test_is_supported_known_version(self) -> None:
        assert is_supported("1.0") is True
        assert is_supported("1.1") is True

    def test_is_supported_unknown_version(self) -> None:
        assert is_supported("2.0") is False
        assert is_supported("bogus") is False

    def test_negotiate_version_overlap(self) -> None:
        result = negotiate_version(["1.0", "1.1"], ["1.1"])
        assert result is ProtocolVersion.V1_1

    def test_negotiate_version_no_overlap(self) -> None:
        result = negotiate_version(["1.0"], ["1.1"])
        assert result is None

    def test_negotiate_version_defaults_to_supported(self) -> None:
        result = negotiate_version(["1.0", "1.1"])
        assert result is ProtocolVersion.V1_1

    def test_handshake_request_defaults(self) -> None:
        req = HandshakeRequest()
        assert req.client_versions == (LATEST_VERSION.value,)
        assert req.auth_token is None

    def test_handshake_response_defaults(self) -> None:
        resp = HandshakeResponse()
        assert resp.success is True
        assert resp.error is None

    def test_perform_handshake_success(self) -> None:
        req = HandshakeRequest(
            client_versions=("1.1",),
            capabilities=("file.read",),
        )
        resp = perform_handshake(
            req,
            server_capabilities=("file.read", "file.write"),
        )
        assert resp.success is True
        assert resp.agreed_version == "1.1"
        assert "file.read" in resp.capabilities

    def test_perform_handshake_version_mismatch(self) -> None:
        req = HandshakeRequest(client_versions=("2.0",))
        resp = perform_handshake(req)
        assert resp.success is False
        assert "no overlapping" in (resp.error or "")

    def test_perform_handshake_capability_intersection(self) -> None:
        req = HandshakeRequest(
            client_versions=("1.1",),
            capabilities=("file.read", "file.delete"),
        )
        resp = perform_handshake(
            req,
            server_capabilities=("file.read", "file.write"),
        )
        assert resp.capabilities == ("file.read",)

    def test_negotiate_capabilities_grants_intersection(self) -> None:
        result = negotiate_capabilities(
            requested=["file.read", "file.write"],
            available=["file.read", "file.execute"],
        )
        assert "file.read" in result.granted
        assert "file.write" in result.denied

    def test_negotiate_capabilities_empty_request(self) -> None:
        result = negotiate_capabilities(requested=[], available=["file.read"])
        assert result.granted == ()

    def test_check_compatibility_success(self) -> None:
        ok, reason = check_compatibility(
            client_versions=["1.1"],
            required_capabilities=["file.read"],
            server_capabilities=["file.read"],
        )
        assert ok is True
        assert "compatible" in reason

    def test_check_compatibility_version_mismatch(self) -> None:
        ok, reason = check_compatibility(
            client_versions=["2.0"],
            required_capabilities=[],
        )
        assert ok is False
        assert "version" in reason

    def test_check_compatibility_missing_capability(self) -> None:
        ok, reason = check_compatibility(
            client_versions=["1.1"],
            required_capabilities=["file.delete"],
            server_capabilities=["file.read"],
        )
        assert ok is False
        assert "missing" in reason


# ===========================================================================
# Permissions
# ===========================================================================


class TestPermissions:
    def test_permission_level_ordering(self) -> None:
        assert PermissionLevel.ADMIN > PermissionLevel.EXECUTE
        assert PermissionLevel.EXECUTE > PermissionLevel.WRITE
        assert PermissionLevel.WRITE > PermissionLevel.READ
        assert PermissionLevel.READ > PermissionLevel.NONE

    def test_builtin_permissions_has_five(self) -> None:
        assert len(BUILTIN_PERMISSIONS) == 5

    def test_permission_registry_defaults(self) -> None:
        reg = PermissionRegistry()
        assert reg.contains("read")
        assert reg.contains("write")
        assert reg.contains("execute")
        assert reg.contains("admin")
        assert reg.contains("none")

    def test_permission_registry_register_custom(self) -> None:
        reg = PermissionRegistry()
        reg.register("custom.git.push", 50)
        assert reg.contains("custom.git.push")
        assert reg.get("custom.git.push") == 50

    def test_permission_registry_unregister_custom(self) -> None:
        reg = PermissionRegistry()
        reg.register("custom", 50)
        assert reg.unregister("custom") is True
        assert reg.unregister("custom") is False

    def test_permission_registry_cannot_unregister_builtin(self) -> None:
        reg = PermissionRegistry()
        assert reg.unregister("read") is False

    def test_permission_registry_register_rejects_empty_name(self) -> None:
        reg = PermissionRegistry()
        with pytest.raises(ValueError):
            reg.register("", 10)

    def test_permission_registry_names_sorted(self) -> None:
        reg = PermissionRegistry()
        reg.register("zebra", 1)
        reg.register("alpha", 1)
        names = reg.names()
        assert names[0] == "admin"
        assert "alpha" in names
        assert "zebra" in names

    def test_permission_registry_contains(self) -> None:
        reg = PermissionRegistry()
        assert "read" in reg
        assert "bogus" not in reg

    def test_permission_registry_len(self) -> None:
        reg = PermissionRegistry()
        assert len(reg) == 5
        reg.register("custom", 10)
        assert len(reg) == 6

    def test_permission_validator_effective_level(self) -> None:
        v = PermissionValidator()
        assert v.effective_level([]) == PermissionLevel.NONE.value
        assert v.effective_level(["read"]) == PermissionLevel.READ.value
        assert v.effective_level(["read", "admin"]) == PermissionLevel.ADMIN.value

    def test_permission_validator_can_with_string(self) -> None:
        v = PermissionValidator()
        assert v.can(["read"], "read") is True
        assert v.can(["read"], "write") is False

    def test_permission_validator_can_with_level(self) -> None:
        v = PermissionValidator()
        assert v.can(["write"], PermissionLevel.READ) is True
        assert v.can(["read"], PermissionLevel.WRITE) is False

    def test_permission_validator_can_with_int(self) -> None:
        v = PermissionValidator()
        assert v.can(["admin"], 50) is True
        assert v.can(["read"], 50) is False

    def test_permission_validator_check_raises(self) -> None:
        v = PermissionValidator()
        with pytest.raises(MCPPermissionError):
            v.check(["read"], "admin")

    def test_permission_validator_check_passes(self) -> None:
        v = PermissionValidator()
        v.check(["admin"], "read")  # should not raise

    def test_permission_grant_is_frozen(self) -> None:
        g = PermissionGrant(name="read", level=10)
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.name = "write"  # type: ignore[misc]


# ===========================================================================
# Exceptions
# ===========================================================================


class TestExceptions:
    def test_mcp_error_is_runtime_error(self) -> None:
        assert issubclass(MCPError, RuntimeError)

    def test_mcp_error_str_includes_connector(self) -> None:
        err = MCPError("boom", connector="fs")
        assert "[fs]" in str(err)
        assert "boom" in str(err)

    def test_mcp_error_str_includes_detail(self) -> None:
        err = MCPError("boom", detail="extra")
        assert "(extra)" in str(err)

    def test_connection_error_is_mcp_error(self) -> None:
        assert issubclass(MCPConnectionError, MCPError)

    def test_capability_error_stores_capability(self) -> None:
        err = MCPCapabilityError(capability="file.read")
        assert err.capability == "file.read"

    def test_permission_error_stores_required_and_actual(self) -> None:
        err = MCPPermissionError(required="admin", actual="read")
        assert err.required == "admin"
        assert err.actual == "read"

    def test_timeout_error_stores_timeout(self) -> None:
        err = MCPTimeoutError(timeout_seconds=5.0)
        assert err.timeout_seconds == 5.0

    def test_transport_error_stores_transport(self) -> None:
        err = MCPTransportError(transport="http")
        assert err.transport == "http"

    def test_execution_error_stores_request_id(self) -> None:
        err = MCPExecutionError(request_id="r123")
        assert err.request_id == "r123"

    def test_is_mcp_error_true_for_subclass(self) -> None:
        assert is_mcp_error(MCPConnectionError()) is True

    def test_is_mcp_error_false_for_plain_exception(self) -> None:
        assert is_mcp_error(ValueError()) is False

    def test_not_found_error_stores_resource(self) -> None:
        err = MCPNotFoundError(resource="connector_x")
        assert err.resource == "connector_x"


# ===========================================================================
# Base connector
# ===========================================================================


class TestBaseConnector:
    def test_placeholder_connector_connect(self) -> None:
        c = PlaceholderConnector()
        assert not c.is_connected
        c.connect()
        assert c.is_connected
        assert c.status is MCPStatus.CONNECTED

    def test_placeholder_connector_disconnect(self) -> None:
        c = PlaceholderConnector()
        c.connect()
        c.disconnect()
        assert not c.is_connected
        assert c.status is MCPStatus.DISCONNECTED

    def test_placeholder_connector_health(self) -> None:
        c = PlaceholderConnector()
        c.connect()
        h = c.health()
        assert h.connector == "placeholder"
        assert h.status is MCPStatus.CONNECTED
        assert h.level is HealthLevel.HEALTHY

    def test_placeholder_connector_capabilities(self) -> None:
        c = PlaceholderConnector()
        caps = c.capabilities()
        assert len(caps) >= 2
        assert any(cap.name == "ping" for cap in caps)

    def test_placeholder_connector_execute_ping(self) -> None:
        c = PlaceholderConnector()
        c.connect()
        req = MCPRequest(connector="placeholder", capability="ping")
        resp = c.execute(req)
        assert resp.success
        assert resp.output == "pong"

    def test_placeholder_connector_execute_echo(self) -> None:
        c = PlaceholderConnector()
        c.connect()
        req = MCPRequest(
            connector="placeholder",
            capability="echo",
            params={"x": 1},
        )
        resp = c.execute(req)
        assert resp.success
        assert resp.output == {"x": 1}

    def test_placeholder_connector_execute_not_connected(self) -> None:
        c = PlaceholderConnector()
        req = MCPRequest(connector="placeholder", capability="ping")
        resp = c.execute(req)
        assert not resp.success
        assert "not connected" in (resp.error or "")

    def test_placeholder_connector_discover(self) -> None:
        c = PlaceholderConnector()
        d = c.discover()
        assert d["name"] == "placeholder"
        assert "capabilities" in d
        assert "supported_transports" in d

    def test_connector_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError):
            PlaceholderConnector(name="")

    def test_connector_connect_is_idempotent(self) -> None:
        c = PlaceholderConnector()
        c.connect()
        c.connect()  # should not raise
        assert c.is_connected

    def test_connector_disconnect_is_idempotent(self) -> None:
        c = PlaceholderConnector()
        c.disconnect()  # should not raise
        assert not c.is_connected

    def test_connector_uptime_seconds(self) -> None:
        c = PlaceholderConnector()
        c.connect()
        assert c.uptime_seconds >= 0.0

    def test_connector_last_error(self) -> None:
        c = PlaceholderConnector()
        assert c.last_error is None


# ===========================================================================
# Transport
# ===========================================================================


class TestTransport:
    def test_in_process_transport_open_close(self) -> None:
        t = InProcessTransport()
        t.open()
        assert t.is_connected
        t.close()
        assert not t.is_connected

    def test_in_process_transport_send_no_handler(self) -> None:
        t = InProcessTransport()
        t.open()
        req = MCPRequest(connector="test", capability="ping")
        resp = t.send(req)
        assert not resp.success

    def test_in_process_transport_send_with_handler(self) -> None:
        def handler(req: MCPRequest) -> MCPResponse:
            return MCPResponse(request_id=req.id, success=True, output="ok")

        t = InProcessTransport(handler=handler)
        t.open()
        req = MCPRequest(connector="test", capability="ping")
        resp = t.send(req)
        assert resp.success
        assert resp.output == "ok"

    def test_stdio_transport_records_sent(self) -> None:
        t = StdioTransport()
        t.open()
        req = MCPRequest(connector="test", capability="ping")
        t.send(req)
        assert len(t.sent_requests) == 1

    def test_http_transport_records_sent(self) -> None:
        t = HTTPTransport()
        t.open()
        req = MCPRequest(connector="test", capability="ping")
        t.send(req)
        assert len(t.sent_requests) == 1

    def test_websocket_transport_records_sent(self) -> None:
        t = WebSocketTransport()
        t.open()
        req = MCPRequest(connector="test", capability="ping")
        t.send(req)
        assert len(t.sent_requests) == 1

    def test_named_pipe_transport_records_sent(self) -> None:
        t = NamedPipeTransport()
        t.open()
        req = MCPRequest(connector="test", capability="ping")
        t.send(req)
        assert len(t.sent_requests) == 1

    def test_create_transport_in_process(self) -> None:
        t = create_transport(MCPTransport(kind=TransportKind.IN_PROCESS))
        assert isinstance(t, InProcessTransport)

    def test_create_transport_http(self) -> None:
        t = create_transport(MCPTransport(kind=TransportKind.HTTP))
        assert isinstance(t, HTTPTransport)

    def test_create_transport_stdio(self) -> None:
        t = create_transport(MCPTransport(kind=TransportKind.STDIO))
        assert isinstance(t, StdioTransport)

    def test_create_transport_websocket(self) -> None:
        t = create_transport(MCPTransport(kind=TransportKind.WEBSOCKET))
        assert isinstance(t, WebSocketTransport)

    def test_create_transport_named_pipe(self) -> None:
        t = create_transport(MCPTransport(kind=TransportKind.NAMED_PIPE))
        assert isinstance(t, NamedPipeTransport)

    def test_supported_kinds_returns_all(self) -> None:
        kinds = supported_kinds()
        assert len(kinds) == 5

    def test_transport_open_is_idempotent(self) -> None:
        t = InProcessTransport()
        t.open()
        t.open()
        assert t.is_connected


# ===========================================================================
# Registry
# ===========================================================================


class TestRegistry:
    def test_registry_register_and_get(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="test")
        reg.register(c)
        assert reg.get("test") is c

    def test_registry_contains(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="test"))
        assert reg.contains("test")
        assert "test" in reg

    def test_registry_register_duplicate_raises(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="test"))
        with pytest.raises(MCPRegistryError):
            reg.register(PlaceholderConnector(name="test"))

    def test_registry_unregister(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="test"))
        assert reg.unregister("test") is True
        assert reg.unregister("test") is False

    def test_registry_get_missing_raises(self) -> None:
        reg = MCPRegistry()
        with pytest.raises(MCPNotFoundError):
            reg.get("missing")

    def test_registry_get_optional_returns_none(self) -> None:
        reg = MCPRegistry()
        assert reg.get_optional("missing") is None

    def test_registry_find_by_capability(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"))
        reg.register(PlaceholderConnector(name="b"))
        results = reg.find_by_capability("ping")
        assert len(results) == 2

    def test_registry_find_with_predicate(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"))
        reg.register(PlaceholderConnector(name="b"))
        results = reg.find(lambda c: c.name == "a")
        assert len(results) == 1

    def test_registry_find_by_tag(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"), tags=["storage"])
        reg.register(PlaceholderConnector(name="b"), tags=["storage"])
        results = reg.find_by_tag("storage")
        assert len(results) == 2

    def test_registry_list_sorted(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="b"))
        reg.register(PlaceholderConnector(name="a"))
        assert [c.name for c in reg.list()] == ["a", "b"]

    def test_registry_names(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"))
        assert reg.names() == ["a"]

    def test_registry_tags(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"), tags=["x"])
        assert "x" in reg.tags()

    def test_registry_all_capabilities(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"))
        caps = reg.all_capabilities()
        assert "a" in caps
        assert "ping" in caps["a"]

    def test_registry_statistics_empty(self) -> None:
        reg = MCPRegistry()
        stats = reg.statistics()
        assert stats.connectors_total == 0
        assert stats.overall_health is HealthLevel.UNKNOWN

    def test_registry_statistics_with_connectors(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        stats = reg.statistics()
        assert stats.connectors_total == 1
        assert stats.connectors_connected == 1
        assert stats.overall_health is HealthLevel.HEALTHY

    def test_registry_len(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"))
        assert len(reg) == 1

    def test_registry_iter(self) -> None:
        reg = MCPRegistry()
        reg.register(PlaceholderConnector(name="a"))
        reg.register(PlaceholderConnector(name="b"))
        names = [c.name for c in reg]
        assert sorted(names) == ["a", "b"]


# ===========================================================================
# Session
# ===========================================================================


class TestSession:
    def test_session_manager_open(self) -> None:
        sm = SessionManager()
        s = sm.open("connector_x")
        assert s.connector == "connector_x"
        assert s.is_open()

    def test_session_manager_close(self) -> None:
        sm = SessionManager()
        s = sm.open("connector_x")
        closed = sm.close(s.id)
        assert closed is not None
        assert not closed.is_open()

    def test_session_manager_close_missing_returns_none(self) -> None:
        sm = SessionManager()
        assert sm.close("missing") is None

    def test_session_manager_get(self) -> None:
        sm = SessionManager()
        s = sm.open("connector_x")
        assert sm.get(s.id) is s

    def test_session_manager_get_missing_raises(self) -> None:
        sm = SessionManager()
        with pytest.raises(MCPSessionError):
            sm.get("missing")

    def test_session_manager_contains(self) -> None:
        sm = SessionManager()
        s = sm.open("connector_x")
        assert s.id in sm

    def test_session_manager_list_excludes_closed(self) -> None:
        sm = SessionManager()
        s1 = sm.open("c1")
        s2 = sm.open("c2")
        sm.close(s1.id)
        active = sm.list()
        assert len(active) == 1
        assert active[0].id == s2.id

    def test_session_manager_list_include_closed(self) -> None:
        sm = SessionManager()
        s1 = sm.open("c1")
        sm.open("c2")
        sm.close(s1.id)
        assert len(sm.list(include_closed=True)) == 2

    def test_session_manager_active_count(self) -> None:
        sm = SessionManager()
        sm.open("c1")
        sm.open("c2")
        assert sm.active_count() == 2

    def test_session_manager_record_request(self) -> None:
        sm = SessionManager()
        s = sm.open("c1")
        resp = MCPResponse(request_id="r1", success=True)
        sm.record_request(s.id, resp)
        updated = sm.get(s.id)
        assert updated.request_count == 1
        assert updated.error_count == 0

    def test_session_manager_record_request_failure(self) -> None:
        sm = SessionManager()
        s = sm.open("c1")
        resp = MCPResponse(request_id="r1", success=False, error="boom")
        sm.record_request(s.id, resp)
        updated = sm.get(s.id)
        assert updated.error_count == 1

    def test_session_manager_touch(self) -> None:
        sm = SessionManager()
        s = sm.open("c1")
        old_active = s.last_active_at
        sm.touch(s.id)
        updated = sm.get(s.id)
        assert updated.last_active_at >= old_active

    def test_session_manager_expire_stale(self) -> None:
        sm = SessionManager(default_timeout_seconds=0.0)
        s = sm.open("c1")
        expired = sm.expire_stale()
        assert s.id in expired

    def test_session_manager_reconnect(self) -> None:
        sm = SessionManager()
        s = sm.open("c1")
        sm.close(s.id)
        sm.reconnect(s.id)
        assert sm.get(s.id).is_open()

    def test_session_manager_clear(self) -> None:
        sm = SessionManager()
        sm.open("c1")
        sm.clear()
        assert len(sm) == 0

    def test_session_manager_len(self) -> None:
        sm = SessionManager()
        sm.open("c1")
        sm.open("c2")
        assert len(sm) == 2


# ===========================================================================
# Heartbeat
# ===========================================================================


class TestHeartbeat:
    def test_heartbeat_monitor_beat(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        samples = hm.beat()
        assert len(samples) == 1
        assert samples[0].connector == "a"
        assert samples[0].success is True

    def test_heartbeat_monitor_beat_one(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        sample = hm.beat_one("a")
        assert sample.connector == "a"

    def test_heartbeat_monitor_history(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        hm.beat()
        hm.beat()
        assert len(hm.history("a")) == 2

    def test_heartbeat_monitor_last_sample(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        assert hm.last_sample("a") is None
        hm.beat()
        assert hm.last_sample("a") is not None

    def test_heartbeat_monitor_avg_latency(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        hm.beat()
        avg = hm.avg_latency("a")
        assert avg is not None
        assert avg >= 0.0

    def test_heartbeat_monitor_recommend_reconnect_disconnected(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        # Not connected
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        hm.beat()
        assert hm.recommend_reconnect("a") is True

    def test_heartbeat_monitor_recommend_reconnect_connected(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        hm.beat()
        assert hm.recommend_reconnect("a") is False

    def test_heartbeat_monitor_clear(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = HeartbeatMonitor(reg)
        hm.beat()
        hm.clear()
        assert len(hm) == 0

    def test_heartbeat_sample_is_frozen(self) -> None:
        s = HeartbeatSample(
            connector="a",
            timestamp=datetime.now(UTC),
            latency_ms=1.0,
            status=MCPStatus.CONNECTED,
            success=True,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.connector = "b"  # type: ignore[misc]


# ===========================================================================
# Health
# ===========================================================================


class TestHealth:
    def test_health_monitor_snapshot_empty(self) -> None:
        reg = MCPRegistry()
        hm = MCPHealthMonitor(reg)
        assert hm.snapshot() == {}

    def test_health_monitor_snapshot_with_connector(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = MCPHealthMonitor(reg)
        snap = hm.snapshot()
        assert "a" in snap
        assert snap["a"].level is HealthLevel.HEALTHY

    def test_health_monitor_overall_healthy(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = MCPHealthMonitor(reg)
        assert hm.overall() is HealthLevel.HEALTHY

    def test_health_monitor_overall_unknown_empty(self) -> None:
        reg = MCPRegistry()
        hm = MCPHealthMonitor(reg)
        assert hm.overall() is HealthLevel.UNKNOWN

    def test_health_monitor_is_healthy(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = MCPHealthMonitor(reg)
        assert hm.is_healthy() is True

    def test_health_monitor_degraded_connectors(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = MCPHealthMonitor(reg)
        assert hm.degraded_connectors() == []

    def test_health_monitor_offline_connectors(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        # Not connected
        reg.register(c)
        hm = MCPHealthMonitor(reg)
        offline = hm.offline_connectors()
        assert "a" in offline

    def test_health_monitor_to_dict(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        hm = MCPHealthMonitor(reg)
        d = hm.to_dict()
        assert "overall" in d
        assert "connectors" in d


# ===========================================================================
# Discovery
# ===========================================================================


class TestDiscovery:
    def test_discovery_register(self) -> None:
        d = ConnectorDiscovery()
        desc = ConnectorDescriptor(name="test", module="m", class_name="C")
        d.register(desc)
        assert d.contains("test")

    def test_discovery_unregister(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="test"))
        assert d.unregister("test") is True
        assert d.unregister("test") is False

    def test_discovery_descriptors(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="a"))
        d.register(ConnectorDescriptor(name="b"))
        assert len(d.descriptors()) == 2

    def test_discovery_descriptor_by_name(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="a"))
        assert d.descriptor("a") is not None
        assert d.descriptor("missing") is None

    def test_discovery_names(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="b"))
        d.register(ConnectorDescriptor(name="a"))
        assert d.names() == ["a", "b"]

    def test_discovery_contains(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="a"))
        assert "a" in d

    def test_discovery_register_rejects_empty_name(self) -> None:
        d = ConnectorDiscovery()
        with pytest.raises(MCPDiscoveryError):
            d.register(ConnectorDescriptor(name=""))

    def test_discovery_scan_filesystem_placeholder(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="a"))
        result = d.scan_filesystem("/some/path")
        assert len(result) == 1

    def test_discovery_scan_network_placeholder(self) -> None:
        d = ConnectorDiscovery()
        result = d.scan_network("local")
        assert result == []

    def test_discovery_instantiate(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="test", capabilities=("cap1",)))
        c = d.instantiate("test")
        assert c.name == "test"
        assert any(cap.name == "cap1" for cap in c.capabilities())

    def test_discovery_instantiate_missing_raises(self) -> None:
        d = ConnectorDiscovery()
        with pytest.raises(MCPDiscoveryError):
            d.instantiate("missing")

    def test_discovery_instantiate_all(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="a"))
        d.register(ConnectorDescriptor(name="b"))
        all_c = d.instantiate_all()
        assert len(all_c) == 2

    def test_discovery_len(self) -> None:
        d = ConnectorDiscovery()
        d.register(ConnectorDescriptor(name="a"))
        assert len(d) == 1


# ===========================================================================
# Router
# ===========================================================================


class TestRouter:
    def test_router_routes_by_capability(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        router = MCPRouter(reg)
        req = MCPRequest(connector="", capability="ping")
        chosen = router.route(req)
        assert chosen.name == "a"

    def test_router_routes_by_explicit_connector(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        router = MCPRouter(reg)
        req = MCPRequest(connector="a", capability="ping")
        chosen = router.route(req)
        assert chosen.name == "a"

    def test_router_raises_on_no_capability(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        router = MCPRouter(reg)
        req = MCPRequest(connector="", capability="bogus")
        with pytest.raises(MCPCapabilityError):
            router.route(req)

    def test_router_raises_on_missing_connector(self) -> None:
        reg = MCPRegistry()
        router = MCPRouter(reg)
        req = MCPRequest(connector="missing", capability="ping")
        with pytest.raises(MCPNotFoundError):
            router.route(req)

    def test_router_can_route_true(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        router = MCPRouter(reg)
        req = MCPRequest(connector="", capability="ping")
        assert router.can_route(req) is True

    def test_router_can_route_false(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        router = MCPRouter(reg)
        req = MCPRequest(connector="", capability="bogus")
        assert router.can_route(req) is False

    def test_router_available_connectors(self) -> None:
        reg = MCPRegistry()
        c = PlaceholderConnector(name="a")
        c.connect()
        reg.register(c)
        router = MCPRouter(reg)
        available = router.available_connectors("ping")
        assert len(available) == 1


# ===========================================================================
# Manager
# ===========================================================================


class TestManager:
    def test_manager_register_connector(self) -> None:
        m = MCPManager()
        c = PlaceholderConnector(name="a")
        m.register_connector(c)
        assert m.registry.contains("a")

    def test_manager_unregister_connector(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        assert m.unregister_connector("a") is True

    def test_manager_get_connector(self) -> None:
        m = MCPManager()
        c = PlaceholderConnector(name="a")
        m.register_connector(c)
        assert m.get_connector("a") is c

    def test_manager_list_connectors(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        m.register_connector(PlaceholderConnector(name="b"))
        assert len(m.list_connectors()) == 2

    def test_manager_open_session(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        s = m.open_session("a", permissions=["read"])
        assert s.connector == "a"

    def test_manager_open_session_missing_connector(self) -> None:
        m = MCPManager()
        with pytest.raises(MCPNotFoundError):
            m.open_session("missing")

    def test_manager_close_session(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        s = m.open_session("a")
        closed = m.close_session(s.id)
        assert closed is not None

    def test_manager_execute_with_session(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        s = m.open_session("a", permissions=["read"])
        resp = m.execute_capability("ping", connector="a", session_id=s.id)
        assert resp.success
        assert resp.output == "pong"

    def test_manager_execute_permission_denied(self) -> None:
        m = MCPManager()
        # Register a connector that requires EXECUTE permission
        from atlas.mcp.permissions import PermissionLevel

        c = PlaceholderConnector(name="a", required_permission=PermissionLevel.EXECUTE)
        m.register_connector(c)
        s = m.open_session("a", permissions=["read"])  # only read
        with pytest.raises(MCPPermissionError):
            m.execute_capability("ping", connector="a", session_id=s.id)

    def test_manager_execute_no_capability(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        s = m.open_session("a", permissions=["read"])
        with pytest.raises(MCPCapabilityError):
            m.execute_capability("bogus", session_id=s.id)

    def test_manager_health(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        health = m.health()
        assert "a" in health

    def test_manager_is_healthy(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        assert m.is_healthy() is True

    def test_manager_overall_health(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        assert m.overall_health() is HealthLevel.HEALTHY

    def test_manager_statistics(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        stats = m.statistics()
        assert stats.connectors_total == 1

    def test_manager_heartbeat(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        needs = m.heartbeat()
        assert needs == []

    def test_manager_reconnect(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        assert m.reconnect("a") is True

    def test_manager_reconnect_missing(self) -> None:
        m = MCPManager()
        assert m.reconnect("missing") is False

    def test_manager_reconnect_all(self) -> None:
        m = MCPManager()
        c = PlaceholderConnector(name="a")
        m.register_connector(c)
        c.disconnect()
        results = m.reconnect_all()
        assert "a" in results
        assert results["a"] is True

    def test_manager_find_by_capability(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        results = m.find_by_capability("ping")
        assert len(results) == 1

    def test_manager_all_capabilities(self) -> None:
        m = MCPManager()
        m.register_connector(PlaceholderConnector(name="a"))
        caps = m.all_capabilities()
        assert "a" in caps

    def test_manager_auto_connect(self) -> None:
        m = MCPManager(auto_connect=True)
        c = PlaceholderConnector(name="a")
        m.register_connector(c)
        assert c.is_connected

    def test_manager_no_auto_connect(self) -> None:
        m = MCPManager(auto_connect=False)
        c = PlaceholderConnector(name="a")
        m.register_connector(c)
        assert not c.is_connected


# ===========================================================================
# Server / Client
# ===========================================================================


class TestServerClient:
    def test_server_start_stop(self) -> None:
        s = MCPServerInstance(name="test")
        s.start()
        assert s.is_running
        s.stop()
        assert not s.is_running

    def test_server_handshake(self) -> None:
        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
        )
        s.start()
        req = HandshakeRequest(
            client_versions=("1.1",),
            capabilities=("ping",),
        )
        resp = s.handshake(req)
        assert resp.success
        assert resp.agreed_version == "1.1"

    def test_server_handshake_not_running_raises(self) -> None:
        s = MCPServerInstance(name="test")
        with pytest.raises(MCPHandshakeError):
            s.handshake(HandshakeRequest())

    def test_server_handle(self) -> None:
        def handler(req: MCPRequest) -> MCPResponse:
            return MCPResponse(request_id=req.id, success=True, output="ok")

        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
            handler=handler,
        )
        s.start()
        req = MCPRequest(connector="test", capability="ping")
        resp = s.handle(req)
        assert resp.success
        assert resp.output == "ok"

    def test_server_handle_not_running(self) -> None:
        s = MCPServerInstance(name="test")
        req = MCPRequest(connector="test", capability="ping")
        resp = s.handle(req)
        assert not resp.success

    def test_server_handle_unknown_capability(self) -> None:
        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
        )
        s.start()
        req = MCPRequest(connector="test", capability="bogus")
        with pytest.raises(MCPProtocolError):
            s.handle(req)

    def test_server_request_count(self) -> None:
        def handler(req: MCPRequest) -> MCPResponse:
            return MCPResponse(request_id=req.id, success=True)

        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
            handler=handler,
        )
        s.start()
        s.handle(MCPRequest(connector="test", capability="ping"))
        s.handle(MCPRequest(connector="test", capability="ping"))
        assert s.request_count == 2

    def test_client_connect(self) -> None:
        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
        )
        s.start()
        c = MCPClientInstance(name="c1", server=s)
        resp = c.connect(capabilities=["ping"])
        assert resp.success
        assert c.is_connected

    def test_client_connect_server_not_running(self) -> None:
        s = MCPServerInstance(name="test")
        c = MCPClientInstance(name="c1", server=s)
        with pytest.raises(MCPConnectionError):
            c.connect()

    def test_client_send(self) -> None:
        def handler(req: MCPRequest) -> MCPResponse:
            return MCPResponse(request_id=req.id, success=True, output="pong")

        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
            handler=handler,
        )
        s.start()
        c = MCPClientInstance(name="c1", server=s)
        c.connect()
        resp = c.call("ping")
        assert resp.success
        assert resp.output == "pong"

    def test_client_send_not_connected(self) -> None:
        s = MCPServerInstance(name="test")
        c = MCPClientInstance(name="c1", server=s)
        with pytest.raises(MCPConnectionError):
            c.send(MCPRequest(connector="test", capability="ping"))

    def test_client_disconnect(self) -> None:
        s = MCPServerInstance(name="test")
        s.start()
        c = MCPClientInstance(name="c1", server=s)
        c.connect()
        c.disconnect()
        assert not c.is_connected

    def test_client_request_count(self) -> None:
        def handler(req: MCPRequest) -> MCPResponse:
            return MCPResponse(request_id=req.id, success=True)

        s = MCPServerInstance(
            name="test",
            capabilities=(MCPCapability(name="ping"),),
            handler=handler,
        )
        s.start()
        c = MCPClientInstance(name="c1", server=s)
        c.connect()
        c.call("ping")
        c.call("ping")
        assert c.request_count == 2


# ===========================================================================
# Connectors
# ===========================================================================


class TestConnectors:
    """Test every connector."""

    def test_all_connectors_count(self) -> None:
        assert len(ALL_CONNECTORS) == 17

    def test_all_connector_classes_returns_list(self) -> None:
        classes = all_connector_classes()
        assert len(classes) == 17

    def test_instantiate_all_returns_17(self) -> None:
        instances = instantiate_all()
        assert len(instances) == 17

    def test_connector_class_for_known(self) -> None:
        cls = connector_class_for("FilesystemConnector")
        assert cls is FilesystemConnector

    def test_connector_class_for_unknown(self) -> None:
        assert connector_class_for("Bogus") is None

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_has_name(self, connector_cls: type) -> None:
        c = connector_cls()
        assert c.name != ""

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_has_description(self, connector_cls: type) -> None:
        c = connector_cls()
        assert c.description != ""

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_has_capabilities(self, connector_cls: type) -> None:
        c = connector_cls()
        assert len(c.capabilities()) > 0

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_connect_disconnect(self, connector_cls: type) -> None:
        c = connector_cls()
        c.connect()
        assert c.is_connected
        c.disconnect()
        assert not c.is_connected

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_health(self, connector_cls: type) -> None:
        c = connector_cls()
        c.connect()
        h = c.health()
        assert h.status is MCPStatus.CONNECTED
        assert h.level is HealthLevel.HEALTHY

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_discover(self, connector_cls: type) -> None:
        c = connector_cls()
        d = c.discover()
        assert "name" in d
        assert "capabilities" in d
        assert "supported_transports" in d

    @pytest.mark.parametrize(
        "connector_cls",
        list(ALL_CONNECTORS),
    )
    def test_connector_execute_not_connected(self, connector_cls: type) -> None:
        c = connector_cls()
        req = MCPRequest(connector=c.name, capability="test")
        resp = c.execute(req)
        assert not resp.success

    def test_filesystem_connector_execute(self) -> None:
        c = FilesystemConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="filesystem",
                capability="file.read",
                params={"path": "/tmp/x"},
            )
        )
        assert resp.success
        assert resp.output["path"] == "/tmp/x"

    def test_github_connector_execute(self) -> None:
        c = GitHubConnector()
        c.connect()
        resp = c.execute(MCPRequest(connector="github", capability="repo.list"))
        assert resp.success
        assert "repos" in resp.output

    def test_browser_connector_execute(self) -> None:
        c = BrowserConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="browser",
                capability="browser.navigate",
                params={"url": "https://example.com"},
            )
        )
        assert resp.success
        assert resp.output["url"] == "https://example.com"

    def test_playwright_connector_execute(self) -> None:
        c = PlaywrightConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="playwright",
                capability="playwright.launch",
                params={"browser": "chromium"},
            )
        )
        assert resp.success

    def test_blender_connector_execute(self) -> None:
        c = BlenderConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="blender", capability="blender.render", params={"frame": 1}
            )
        )
        assert resp.success

    def test_ollama_connector_execute(self) -> None:
        c = OllamaConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="ollama",
                capability="ollama.generate",
                params={"prompt": "hello"},
            )
        )
        assert resp.success
        assert "response" in resp.output

    def test_windows_connector_execute(self) -> None:
        c = WindowsConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="windows",
                capability="windows.shell",
                params={"command": "dir"},
            )
        )
        assert resp.success

    def test_openrouter_connector_execute(self) -> None:
        c = OpenRouterConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(connector="openrouter", capability="openrouter.models")
        )
        assert resp.success
        assert "models" in resp.output

    def test_surpac_connector_execute(self) -> None:
        c = SurpacConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="surpac",
                capability="surpac.blockmodel.load",
                params={"path": "model.mdl"},
            )
        )
        assert resp.success

    def test_autocad_connector_execute(self) -> None:
        c = AutoCADConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="autocad",
                capability="autocad.drawing.new",
                params={"name": "D1"},
            )
        )
        assert resp.success

    def test_qgis_connector_execute(self) -> None:
        c = QGISConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="qgis", capability="qgis.project.new", params={"name": "P1"}
            )
        )
        assert resp.success

    def test_photoshop_connector_execute(self) -> None:
        c = PhotoshopConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="photoshop",
                capability="photoshop.doc.new",
                params={"name": "D1"},
            )
        )
        assert resp.success

    def test_canva_connector_execute(self) -> None:
        c = CanvaConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="canva",
                capability="canva.design.create",
                params={"type": "poster"},
            )
        )
        assert resp.success

    def test_google_forms_connector_execute(self) -> None:
        c = GoogleFormsConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="google_forms",
                capability="forms.create",
                params={"title": "Survey"},
            )
        )
        assert resp.success

    def test_excel_connector_execute(self) -> None:
        c = ExcelConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="excel",
                capability="excel.cell.set",
                params={"cell": "A1", "value": "42"},
            )
        )
        assert resp.success

    def test_word_connector_execute(self) -> None:
        c = WordConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="word",
                capability="word.paragraph.add",
                params={"text": "Hello"},
            )
        )
        assert resp.success

    def test_powerpoint_connector_execute(self) -> None:
        c = PowerPointConnector()
        c.connect()
        resp = c.execute(
            MCPRequest(
                connector="powerpoint", capability="ppt.slide.add", params={"number": 1}
            )
        )
        assert resp.success

    def test_each_connector_has_unique_name(self) -> None:
        names = [cls().name for cls in ALL_CONNECTORS]
        assert len(names) == len(set(names))


# ===========================================================================
# End-to-end
# ===========================================================================


class TestEndToEnd:
    def test_full_manager_lifecycle(self) -> None:
        m = MCPManager()
        for c in instantiate_all():
            m.register_connector(c)
        assert len(m.list_connectors()) == 17
        assert m.overall_health() is HealthLevel.HEALTHY
        s = m.open_session("filesystem", permissions=["read", "write"])
        resp = m.execute_capability(
            "file.read", {"path": "/x"}, connector="filesystem", session_id=s.id
        )
        assert resp.success
        stats = m.statistics()
        assert stats.requests_total >= 1
        m.close_session(s.id)

    def test_full_client_server_flow(self) -> None:
        def handler(req: MCPRequest) -> MCPResponse:
            return MCPResponse(
                request_id=req.id, success=True, output={"echoed": req.capability}
            )

        server = MCPServerInstance(
            name="test-server",
            capabilities=(MCPCapability(name="test.cap"),),
            handler=handler,
        )
        server.start()
        client = MCPClientInstance(name="test-client", server=server)
        client.connect(capabilities=["test.cap"])
        resp = client.call("test.cap", {"param": 1})
        assert resp.success
        assert resp.output == {"echoed": "test.cap"}
        client.disconnect()
        server.stop()

    def test_heartbeat_with_all_connectors(self) -> None:
        m = MCPManager()
        for c in instantiate_all():
            m.register_connector(c)
        needs = m.heartbeat()
        assert needs == []

    def test_reconnect_all(self) -> None:
        m = MCPManager()
        for c in instantiate_all():
            m.register_connector(c)
        # Disconnect one
        m.get_connector("filesystem").disconnect()
        results = m.reconnect_all()
        assert "filesystem" in results
        assert results["filesystem"] is True

    def test_router_with_multiple_connectors(self) -> None:
        m = MCPManager()
        for c in instantiate_all():
            m.register_connector(c)
        # Every connector should be routable for at least one capability
        for c in m.list_connectors():
            caps = c.capabilities()
            if caps:
                req = MCPRequest(connector="", capability=caps[0].name)
                assert m.router.can_route(req)

    def test_zero_circular_imports(self) -> None:
        import importlib

        modules = [
            "atlas.mcp.exceptions",
            "atlas.mcp.models",
            "atlas.mcp.protocol",
            "atlas.mcp.permissions",
            "atlas.mcp.base",
            "atlas.mcp.transport",
            "atlas.mcp.registry",
            "atlas.mcp.session",
            "atlas.mcp.heartbeat",
            "atlas.mcp.health",
            "atlas.mcp.discovery",
            "atlas.mcp.router",
            "atlas.mcp.manager",
            "atlas.mcp.server",
            "atlas.mcp.client",
            "atlas.mcp.connectors",
            "atlas.mcp",
        ]
        for m in modules:
            importlib.import_module(m)
