"""OpenRouter MCP connector — deterministic placeholder."""

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


class OpenRouterConnector(BaseConnector):
    """Deterministic placeholder OpenRouter MCP connector.

    OpenRouter is a multi-model LLM gateway. A real implementation
    would call the OpenRouter HTTP API; the placeholder returns
    deterministic responses.
    """

    def __init__(self) -> None:
        super().__init__(
            name="openrouter",
            description="Multi-model LLM gateway (generate, chat, list models)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="openrouter.generate",
                    description="Generate text",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="openrouter.chat",
                    description="Chat completion",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="openrouter.models",
                    description="List available models",
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
            latency_ms=400.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "openrouter.generate":
            return {
                "model": request.params.get("model", "openai/gpt-4"),
                "response": (
                    f"placeholder response for: "
                    f"{request.params.get('prompt', '')[:50]}"
                ),
                "usage": {"prompt_tokens": 12, "completion_tokens": 22},
            }
        if request.capability == "openrouter.chat":
            return {
                "model": request.params.get("model", "openai/gpt-4"),
                "message": {
                    "role": "assistant",
                    "content": "placeholder chat response",
                },
                "usage": {"prompt_tokens": 18, "completion_tokens": 28},
            }
        if request.capability == "openrouter.models":
            return {
                "models": ["openai/gpt-4", "anthropic/claude-3", "google/gemini-pro"]
            }
        return {"capability": request.capability, "params": request.params}


__all__ = ["OpenRouterConnector"]
