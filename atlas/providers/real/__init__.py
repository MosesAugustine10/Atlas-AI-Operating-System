"""Real HTTP-calling provider implementations.

This package contains production provider implementations that make
actual HTTP calls to LLM APIs. Each provider activates real HTTP mode
when an API key is present and falls back to deterministic mode when
no key is available — so the pipeline always works in tests and on
air-gapped hosts.

Supported providers:

* :class:`RealOpenAIProvider` — OpenAI Chat Completions API.
* :class:`RealAnthropicProvider` — Anthropic Messages API.
* :class:`RealGeminiProvider` — Google Gemini Generate Content API.
* :class:`RealOpenRouterProvider` — OpenRouter Chat Completions API.
* :class:`RealOllamaProvider` — Ollama local API.
* :class:`RealZAIProvider` — Z.ai GLM API.

All providers use :mod:`urllib` (no third-party HTTP dependencies) and
follow the :class:`~atlas.providers.base.BaseProvider` contract.
"""

from __future__ import annotations

from atlas.providers.real.anthropic import RealAnthropicProvider
from atlas.providers.real.gemini import RealGeminiProvider
from atlas.providers.real.ollama import RealOllamaProvider
from atlas.providers.real.openai import RealOpenAIProvider
from atlas.providers.real.openrouter import RealOpenRouterProvider
from atlas.providers.real.zai import RealZAIProvider

__all__ = [
    "RealAnthropicProvider",
    "RealGeminiProvider",
    "RealOllamaProvider",
    "RealOpenAIProvider",
    "RealOpenRouterProvider",
    "RealZAIProvider",
]
