"""Ollama MCP connector — real implementation.

Talks to a local Ollama server (default ``http://localhost:11434``) via
its HTTP API. Supports health checks, model listing, pulling / deleting
models, generation, chat, and embeddings. Streaming is a placeholder
(returned as a single chunk).

Capabilities:

* ``ollama.health`` — ping the Ollama server.
* ``ollama.models`` — list installed models.
* ``ollama.pull`` — pull a model from the registry.
* ``ollama.delete`` — delete a local model.
* ``ollama.generate`` — generate text from a prompt.
* ``ollama.chat`` — multi-turn chat completion.
* ``ollama.embed`` — generate embeddings.
* ``ollama.stream`` — streaming generation (placeholder).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from atlas.mcp.base import BaseConnector
from atlas.mcp.connector_config import get_connector_config
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
    """Real Ollama MCP connector.

    Parameters:
        base_url: Ollama server URL. Defaults to the value in
            ``connectors.yaml`` (``ollama.base_url``), or
            ``http://localhost:11434``. Can be overridden via the
            ``OLLAMA_BASE_URL`` environment variable.
        timeout: Request timeout in seconds.
        default_model: Default model for generate / chat.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        default_model: str | None = None,
    ) -> None:
        cfg = get_connector_config("ollama")
        self.base_url = (
            base_url
            or os.environ.get(cfg.get("env_base_url", "OLLAMA_BASE_URL"))
            or cfg.get("base_url", "http://localhost:11434")
        )
        self.timeout = (
            timeout if timeout is not None else cfg.get("timeout_seconds", 60)
        )
        self.default_model = default_model or cfg.get("default_model", "llama3")
        self._available: bool | None = None
        super().__init__(
            name="ollama",
            description=(
                "Local LLM via Ollama (health, models, pull, delete, "
                "generate, chat, embed, stream)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="ollama.health",
                    description="Ping the Ollama server",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ollama.models",
                    description="List installed models",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="ollama.pull",
                    description="Pull a model",
                    permissions=("admin",),
                ),
                MCPCapability(
                    name="ollama.delete",
                    description="Delete a local model",
                    permissions=("admin",),
                ),
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
                    name="ollama.stream",
                    description="Streaming generation (placeholder)",
                    permissions=("read",),
                ),
            ),
            metadata={
                "base_url": self.base_url,
                "default_model": self.default_model,
                "timeout": self.timeout,
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _do_connect(self, transport: MCPTransport) -> None:
        """Probe the Ollama server on connect."""
        self._available = self._ping()

    def _do_disconnect(self) -> None:
        self._available = None

    def _do_health(self) -> MCPHealth:
        available = self._ping() if self._available is None else self._available
        status = MCPStatus.CONNECTED if available else MCPStatus.DEGRADED
        level = HealthLevel.HEALTHY if available else HealthLevel.WARNING
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=5.0 if available else None,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={"base_url": self.base_url, "available": available},
        )

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
        timeout: int | None = None,
    ) -> Any:
        """Make an HTTP request to the Ollama server."""
        import requests

        url = f"{self.base_url}{endpoint}"
        response = requests.request(
            method, url, json=json, timeout=timeout or self.timeout
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _ping(self) -> bool:
        """Return ``True`` if the Ollama server responds."""
        try:
            import requests

            requests.get(f"{self.base_url}/api/tags", timeout=5)
            return True
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        cap = request.capability
        params = request.params
        if cap == "ollama.health":
            return self._health(params)
        if cap == "ollama.models":
            return self._list_models(params)
        if cap == "ollama.pull":
            return self._pull_model(params)
        if cap == "ollama.delete":
            return self._delete_model(params)
        if cap == "ollama.generate":
            return self._generate(params)
        if cap == "ollama.chat":
            return self._chat(params)
        if cap == "ollama.embed":
            return self._embed(params)
        if cap == "ollama.stream":
            return self._stream(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    def _health(self, params: dict[str, Any]) -> dict[str, Any]:
        available = self._ping()
        return {"base_url": self.base_url, "available": available}

    def _list_models(self, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        data = self._request("GET", "/api/tags")
        models = [m["name"] for m in data.get("models", [])]
        return {"models": models, "count": len(models)}

    def _pull_model(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name") or params.get("model", "")
        if not name:
            raise ValueError("missing 'name' or 'model' parameter")
        # Pull is a streaming endpoint; we send the request and ignore
        # the stream.
        import requests

        response = requests.post(
            f"{self.base_url}/api/pull",
            json={"name": name},
            timeout=self.timeout,
            stream=True,
        )
        response.raise_for_status()
        # Consume the stream.
        for _ in response.iter_lines():
            pass
        return {"model": name, "pulled": True}

    def _delete_model(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name") or params.get("model", "")
        if not name:
            raise ValueError("missing 'name' or 'model' parameter")
        self._request("DELETE", "/api/delete", json={"name": name})
        return {"model": name, "deleted": True}

    def _generate(self, params: dict[str, Any]) -> dict[str, Any]:
        model = params.get("model", self.default_model)
        prompt = params.get("prompt", "")
        if not prompt:
            raise ValueError("missing 'prompt' parameter")
        data = self._request(
            "POST",
            "/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": params.get("options", {}),
            },
        )
        return {
            "model": model,
            "response": data.get("response", ""),
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_duration_ns": data.get("total_duration", 0),
            },
        }

    def _chat(self, params: dict[str, Any]) -> dict[str, Any]:
        model = params.get("model", self.default_model)
        messages = params.get("messages", [])
        if not messages:
            raise ValueError("missing 'messages' parameter")
        data = self._request(
            "POST",
            "/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": params.get("options", {}),
            },
        )
        message = data.get("message", {})
        return {
            "model": model,
            "message": message,
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        }

    def _embed(self, params: dict[str, Any]) -> dict[str, Any]:
        model = params.get("model", "nomic-embed-text")
        input_text = params.get("input") or params.get("text", "")
        if not input_text:
            raise ValueError("missing 'input' or 'text' parameter")
        data = self._request(
            "POST",
            "/api/embeddings",
            json={"model": model, "prompt": input_text},
        )
        return {"model": model, "embedding": data.get("embedding", [])}

    def _stream(self, params: dict[str, Any]) -> dict[str, Any]:
        """Placeholder — returns the full generation as a single chunk."""
        result = self._generate(params)
        return {
            "model": result["model"],
            "chunks": [result["response"]],
            "done": True,
        }


__all__ = ["OllamaConnector"]
