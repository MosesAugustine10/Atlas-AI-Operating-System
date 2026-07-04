"""Browser MCP connector — deterministic placeholder."""

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


class BrowserConnector(BaseConnector):
    """Deterministic placeholder browser MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="browser",
            description="Browser automation (navigate, click, extract)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.WEBSOCKET),
            default_transport=TransportKind.WEBSOCKET,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="browser.navigate",
                    description="Navigate to URL",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="browser.click",
                    description="Click an element",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="browser.extract",
                    description="Extract page content",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="browser.screenshot",
                    description="Take screenshot",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="browser.fill",
                    description="Fill a form field",
                    permissions=("write",),
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
            latency_ms=80.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "browser.navigate":
            return {
                "url": request.params.get("url", ""),
                "title": "Placeholder Page",
                "status": 200,
            }
        if request.capability == "browser.click":
            return {"selector": request.params.get("selector", ""), "clicked": True}
        if request.capability == "browser.extract":
            return {
                "url": request.params.get("url", ""),
                "text": "Placeholder page content",
                "links": [],
            }
        if request.capability == "browser.screenshot":
            return {
                "url": request.params.get("url", ""),
                "bytes": 1024,
                "format": "png",
            }
        if request.capability == "browser.fill":
            return {
                "selector": request.params.get("selector", ""),
                "value": request.params.get("value", ""),
                "filled": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["BrowserConnector"]
