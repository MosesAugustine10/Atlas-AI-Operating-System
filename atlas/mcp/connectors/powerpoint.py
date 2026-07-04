"""PowerPoint MCP connector — deterministic placeholder."""

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


class PowerPointConnector(BaseConnector):
    """Deterministic placeholder Microsoft PowerPoint MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="powerpoint",
            description="Microsoft PowerPoint automation (slides, shapes, export)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="ppt.presentation.new",
                    description="Create a presentation",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="ppt.presentation.open",
                    description="Open a presentation",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ppt.slide.add",
                    description="Add a slide",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="ppt.text.add",
                    description="Add text to a slide",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="ppt.image.add",
                    description="Add an image",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="ppt.template.apply",
                    description="Apply a template",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="ppt.export",
                    description="Export presentation",
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
            latency_ms=140.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "ppt.presentation.new":
            return {
                "name": request.params.get("name", "Presentation1"),
                "created": True,
            }
        if request.capability == "ppt.presentation.open":
            return {
                "path": request.params.get("path", ""),
                "opened": True,
                "slides": 10,
            }
        if request.capability == "ppt.slide.add":
            return {
                "slide_number": request.params.get("number", 1),
                "layout": request.params.get("layout", "title"),
                "added": True,
            }
        if request.capability == "ppt.text.add":
            return {
                "slide": request.params.get("slide", 1),
                "text": request.params.get("text", ""),
                "added": True,
            }
        if request.capability == "ppt.image.add":
            return {
                "slide": request.params.get("slide", 1),
                "path": request.params.get("path", ""),
                "added": True,
            }
        if request.capability == "ppt.template.apply":
            return {"template": request.params.get("template", ""), "applied": True}
        if request.capability == "ppt.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "pptx"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["PowerPointConnector"]
