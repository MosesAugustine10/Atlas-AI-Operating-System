"""Google Forms MCP connector — deterministic placeholder."""

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


class GoogleFormsConnector(BaseConnector):
    """Deterministic placeholder Google Forms MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="google_forms",
            description="Google Forms automation (create, list, responses)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="forms.create",
                    description="Create a form",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="forms.list", description="List forms", permissions=("read",)
                ),
                MCPCapability(
                    name="forms.question.add",
                    description="Add a question",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="forms.responses.list",
                    description="List responses",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="forms.response.count",
                    description="Count responses",
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
            latency_ms=280.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "forms.create":
            return {
                "form_id": "placeholder_form_123",
                "title": request.params.get("title", ""),
                "created": True,
            }
        if request.capability == "forms.list":
            return {
                "forms": [
                    {"id": "form_1", "title": "Survey"},
                    {"id": "form_2", "title": "Quiz"},
                ]
            }
        if request.capability == "forms.question.add":
            return {
                "form_id": request.params.get("form_id", ""),
                "question": request.params.get("text", ""),
                "added": True,
            }
        if request.capability == "forms.responses.list":
            return {
                "form_id": request.params.get("form_id", ""),
                "responses": [{"id": "r1", "submitted_at": "2026-01-01"}],
            }
        if request.capability == "forms.response.count":
            return {"form_id": request.params.get("form_id", ""), "count": 42}
        return {"capability": request.capability, "params": request.params}


__all__ = ["GoogleFormsConnector"]
