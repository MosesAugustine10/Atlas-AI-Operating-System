"""Windows MCP connector — deterministic placeholder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.mcp.base import BaseConnector
from atlas.mcp.models import (
    HealthLevel,
    MCPCapability,
    MCPHealth,
    MCPRequest,
    MCPStatus,
    MCPTransport,
    TransportKind,
)
from atlas.mcp.permissions import PermissionLevel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WindowsConnector(BaseConnector):
    """Deterministic placeholder Windows OS MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="windows",
            description="Windows OS automation (apps, files, registry, shell)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="windows.app.open",
                    description="Open an application",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.app.close",
                    description="Close an application",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.shell",
                    description="Run a shell command",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.registry.get",
                    description="Read registry value",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="windows.registry.set",
                    description="Write registry value",
                    permissions=("admin",),
                ),
                MCPCapability(
                    name="windows.clipboard",
                    description="Read/write clipboard",
                    permissions=("read", "write"),
                ),
            ),
        )

    def _do_connect(self, transport: MCPTransport) -> None:
        return None

    def _do_disconnect(self) -> None:
        return None

    def _do_health(self) -> MCPHealth:
        return MCPHealth(
            connector=self.name,
            status=MCPStatus.CONNECTED,
            level=HealthLevel.HEALTHY,
            latency_ms=50.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "windows.app.open":
            return {"app": request.params.get("app", ""), "opened": True}
        if request.capability == "windows.app.close":
            return {"app": request.params.get("app", ""), "closed": True}
        if request.capability == "windows.shell":
            return {
                "command": request.params.get("command", ""),
                "exit_code": 0,
                "stdout": "placeholder output",
            }
        if request.capability == "windows.registry.get":
            return {"key": request.params.get("key", ""), "value": "placeholder_value"}
        if request.capability == "windows.registry.set":
            return {"key": request.params.get("key", ""), "set": True}
        if request.capability == "windows.clipboard":
            action = request.params.get("action", "read")
            return {"action": action, "data": "placeholder_clipboard_data"}
        return {"capability": request.capability, "params": request.params}


__all__ = ["WindowsConnector"]
