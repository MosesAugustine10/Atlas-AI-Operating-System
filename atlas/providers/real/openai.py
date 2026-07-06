"""Real OpenAI provider — makes actual HTTP calls to the OpenAI API.

When ``api_key`` is present, :meth:`generate` POSTs to the OpenAI Chat
Completions API and returns the real response. When ``api_key`` is
``None`` (the default in tests), it falls back to deterministic mode
so the pipeline always works.
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
    name="openai",
    display_name="OpenAI",
    base_url="https://api.openai.com/v1",
    priority=10,
    cost_per_1k=0.02,
    capabilities=ProviderCapability(
        streaming=True, tools=True, images=True, system_prompt=True
    ),
)


class RealOpenAIProvider(BaseProvider):
    """Production OpenAI provider.

    Parameters:
        api_key: Optional OpenAI API key. When present, :meth:`generate`
            makes a real HTTP call. When ``None``, the provider runs in
            deterministic mode (no network).
        base_url: Optional base URL override (for testing / proxies).
        model: Default model to use when ``request.model == "default"``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        super().__init__(info=_INFO, api_key=api_key)
        self._base_url = base_url or _INFO.base_url
        self._default_model = model

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self.api_key:
            return self._generate_real(request)
        return self._generate_fallback(request)

    def _generate_real(self, request: ProviderRequest) -> ProviderResponse:
        model = request.model if request.model != "default" else self._default_model
        messages = self._build_messages(request)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            data = http_post_json(
                f"{self._base_url}/chat/completions",
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
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "")
        usage = data.get("usage", {})
        return ProviderResponse(
            text=text,
            model=model,
            provider=self.name,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
        )

    def _generate_fallback(self, request: ProviderRequest) -> ProviderResponse:
        text = f"[openai:{request.model}] {request.prompt or self._last_user(request)}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 10, "completion": 5, "total": 15},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        # Real streaming would use SSE; for now, yield the full response
        # in word chunks to simulate streaming.
        full = self.generate(request)
        for word in full.text.split():
            yield ProviderResponse(
                text=word,
                model=full.model,
                provider=self.name,
                finish_reason="streaming",
            )

    def health(self) -> bool:
        if not self.api_key:
            return self._available
        try:
            # A lightweight models list call
            from atlas.providers.real._http import http_get_json

            http_get_json(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    def available_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(self, request: ProviderRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for msg in request.messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            messages.append({"role": role, "content": msg.content})
        if request.prompt and not messages:
            messages.append({"role": "user", "content": request.prompt})
        return messages

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if role == "user":
                return msg.content
        return ""


__all__ = ["RealOpenAIProvider"]
