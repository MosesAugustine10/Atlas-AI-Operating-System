"""OpenRouter provider placeholder.

OpenRouter is a meta-provider that routes requests across many underlying
models through a single API. Wrapped behind the :class:`BaseProvider`
contract with deterministic fake responses — no network calls are made.
"""

from __future__ import annotations

from collections.abc import Iterator

from atlas.providers.base import BaseProvider
from atlas.providers.models import (
    ProviderCapability,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
)

_INFO = ProviderInfo(
    name="openrouter",
    display_name="OpenRouter",
    base_url="https://openrouter.ai/api/v1",
    priority=40,
    cost_per_1k=0.015,
    capabilities=ProviderCapability(
        streaming=True, tools=True, images=False, system_prompt=True
    ),
)


class OpenRouterProvider(BaseProvider):
    """Placeholder OpenRouter provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        prompt_text = request.prompt or self._last_user(request)
        text = f"[openrouter:{request.model}] {prompt_text}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 11, "completion": 5, "total": 16},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        prompt_text = request.prompt or self._last_user(request)
        text = f"[openrouter:{request.model}] {prompt_text}"
        for word in text.split():
            yield ProviderResponse(
                text=word,
                model=request.model,
                provider=self.name,
                finish_reason="streaming",
            )

    def health(self) -> bool:
        return self._available

    def available_models(self) -> list[str]:
        return ["auto", "openai/gpt-4o", "anthropic/claude-3.5-sonnet"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
