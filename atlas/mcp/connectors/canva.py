"""Canva MCP connector — deterministic placeholder."""

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


class CanvaConnector(BaseConnector):
    """Deterministic placeholder Canva MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="canva",
            description="Canva design automation (designs, templates, export)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="canva.design.create",
                    description="Create a design",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="canva.template.list",
                    description="List templates",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="canva.element.add",
                    description="Add an element",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="canva.text.add",
                    description="Add text",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="canva.export",
                    description="Export design",
                    permissions=("read",),
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
            latency_ms=350.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "canva.design.create":
            return {
                "design_id": "placeholder_123",
                "type": request.params.get("type", "poster"),
                "created": True,
            }
        if request.capability == "canva.template.list":
            return {"templates": ["poster_1", "social_1", "presentation_1"]}
        if request.capability == "canva.element.add":
            return {"element": request.params.get("type", "shape"), "added": True}
        if request.capability == "canva.text.add":
            return {"text": request.params.get("content", ""), "added": True}
        if request.capability == "canva.export":
            return {
                "design_id": request.params.get("design_id", ""),
                "format": request.params.get("format", "png"),
                "bytes": 5120,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["CanvaConnector"]
