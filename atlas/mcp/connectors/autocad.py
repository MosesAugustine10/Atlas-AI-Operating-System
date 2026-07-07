"""AutoCAD MCP connector — deterministic placeholder."""

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


class AutoCADConnector(BaseConnector):
    """Deterministic placeholder AutoCAD MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="autocad",
            description="AutoCAD drafting (drawings, layers, blocks, dimensions)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="autocad.drawing.new",
                    description="Create a new drawing",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="autocad.drawing.open",
                    description="Open a drawing",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="autocad.layer.create",
                    description="Create a layer",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="autocad.entity.add",
                    description="Add an entity",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="autocad.dimension.add",
                    description="Add a dimension",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="autocad.block.insert",
                    description="Insert a block",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="autocad.export",
                    description="Export drawing",
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
            latency_ms=180.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "autocad.drawing.new":
            return {"name": request.params.get("name", "Drawing1"), "created": True}
        if request.capability == "autocad.drawing.open":
            return {
                "path": request.params.get("path", ""),
                "opened": True,
                "layers": ["0", "Dimensions"],
            }
        if request.capability == "autocad.layer.create":
            return {"layer": request.params.get("name", ""), "created": True}
        if request.capability == "autocad.entity.add":
            return {"entity": request.params.get("type", "line"), "added": True}
        if request.capability == "autocad.dimension.add":
            return {"dimension": request.params.get("type", "linear"), "added": True}
        if request.capability == "autocad.block.insert":
            return {"block": request.params.get("name", ""), "inserted": True}
        if request.capability == "autocad.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "dwg"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["AutoCADConnector"]
