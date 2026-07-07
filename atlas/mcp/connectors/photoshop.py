"""Photoshop MCP connector — deterministic placeholder."""

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


class PhotoshopConnector(BaseConnector):
    """Deterministic placeholder Photoshop MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="photoshop",
            description="Adobe Photoshop automation (documents, layers, filters)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="photoshop.doc.new",
                    description="Create a new document",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="photoshop.doc.open",
                    description="Open a document",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="photoshop.layer.add",
                    description="Add a layer",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="photoshop.filter.apply",
                    description="Apply a filter",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="photoshop.adjustment",
                    description="Apply an adjustment",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="photoshop.export",
                    description="Export document",
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
            latency_ms=160.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "photoshop.doc.new":
            return {
                "name": request.params.get("name", "Untitled"),
                "width": 1920,
                "height": 1080,
                "created": True,
            }
        if request.capability == "photoshop.doc.open":
            return {"path": request.params.get("path", ""), "opened": True}
        if request.capability == "photoshop.layer.add":
            return {"layer": request.params.get("name", "Layer 1"), "added": True}
        if request.capability == "photoshop.filter.apply":
            return {
                "filter": request.params.get("filter", "gaussian_blur"),
                "applied": True,
            }
        if request.capability == "photoshop.adjustment":
            return {
                "adjustment": request.params.get("type", "brightness"),
                "applied": True,
            }
        if request.capability == "photoshop.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "png"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["PhotoshopConnector"]
