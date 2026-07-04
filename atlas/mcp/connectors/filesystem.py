"""Filesystem MCP connector — deterministic placeholder.

Exposes file-read / file-write / file-list capabilities. A real
implementation would call the Atlas Tool Layer's filesystem adapter;
the placeholder returns deterministic responses.
"""

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


class FilesystemConnector(BaseConnector):
    """Deterministic placeholder filesystem MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="filesystem",
            description="Filesystem access (read, write, list)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.STDIO),
            default_transport=TransportKind.IN_PROCESS,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="file.read",
                    description="Read a file",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.write",
                    description="Write a file",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="file.list",
                    description="List directory contents",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="file.delete",
                    description="Delete a file",
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
            latency_ms=0.5,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        path = request.params.get("path", "")
        if request.capability == "file.read":
            return {"path": path, "content": f"placeholder content of {path}"}
        if request.capability == "file.write":
            return {
                "path": path,
                "bytes_written": len(str(request.params.get("content", ""))),
            }
        if request.capability == "file.list":
            return {"path": path, "entries": ["file1.txt", "file2.txt", "subdir/"]}
        if request.capability == "file.delete":
            return {"path": path, "deleted": True}
        return {"capability": request.capability, "params": request.params}


__all__ = ["FilesystemConnector"]
