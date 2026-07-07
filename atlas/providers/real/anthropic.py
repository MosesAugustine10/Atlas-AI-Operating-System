"""Real Anthropic provider — makes actual HTTP calls.

When ``api_key`` is present (or the service is reachable for local
providers), :meth:`generate` makes a real HTTP call. When no key is
available, it falls back to deterministic mode.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from atlas.providers.base import BaseProvider
from atlas.providers.models import (
    ProviderCapability,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
)
from atlas.providers.real._http import ProviderHTTPError, http_post_json

_INFO = ProviderInfo(
    name="anthropic",
    display_name="Anthropic",
    base_url="https://api.anthropic.com/v1",
    priority=20,
    cost_per_1k=0.01,
    capabilities=ProviderCapability(
        streaming=True, tools=True, images=False, system_prompt=True
    ),
)


class RealAnthropicProvider(BaseProvider):
    """Production Anthropic provider.

    Parameters:
        api_key: Optional API key. When present, :meth:`generate` makes
            a real HTTP call. When ``None``, the provider runs in
            deterministic mode.
        base_url: Optional base URL override.
        model: Default model to use when ``request.model == "default"``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        super().__init__(info=_INFO, api_key=api_key)
        self._base_url = base_url or _INFO.base_url
        self._default_model = model

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self.api_key:
            return self._generate_real(request)
        return self._generate_fallback(request)

    def _generate_real(self, request: ProviderRequest) -> ProviderResponse:
        model = request.model if request.model != "default" else self._default_model
        payload = self._build_payload(request, model)
        headers = self._build_headers()
        try:
            data = http_post_json(
                self._endpoint(model),
                payload,
                headers=headers,
            )
        except ProviderHTTPError as exc:
            return ProviderResponse(
                text="",
                model=model,
                provider=self.name,
                finish_reason="error",
                usage={},
                metadata={"error": str(exc), "error_status": exc.status},
            )
        return self._parse_response(data, model)

    def _generate_fallback(self, request: ProviderRequest) -> ProviderResponse:
        text = (
            f"[anthropic:{request.model}] {request.prompt or self._last_user(request)}"
        )
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 10, "completion": 5, "total": 15},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        full = self.generate(request)
        for word in full.text.split():
            yield ProviderResponse(
                text=word,
                model=full.model,
                provider=self.name,
                finish_reason="streaming",
            )

    def health(self) -> bool:
        return self._available

    def available_models(self) -> list[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]

    # ------------------------------------------------------------------
    # Provider-specific payload / parsing
    # ------------------------------------------------------------------

    def _build_payload(self, request: ProviderRequest, model: str) -> dict[str, Any]:
        messages = []
        system_content = ""
        for msg in request.messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if role == "system":
                system_content = msg.content
                continue
            messages.append({"role": role, "content": msg.content})
        if request.prompt and not messages:
            messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_content:
            payload["system"] = system_content
        return payload

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }

    def _endpoint(self, model: str) -> str:
        return f"{self._base_url}/messages"

    def _parse_response(self, data: dict[str, Any], model: str) -> ProviderResponse:
        content = data.get("content", [{}])
        text = content[0].get("text", "") if content else ""
        usage = data.get("usage", {})
        return ProviderResponse(
            text=text,
            model=model,
            provider=self.name,
            finish_reason=data.get("stop_reason", "stop"),
            usage=usage,
        )

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if role == "user":
                return msg.content
        return ""


__all__ = ["RealAnthropicProvider"]
