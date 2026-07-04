"""Excel MCP connector — deterministic placeholder."""

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


class ExcelConnector(BaseConnector):
    """Deterministic placeholder Excel MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="excel",
            description="Microsoft Excel automation (workbooks, sheets, formulas)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="excel.workbook.new",
                    description="Create a workbook",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="excel.workbook.open",
                    description="Open a workbook",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="excel.sheet.add",
                    description="Add a worksheet",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="excel.cell.set",
                    description="Set a cell value",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="excel.cell.get",
                    description="Get a cell value",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="excel.formula.set",
                    description="Set a formula",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="excel.export",
                    description="Export workbook",
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
            latency_ms=120.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "excel.workbook.new":
            return {"name": request.params.get("name", "Book1"), "created": True}
        if request.capability == "excel.workbook.open":
            return {
                "path": request.params.get("path", ""),
                "opened": True,
                "sheets": ["Sheet1"],
            }
        if request.capability == "excel.sheet.add":
            return {"sheet": request.params.get("name", "Sheet2"), "added": True}
        if request.capability == "excel.cell.set":
            return {
                "cell": request.params.get("cell", "A1"),
                "value": request.params.get("value", ""),
                "set": True,
            }
        if request.capability == "excel.cell.get":
            return {
                "cell": request.params.get("cell", "A1"),
                "value": "placeholder_value",
            }
        if request.capability == "excel.formula.set":
            return {
                "cell": request.params.get("cell", "B1"),
                "formula": request.params.get("formula", "=SUM(A1:A10)"),
                "set": True,
            }
        if request.capability == "excel.export":
            return {
                "path": request.params.get("path", ""),
                "format": request.params.get("format", "xlsx"),
                "exported": True,
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["ExcelConnector"]
