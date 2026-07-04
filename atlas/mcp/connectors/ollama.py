"""Ollama MCP connector — deterministic placeholder."""

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


class OllamaConnector(BaseConnector):
    """Deterministic placeholder Ollama MCP connector.

    Ollama is a local LLM runtime. A real implementation would call the
    Ollama HTTP API; the placeholder returns deterministic responses.
    """

    def __init__(self) -> None:
        super().__init__(
            name="ollama",
            description="Local LLM via Ollama (generate, chat, embed)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="ollama.generate",
                    description="Generate text",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ollama.chat",
                    description="Chat completion",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ollama.embed",
                    description="Generate embeddings",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ollama.models",
                    description="List available models",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ollama.pull",
                    description="Pull a model",
                    permissions=("admin",),
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
            latency_ms=300.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "ollama.generate":
            return {
                "model": request.params.get("model", "llama3"),
                "response": (
                    f"placeholder response for: "
                    f"{request.params.get('prompt', '')[:50]}"
                ),
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        if request.capability == "ollama.chat":
            return {
                "model": request.params.get("model", "llama3"),
                "message": {
                    "role": "assistant",
                    "content": "placeholder chat response",
                },
                "usage": {"prompt_tokens": 15, "completion_tokens": 25},
            }
        if request.capability == "ollama.embed":
            return {
                "model": request.params.get("model", "nomic-embed-text"),
                "embedding": [0.1] * 128,
            }
        if request.capability == "ollama.models":
            return {"models": ["llama3", "mistral", "phi3"]}
        if request.capability == "ollama.pull":
            return {"model": request.params.get("model", ""), "pulled": True}
        return {"capability": request.capability, "params": request.params}


__all__ = ["OllamaConnector"]
