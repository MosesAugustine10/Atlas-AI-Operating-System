"""QGIS MCP connector — deterministic placeholder."""

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


class QGISConnector(BaseConnector):
    """Deterministic placeholder QGIS MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="qgis",
            description="QGIS GIS automation (layers, maps, analysis, plugins)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="qgis.project.new",
                    description="Create a new project",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="qgis.layer.add",
                    description="Add a layer",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="qgis.layer.style",
                    description="Set layer style",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="qgis.analysis.buffer",
                    description="Buffer analysis",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="qgis.analysis.overlay",
                    description="Overlay analysis",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="qgis.map.export",
                    description="Export map",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="qgis.plugin.run",
                    description="Run a plugin",
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
            latency_ms=220.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "qgis.project.new":
            return {"project": request.params.get("name", "Project1"), "created": True}
        if request.capability == "qgis.layer.add":
            return {
                "layer": request.params.get("path", ""),
                "type": request.params.get("type", "vector"),
                "added": True,
            }
        if request.capability == "qgis.layer.style":
            return {"layer": request.params.get("layer", ""), "styled": True}
        if request.capability == "qgis.analysis.buffer":
            return {
                "input": request.params.get("layer", ""),
                "buffer_distance": request.params.get("distance", 100),
                "output": "buffer_layer",
            }
        if request.capability == "qgis.analysis.overlay":
            return {
                "input": request.params.get("layer1", ""),
                "overlay": request.params.get("layer2", ""),
                "output": "overlay_layer",
            }
        if request.capability == "qgis.map.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "png"),
                "exported": True,
            }
        if request.capability == "qgis.plugin.run":
            return {"plugin": request.params.get("name", ""), "executed": True}
        return {"capability": request.capability, "params": request.params}


__all__ = ["QGISConnector"]
