"""Google Gemini provider placeholder.

Wraps the Gemini API behind the :class:`BaseProvider` contract. Returns
deterministic fake responses — no network calls are made.
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
    name="gemini",
    display_name="Google Gemini",
    base_url="https://generativelanguage.googleapis.com/v1",
    priority=20,
    cost_per_1k=0.01,
    capabilities=ProviderCapability(
        streaming=True, tools=True, images=True, system_prompt=True
    ),
)


class GeminiProvider(BaseProvider):
    """Placeholder Gemini provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        text = f"[gemini:{request.model}] {request.prompt or self._last_user(request)}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 9, "completion": 4, "total": 13},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        text = f"[gemini:{request.model}] {request.prompt or self._last_user(request)}"
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
        return ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
