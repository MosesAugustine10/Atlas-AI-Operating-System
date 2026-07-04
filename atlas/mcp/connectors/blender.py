"""Blender MCP connector — deterministic placeholder."""

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


class BlenderConnector(BaseConnector):
    """Deterministic placeholder Blender MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="blender",
            description="Blender 3D automation (scenes, objects, rendering)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="blender.scene.new",
                    description="Create a new scene",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.object.add",
                    description="Add an object",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.object.transform",
                    description="Transform an object",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.material.apply",
                    description="Apply a material",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.render",
                    description="Render the scene",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="blender.export",
                    description="Export to a file",
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
            latency_ms=200.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "blender.scene.new":
            return {"scene": request.params.get("name", "Scene"), "created": True}
        if request.capability == "blender.object.add":
            return {
                "object": request.params.get("name", "Cube"),
                "type": request.params.get("type", "mesh"),
            }
        if request.capability == "blender.object.transform":
            return {"object": request.params.get("name", ""), "transformed": True}
        if request.capability == "blender.material.apply":
            return {
                "object": request.params.get("name", ""),
                "material": request.params.get("material", ""),
            }
        if request.capability == "blender.render":
            return {
                "frame": request.params.get("frame", 1),
                "bytes": 8192,
                "format": "png",
            }
        if request.capability == "blender.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "obj"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["BlenderConnector"]
