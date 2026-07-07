"""Word MCP connector — deterministic placeholder."""

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


class WordConnector(BaseConnector):
    """Deterministic placeholder Microsoft Word MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="word",
            description="Microsoft Word automation (documents, paragraphs, styles)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="word.doc.new",
                    description="Create a document",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="word.doc.open",
                    description="Open a document",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="word.paragraph.add",
                    description="Add a paragraph",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="word.heading.add",
                    description="Add a heading",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="word.style.apply",
                    description="Apply a style",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="word.table.add",
                    description="Add a table",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="word.export",
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
            latency_ms=130.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "word.doc.new":
            return {"name": request.params.get("name", "Document1"), "created": True}
        if request.capability == "word.doc.open":
            return {
                "path": request.params.get("path", ""),
                "opened": True,
                "paragraphs": 10,
            }
        if request.capability == "word.paragraph.add":
            return {"text": request.params.get("text", ""), "added": True}
        if request.capability == "word.heading.add":
            return {
                "text": request.params.get("text", ""),
                "level": request.params.get("level", 1),
                "added": True,
            }
        if request.capability == "word.style.apply":
            return {"style": request.params.get("style", "Normal"), "applied": True}
        if request.capability == "word.table.add":
            return {
                "rows": request.params.get("rows", 3),
                "cols": request.params.get("cols", 3),
                "added": True,
            }
        if request.capability == "word.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "docx"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["WordConnector"]
