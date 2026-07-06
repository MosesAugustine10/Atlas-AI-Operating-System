"""Tests for the Atlas Provider Layer.

Covers models, registry, router, manager, every provider placeholder,
fallback, unavailable providers, duplicate registration, and health checks.
"""

from __future__ import annotations

import pytest

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

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_message_roles() -> None:
    assert MessageRole.SYSTEM.value == "system"
    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.TOOL.value == "tool"


def test_message_construction() -> None:
    msg = Message(role=MessageRole.USER, content="hi", name="tester")
    assert msg.role is MessageRole.USER
    assert msg.content == "hi"
    assert msg.name == "tester"


def test_capability_defaults() -> None:
    cap = ProviderCapability()
    assert cap.streaming is False
    assert cap.tools is False
    assert cap.images is False
    assert cap.system_prompt is True


def test_provider_info_defaults() -> None:
    info = ProviderInfo(name="x", display_name="X")
    assert info.name == "x"
    assert info.priority == 100
    assert info.cost_per_1k == 0.0


def test_request_defaults() -> None:
    req = ProviderRequest()
    assert req.model == "default"
    assert req.temperature == 0.7
    assert req.max_tokens == 1024
    assert req.id
    assert req.created_at


def test_request_uuid_unique() -> None:
    a = ProviderRequest()
    b = ProviderRequest()
    assert a.id != b.id


def test_response_construction() -> None:
    resp = ProviderResponse(text="hi", model="m", provider="p")
    assert resp.text == "hi"
    assert resp.finish_reason == "stop"
    assert resp.id


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_register_and_get() -> None:
    reg = ProviderRegistry()
    p = OpenAIProvider()
    reg.register(p)
    assert reg.contains("openai")
    assert reg.get("openai") is p
    assert len(reg) == 1


def test_registry_default_is_first() -> None:
    reg = ProviderRegistry()
    first = OpenAIProvider()
    reg.register(first)
    reg.register(AnthropicProvider())
    assert reg.default() is first


def test_registry_make_default() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    reg.register(AnthropicProvider(), make_default=True)
    assert reg.default().name == "anthropic"


def test_registry_set_default_unknown_raises() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    with pytest.raises(KeyError):
        reg.set_default("nope")


def test_registry_duplicate_raises() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(OpenAIProvider())


def test_registry_unregister() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    reg.unregister("openai")
    assert not reg.contains("openai")
    assert reg.default() is None


def test_registry_names_sorted() -> None:
    reg = ProviderRegistry()
    reg.register(ZAIProvider())
    reg.register(OpenAIProvider())
    assert reg.names() == ["openai", "zai"]


def test_registry_get_unknown_returns_none() -> None:
    reg = ProviderRegistry()
    assert reg.get("missing") is None


# ---------------------------------------------------------------------------
# Router — auto, manual, fallback, round_robin
# ---------------------------------------------------------------------------


def test_router_auto_selects_lowest_priority() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())  # priority 10 (lowest = highest priority)
    reg.register(ZAIProvider())  # priority 20
    router = ProviderRouter(reg)
    selected = router.select()
    assert selected.name == "openai"


def test_router_auto_skips_unavailable() -> None:
    reg = ProviderRegistry()
    oai = OpenAIProvider()
    oai.set_available(False)
    zai = ZAIProvider()
    reg.register(zai)
    reg.register(oai)
    router = ProviderRouter(reg)
    selected = router.select()
    assert selected.name == "zai"


def test_router_auto_none_when_all_unavailable() -> None:
    reg = ProviderRegistry()
    zai = ZAIProvider()
    zai.set_available(False)
    reg.register(zai)
    router = ProviderRouter(reg)
    assert router.select() is None


def test_router_manual_selects_named() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    reg.register(AnthropicProvider())
    router = ProviderRouter(reg)
    selected = router.select(strategy=RoutingStrategy.MANUAL, name="anthropic")
    assert selected.name == "anthropic"


def test_router_manual_requires_name() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    router = ProviderRouter(reg)
    with pytest.raises(ValueError):
        router.select(strategy=RoutingStrategy.MANUAL)


