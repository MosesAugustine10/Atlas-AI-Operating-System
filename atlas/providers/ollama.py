"""Ollama provider placeholder.

Ollama runs models locally — a key path for Atlas's future "local AI"
support. Wrapped behind the :class:`BaseProvider` contract with
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
    name="ollama",
    display_name="Ollama (local)",
    base_url="http://localhost:11434",
    priority=50,
    cost_per_1k=0.0,
    capabilities=ProviderCapability(
        streaming=True, tools=False, images=False, system_prompt=True
    ),
)


class OllamaProvider(BaseProvider):
    """Placeholder Ollama (local) provider.

    .. note::
        Deterministic fake responses only — no external API calls.
    """

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(info=_INFO, api_key=api_key)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        text = f"[ollama:{request.model}] {request.prompt or self._last_user(request)}"
        return ProviderResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage={"prompt": 6, "completion": 3, "total": 9},
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        text = f"[ollama:{request.model}] {request.prompt or self._last_user(request)}"
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
        return ["llama3.2", "qwen2.5", "phi3", "mistral"]

    @staticmethod
    def _last_user(request: ProviderRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                return msg.content
        return ""
