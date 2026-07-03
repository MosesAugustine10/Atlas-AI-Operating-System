"""The Atlas Provider Layer.

A provider-agnostic abstraction over every LLM Atlas can talk to. Each
provider implements the :class:`BaseProvider` contract; the
:class:`ProviderManager` exposes a single high-level API (``generate``,
``chat``, ``complete``) that routes to the right provider via the
:class:`ProviderRouter` and :class:`ProviderRegistry`.

The dependency graph is acyclic:

* ``models`` — pure dataclasses (leaf).
* ``base`` — abstract provider contract.
* ``openai / anthropic / gemini / groq / nvidia / openrouter / ollama /
  lmstudio / zai`` — concrete provider placeholders.
* ``registry`` — catalog of providers.
* ``router`` — selection logic over the registry.
* ``manager`` — high-level facade over the router.
"""

from __future__ import annotations

from atlas.providers.anthropic import AnthropicProvider
from atlas.providers.base import BaseProvider
from atlas.providers.gemini import GeminiProvider
from atlas.providers.groq import GroqProvider
from atlas.providers.lmstudio import LMStudioProvider
from atlas.providers.manager import ProviderManager
from atlas.providers.models import (
    Message,
    MessageRole,
    ProviderCapability,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
)
from atlas.providers.nvidia import NvidiaProvider
from atlas.providers.ollama import OllamaProvider
from atlas.providers.openai import OpenAIProvider
from atlas.providers.openrouter import OpenRouterProvider
from atlas.providers.registry import ProviderRegistry
from atlas.providers.router import ProviderRouter, RoutingStrategy
from atlas.providers.zai import ZAIProvider

__all__ = [
    "AnthropicProvider",
    "BaseProvider",
    "GeminiProvider",
    "GroqProvider",
    "LMStudioProvider",
    "Message",
    "MessageRole",
    "NvidiaProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "ProviderCapability",
    "ProviderInfo",
    "ProviderManager",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRouter",
    "RoutingStrategy",
    "ZAIProvider",
]
