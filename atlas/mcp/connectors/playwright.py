"""Playwright MCP connector — deterministic placeholder."""

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


class PlaywrightConnector(BaseConnector):
    """Deterministic placeholder Playwright MCP connector.

    Playwright is a higher-fidelity browser automation library than the
    basic browser connector. A real implementation would drive a
    Playwright subprocess; the placeholder returns deterministic
    responses.
    """

    def __init__(self) -> None:
        super().__init__(
            name="playwright",
            description="Playwright browser automation (multi-browser, headless)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.STDIO),
            default_transport=TransportKind.STDIO,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="playwright.launch",
                    description="Launch a browser",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.goto",
                    description="Navigate to URL",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.click",
                    description="Click an element",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.type",
                    description="Type into a field",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="playwright.pdf",
                    description="Save page as PDF",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="playwright.screenshot",
                    description="Take screenshot",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="playwright.evaluate",
                    description="Evaluate JS",
                    permissions=("execute",),
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
            latency_ms=150.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "playwright.launch":
            return {
                "browser": request.params.get("browser", "chromium"),
                "launched": True,
            }
        if request.capability == "playwright.goto":
            return {
                "url": request.params.get("url", ""),
                "status": 200,
                "title": "Placeholder",
            }
        if request.capability == "playwright.click":
            return {"selector": request.params.get("selector", ""), "clicked": True}
        if request.capability == "playwright.type":
            return {
                "selector": request.params.get("selector", ""),
                "text": request.params.get("text", ""),
                "typed": True,
            }
        if request.capability == "playwright.pdf":
            return {"url": request.params.get("url", ""), "bytes": 2048, "pages": 1}
        if request.capability == "playwright.screenshot":
            return {
                "url": request.params.get("url", ""),
                "bytes": 4096,
                "format": "png",
            }
        if request.capability == "playwright.evaluate":
            return {"result": "placeholder_js_result"}
        return {"capability": request.capability, "params": request.params}


__all__ = ["PlaywrightConnector"]