def test_router_manual_unknown_returns_none() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    router = ProviderRouter(reg)
    assert router.select(strategy=RoutingStrategy.MANUAL, name="ghost") is None


def test_router_fallback_first_available() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    reg.register(AnthropicProvider())
    router = ProviderRouter(reg)
    selected = router.select(
        strategy=RoutingStrategy.FALLBACK, fallback=["groq", "anthropic"]
    )
    assert selected.name == "anthropic"


def test_router_fallback_none_when_all_missing() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    router = ProviderRouter(reg)
    assert router.select(strategy=RoutingStrategy.FALLBACK, fallback=["groq"]) is None


def test_router_capability_filter() -> None:
    reg = ProviderRegistry()
    reg.register(OllamaProvider())  # tools=False
    reg.register(OpenAIProvider())  # tools=True
    router = ProviderRouter(reg)
    selected = router.select(require=ProviderCapability(tools=True))
    assert selected.name == "openai"


def test_router_capability_images() -> None:
    reg = ProviderRegistry()
    reg.register(GroqProvider())  # images=False
    reg.register(OpenAIProvider())  # images=True
    router = ProviderRouter(reg)
    selected = router.select(require=ProviderCapability(images=True))
    assert selected.name == "openai"


def test_router_round_robin_rotates() -> None:
    reg = ProviderRegistry()
    reg.register(OpenAIProvider())
    reg.register(AnthropicProvider())
    router = ProviderRouter(reg, strategy=RoutingStrategy.ROUND_ROBIN)
    first = router.select()
    second = router.select()
    assert first.name != second.name


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


def test_manager_generate() -> None:
    mgr = ProviderManager()
    mgr.register(ZAIProvider(), make_default=True)
    resp = mgr.generate("Hello")
    assert resp.provider == "zai"
    assert "Hello" in resp.text


def test_manager_chat() -> None:
    mgr = ProviderManager()
    mgr.register(OpenAIProvider(), make_default=True)
    msgs = [Message(role=MessageRole.USER, content="Hi there")]
    resp = mgr.chat(msgs)
    assert "Hi there" in resp.text
    assert resp.provider == "openai"


def test_manager_complete_alias() -> None:
    mgr = ProviderManager()
    mgr.register(ZAIProvider(), make_default=True)
    resp = mgr.complete("test prompt")
    assert "test prompt" in resp.text


def test_manager_generate_explicit_provider() -> None:
    mgr = ProviderManager()
    mgr.register(ZAIProvider())
    mgr.register(OpenAIProvider())
    resp = mgr.generate("x", provider="openai")
    assert resp.provider == "openai"


def test_manager_no_provider_raises() -> None:
    mgr = ProviderManager()
    with pytest.raises(RuntimeError):
        mgr.generate("x")


def test_manager_health() -> None:
    mgr = ProviderManager()
    mgr.register(ZAIProvider())
    mgr.register(OpenAIProvider())
    health = mgr.health()
    assert health == {"openai": True, "zai": True}


def test_manager_health_reflects_unavailable() -> None:
    mgr = ProviderManager()
    zai = ZAIProvider()
    zai.set_available(False)
    mgr.register(zai)
    mgr.register(OpenAIProvider())
    health = mgr.health()
    assert health["zai"] is False
    assert health["openai"] is True


def test_manager_list_models_all() -> None:
    mgr = ProviderManager()
    mgr.register(ZAIProvider())
    mgr.register(OllamaProvider())
    models = mgr.list_models()
    assert "glm-4-plus" in models["zai"]
    assert "llama3.2" in models["ollama"]


def test_manager_list_models_single() -> None:
    mgr = ProviderManager()
    mgr.register(ZAIProvider())
    models = mgr.list_models(provider="zai")
    assert "zai" in models
    assert len(models) == 1


