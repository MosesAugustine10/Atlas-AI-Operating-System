"""NVIDIA NIM provider placeholder.

Wraps the NVIDIA NIM inference API behind the :class:`BaseProvider`
contract. Returns deterministic fake responses — no network calls are made.
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
    name="nvidia",
    display_name="NVIDIA NIM",
    base_url="https://integrate.api.nvidia.com/v1",
    priority=30,
    cost_per_1k=0.008,
    capabilities=ProviderCapability(
        streaming=True, tools=False, images=False, system_prompt=True
    ),
)


class NvidiaProvider(BaseProvider):
    """Placeholder NVIDIA NIM provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        text = f"[nvidia:{request.model}] {request.prompt or self._last_user(request)}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 7, "completion": 3, "total": 10},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        text = f"[nvidia:{request.model}] {request.prompt or self._last_user(request)}"
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
        return ["nemotron-70b", "llama-3.1-nemotron", "mistral-nemo"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
