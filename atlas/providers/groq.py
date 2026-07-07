"""Groq provider placeholder.

Wraps the Groq ultra-low-latency inference API behind the
:class:`BaseProvider` contract. Returns deterministic fake responses — no
network calls are made.
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
    name="groq",
    display_name="Groq",
    base_url="https://api.groq.com/openai/v1",
    priority=25,
    cost_per_1k=0.005,
    capabilities=ProviderCapability(
        streaming=True, tools=True, images=False, system_prompt=True
    ),
)


class GroqProvider(BaseProvider):
    """Placeholder Groq provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        text = f"[groq:{request.model}] {request.prompt or self._last_user(request)}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 8, "completion": 4, "total": 12},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        text = f"[groq:{request.model}] {request.prompt or self._last_user(request)}"
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
        return ["llama-3.3-70b", "llama-3.1-8b", "mixtral-8x7b"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
