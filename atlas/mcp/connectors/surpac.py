"""Surpac MCP connector — deterministic placeholder."""

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


class SurpacConnector(BaseConnector):
    """Deterministic placeholder Surpac MCP connector.

    Surpac is a mining-grade geological modelling tool. A real
    implementation would drive Surpac's scripting API; the placeholder
    returns deterministic responses.
    """

    def __init__(self) -> None:
        super().__init__(
            name="surpac",
            description=(
                "Surpac geological modelling " "(block models, drillholes, surfaces)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="surpac.blockmodel.load",
                    description="Load a block model",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="surpac.blockmodel.query",
                    description="Query block model",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="surpac.drillhole.import",
                    description="Import drillholes",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="surpac.surface.create",
                    description="Create a surface",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="surpac.section.create",
                    description="Create a section",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="surpac.export",
                    description="Export data",
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
            latency_ms=250.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "surpac.blockmodel.load":
            return {
                "model": request.params.get("path", ""),
                "blocks": 10000,
                "loaded": True,
            }
        if request.capability == "surpac.blockmodel.query":
            return {
                "model": request.params.get("model", ""),
                "blocks_matched": 42,
                "avg_grade": 1.25,
            }
        if request.capability == "surpac.drillhole.import":
            return {"file": request.params.get("path", ""), "holes_imported": 100}
        if request.capability == "surpac.surface.create":
            return {
                "surface": request.params.get("name", ""),
                "triangles": 5000,
                "created": True,
            }
        if request.capability == "surpac.section.create":
            return {"section": request.params.get("name", ""), "created": True}
        if request.capability == "surpac.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "dxf"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["SurpacConnector"]