# ---------------------------------------------------------------------------
# Every provider placeholder — generate, stream, health, models
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "provider_cls",
    [
        OpenAIProvider,
        AnthropicProvider,
        GeminiProvider,
        GroqProvider,
        NvidiaProvider,
        OpenRouterProvider,
        OllamaProvider,
        LMStudioProvider,
        ZAIProvider,
    ],
)
def test_provider_generate_returns_response(provider_cls: type[BaseProvider]) -> None:
    provider = provider_cls()
    resp = provider.generate(ProviderRequest(prompt="hello"))
    assert isinstance(resp, ProviderResponse)
    assert resp.provider == provider.name
    assert "hello" in resp.text


@pytest.mark.parametrize(
    "provider_cls",
    [
        OpenAIProvider,
        AnthropicProvider,
        GeminiProvider,
        GroqProvider,
        NvidiaProvider,
        OpenRouterProvider,
        OllamaProvider,
        LMStudioProvider,
        ZAIProvider,
    ],
)
def test_provider_stream_yields_chunks(provider_cls: type[BaseProvider]) -> None:
    provider = provider_cls()
    chunks = list(provider.stream(ProviderRequest(prompt="hello world")))
    assert len(chunks) >= 2
    assert all(c.provider == provider.name for c in chunks)


@pytest.mark.parametrize(
    "provider_cls",
    [
        OpenAIProvider,
        AnthropicProvider,
        GeminiProvider,
        GroqProvider,
        NvidiaProvider,
        OpenRouterProvider,
        OllamaProvider,
        LMStudioProvider,
        ZAIProvider,
    ],
)
def test_provider_health(provider_cls: type[BaseProvider]) -> None:
    provider = provider_cls()
    assert provider.health() is True
    provider.set_available(False)
    assert provider.health() is False


@pytest.mark.parametrize(
    "provider_cls",
    [
        OpenAIProvider,
        AnthropicProvider,
        GeminiProvider,
        GroqProvider,
        NvidiaProvider,
        OpenRouterProvider,
        OllamaProvider,
        LMStudioProvider,
        ZAIProvider,
    ],
)
def test_provider_available_models_nonempty(provider_cls: type[BaseProvider]) -> None:
    provider = provider_cls()
    assert len(provider.available_models()) > 0


@pytest.mark.parametrize(
    "provider_cls,expected_name",
    [
        (OpenAIProvider, "openai"),
        (AnthropicProvider, "anthropic"),
        (GeminiProvider, "gemini"),
        (GroqProvider, "groq"),
        (NvidiaProvider, "nvidia"),
        (OpenRouterProvider, "openrouter"),
        (OllamaProvider, "ollama"),
        (LMStudioProvider, "lmstudio"),
        (ZAIProvider, "zai"),
    ],
)
def test_provider_name(provider_cls: type[BaseProvider], expected_name: str) -> None:
    assert provider_cls().name == expected_name


def test_chat_messages_extracted() -> None:
    """Provider should use the last user message when prompt is empty."""
    provider = ZAIProvider()
    msgs = [
        Message(role=MessageRole.SYSTEM, content="be nice"),
        Message(role=MessageRole.USER, content="user text"),
    ]
    resp = provider.generate(ProviderRequest(messages=msgs))
    assert "user text" in resp.text


# ---------------------------------------------------------------------------
# Fallback flow through the manager
# ---------------------------------------------------------------------------


def test_manager_fallback_via_router() -> None:
    """When default is unavailable, auto routing picks another provider."""
    mgr = ProviderManager()
    zai = ZAIProvider()
    zai.set_available(False)
    mgr.register(zai, make_default=True)
    mgr.register(OpenAIProvider())
    resp = mgr.generate("hello")
    assert resp.provider == "openai"


def test_manager_all_unavailable_raises() -> None:
    mgr = ProviderManager(max_retries=1)
    zai = ZAIProvider()
    zai.set_available(False)
    mgr.register(zai)
    with pytest.raises(RuntimeError):
        mgr.generate("hello")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_provider_generate_is_deterministic() -> None:
    provider = ZAIProvider()
    a = provider.generate(ProviderRequest(prompt="same"))
    b = provider.generate(ProviderRequest(prompt="same"))
    assert a.text == b.text
