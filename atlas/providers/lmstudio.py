"""LM Studio provider placeholder.

LM Studio runs local models via an OpenAI-compatible server. Wrapped
behind the :class:`BaseProvider` contract with deterministic fake
responses — no network calls are made.
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
    name="lmstudio",
    display_name="LM Studio (local)",
    base_url="http://localhost:1234/v1",
    priority=55,
    cost_per_1k=0.0,
    capabilities=ProviderCapability(
        streaming=True, tools=False, images=False, system_prompt=True
    ),
)


class LMStudioProvider(BaseProvider):
    """Placeholder LM Studio (local) provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        prompt_text = request.prompt or self._last_user(request)
        text = f"[lmstudio:{request.model}] {prompt_text}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 5, "completion": 2, "total": 7},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        prompt_text = request.prompt or self._last_user(request)
        text = f"[lmstudio:{request.model}] {prompt_text}"
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
        return ["local-model", "qwen2.5-7b", "llama-3.1-8b"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
