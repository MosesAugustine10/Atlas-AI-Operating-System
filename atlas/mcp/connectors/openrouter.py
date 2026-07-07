"""OpenRouter MCP connector — real implementation.

Talks to the OpenRouter multi-model LLM gateway via its REST API. The
API key is read from the ``OPENROUTER_API_KEY`` environment variable
(configured in ``connectors.yaml``).

Capabilities:

* ``openrouter.health`` — ping the OpenRouter API.
* ``openrouter.models`` — list available models.
* ``openrouter.chat`` — chat completion.
* ``openrouter.generate`` — text completion.
* ``openrouter.usage`` — usage metadata.
"""

from __future__ import annotations

import os
import time
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


class OpenRouterConnector(BaseConnector):
    """Real OpenRouter MCP connector.

    Parameters:
        api_key: OpenRouter API key. If ``None``, reads from the
            ``OPENROUTER_API_KEY`` environment variable.
        api_base: OpenRouter API base URL.
        default_model: Default model for completions.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retries on 429 / 5xx.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        cfg = get_connector_config("openrouter")
        self.api_key = api_key or os.environ.get(
            cfg.get("api_key_env", "OPENROUTER_API_KEY")
        )
        self.api_base = api_base or cfg.get("api_base", "https://openrouter.ai/api/v1")
        self.default_model = default_model or cfg.get(
            "default_model", "openai/gpt-4o-mini"
        )
        self.timeout = (
            timeout if timeout is not None else cfg.get("timeout_seconds", 60)
        )
        self.max_retries = (
            max_retries if max_retries is not None else cfg.get("max_retries", 3)
        )
        self._available: bool | None = None
        super().__init__(
            name="openrouter",
            description=(
                "Multi-model LLM gateway via OpenRouter (health, models, "
                "chat, generate, usage)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="openrouter.health",
                    description="Ping the OpenRouter API",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="openrouter.models",
                    description="List available models",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="openrouter.chat",
                    description="Chat completion",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="openrouter.generate",
                    description="Text completion",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="openrouter.usage",
                    description="Usage metadata",
                    permissions=("read",),
                ),
            ),
            metadata={
                "api_base": self.api_base,
                "has_api_key": self.api_key is not None,
                "default_model": self.default_model,
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _do_connect(self, transport: MCPTransport) -> None:
        self._available = self.api_key is not None

    def _do_disconnect(self) -> None:
        self._available = None

    def _do_health(self) -> MCPHealth:
        available = self.api_key is not None
        status = MCPStatus.CONNECTED if available else MCPStatus.DEGRADED
        level = HealthLevel.HEALTHY if available else HealthLevel.WARNING
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=None,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={"has_api_key": available},
        )

    # ------------------------------------------------------------------
    # HTTP helper with retry
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
    ) -> Any:
        """Make an authenticated OpenRouter API request with retry."""
        import requests

        if not self.api_key:
            raise PermissionError(
                "OpenRouter API key required — set OPENROUTER_API_KEY env var"
            )
        url = f"{self.api_base}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method, url, headers=headers, json=json, timeout=self.timeout
                )
                if response.status_code == 429:
                    # Rate limited — wait and retry.
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if response.status_code >= 500:
                    # Server error — retry.
                    last_error = RuntimeError(
                        f"server error {response.status_code}: {response.text}"
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json() if response.content else {}
            except requests.exceptions.Timeout as exc:
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
            except requests.exceptions.RequestException as exc:
                last_error = exc
                break
        raise RuntimeError(
            f"request failed after {self.max_retries} retries: {last_error}"
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        cap = request.capability
        params = request.params
        if cap == "openrouter.health":
            return self._health(params)
        if cap == "openrouter.models":
            return self._list_models(params)
        if cap == "openrouter.chat":
            return self._chat(params)
        if cap == "openrouter.generate":
            return self._generate(params)
        if cap == "openrouter.usage":
            return self._usage(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    def _health(self, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        return {"available": self.api_key is not None, "api_base": self.api_base}

    def _list_models(self, params: dict[str, Any]) -> dict[str, Any]:
        data = self._request("GET", "/models")
        models = [m["id"] for m in data.get("data", [])]
        return {"models": models, "count": len(models)}

    def _chat(self, params: dict[str, Any]) -> dict[str, Any]:
        model = params.get("model", self.default_model)
        messages = params.get("messages", [])
        if not messages:
            raise ValueError("missing 'messages' parameter")
        data = self._request(
            "POST",
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": params.get("temperature", 0.7),
                "max_tokens": params.get("max_tokens", 1024),
            },
        )
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        return {
            "model": model,
            "message": message,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }

    def _generate(self, params: dict[str, Any]) -> dict[str, Any]:
        model = params.get("model", self.default_model)
        prompt = params.get("prompt", "")
        if not prompt:
            raise ValueError("missing 'prompt' parameter")
        data = self._request(
            "POST",
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": params.get("temperature", 0.7),
                "max_tokens": params.get("max_tokens", 1024),
            },
        )
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        return {
            "model": model,
            "response": message.get("content", ""),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }

    def _usage(self, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        data = self._request("GET", "/key")
        return {
            "limit": data.get("limit", 0),
            "usage": data.get("usage", 0),
            "limit_remaining": data.get("limit_remaining", 0),
        }


__all__ = ["OpenRouterConnector"]
