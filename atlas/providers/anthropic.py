"""Anthropic provider placeholder.

Wraps the Anthropic Messages API behind the :class:`BaseProvider` contract.
Returns deterministic fake responses — no network calls are made.
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
    name="anthropic",
    display_name="Anthropic",
    base_url="https://api.anthropic.com/v1",
    priority=15,
    cost_per_1k=0.03,
    capabilities=ProviderCapability(
        streaming=True, tools=True, images=True, system_prompt=True
    ),
)


class AnthropicProvider(BaseProvider):
    """Placeholder Anthropic provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        prompt_text = request.prompt or self._last_user(request)
        text = f"[anthropic:{request.model}] {prompt_text}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 12, "completion": 6, "total": 18},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        prompt_text = request.prompt or self._last_user(request)
        text = f"[anthropic:{request.model}] {prompt_text}"
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
        return ["claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-opus"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
