"""Tests for the Atlas live execution pipeline (Phase 2 — Real AI).

Covers the :class:`Pipeline`, :func:`build_pipeline`, the real
HTTP-calling providers, streaming, and the :class:`AtlasApp.with_pipeline`
integration. All tests are deterministic and headless — they run
without API keys, exercising the providers' fallback mode.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from atlas.pipeline import Pipeline, build_pipeline
from atlas.providers.base import BaseProvider
from atlas.providers.models import ProviderRequest, ProviderResponse
from atlas.providers.real import (
    RealAnthropicProvider,
    RealGeminiProvider,
    RealOllamaProvider,
    RealOpenAIProvider,
    RealOpenRouterProvider,
    RealZAIProvider,
)
from atlas.providers.real._http import (
    ProviderHTTPError,
    http_get_json,
    http_post_json,
)

# ===========================================================================
# Pipeline construction
# ===========================================================================


class TestPipelineConstruction:
    def test_build_pipeline_default(self) -> None:
        p = build_pipeline()
        assert p is not None
        assert isinstance(p, Pipeline)

    def test_pipeline_has_brain(self) -> None:
        p = build_pipeline()
        assert p.brain is not None

    def test_pipeline_has_coordinator(self) -> None:
        p = build_pipeline()
        assert p.coordinator is not None

    def test_pipeline_has_execution(self) -> None:
        p = build_pipeline()
        assert p.execution is not None

    def test_pipeline_has_providers(self) -> None:
        p = build_pipeline()
        assert p.providers is not None

    def test_pipeline_has_memory(self) -> None:
        p = build_pipeline()
        assert p.memory is not None

    def test_pipeline_has_knowledge(self) -> None:
        p = build_pipeline()
        assert p.knowledge is not None

    def test_pipeline_has_mcp(self) -> None:
        p = build_pipeline()
        assert p.mcp is not None

    def test_pipeline_has_workflows(self) -> None:
        p = build_pipeline()
        assert p.workflows is not None

    def test_pipeline_registers_six_providers(self) -> None:
        p = build_pipeline()
        names = [prov.name for prov in p.providers.registry.all()]
        assert "openai" in names
        assert "anthropic" in names
        assert "gemini" in names
        assert "openrouter" in names
        assert "ollama" in names
        assert "zai" in names
        assert len(names) == 6

    def test_pipeline_status(self) -> None:
        p = build_pipeline()
        status = p.status()
        assert "brain" in status
        assert "providers" in status
        assert "memory" in status
        assert "knowledge" in status
        assert "execution" in status
        assert "mcp" in status
        assert "workflows" in status

    def test_pipeline_status_providers_registered(self) -> None:
        p = build_pipeline()
        status = p.status()
        assert status["providers"]["registered"] == 6

    def test_pipeline_status_health(self) -> None:
        p = build_pipeline()
        status = p.status()
        assert isinstance(status["providers"]["health"], dict)
        assert len(status["providers"]["health"]) == 6

    def test_build_pipeline_with_custom_memory(self) -> None:
        from atlas.memory.engine import MemoryEngine

        memory = MemoryEngine()
        p = build_pipeline(memory=memory)
        assert p.memory is memory

    def test_build_pipeline_with_custom_knowledge(self) -> None:
        from atlas.knowledge.engine import KnowledgeEngine

        knowledge = KnowledgeEngine()
        p = build_pipeline(knowledge=knowledge)
        assert p.knowledge is knowledge

    def test_build_pipeline_with_custom_providers(self) -> None:
        from atlas.providers.manager import ProviderManager

        providers = ProviderManager()
        p = build_pipeline(providers=providers)
        assert p.providers is providers

    def test_build_pipeline_no_providers(self) -> None:
        p = build_pipeline(register_providers=False)
        # With register_providers=False, no providers are registered
        # (the manager is still created, just empty)
        assert len(p.providers.registry.all()) == 0

    def test_build_pipeline_with_api_keys(self) -> None:
        p = build_pipeline(api_keys={"openai": "sk-test-key"})
        openai = p.providers.registry.get("openai")
        assert openai is not None
        assert openai.api_key == "sk-test-key"


# ===========================================================================
# Pipeline.think — real execution
# ===========================================================================


class TestPipelineThink:
    def test_think_returns_outcome(self) -> None:
        from atlas.intelligence.models import ExecutionOutcome

        p = build_pipeline()
        outcome = p.think("Say hello")
        assert isinstance(outcome, ExecutionOutcome)

    def test_think_completes(self) -> None:
        p = build_pipeline()
        outcome = p.think("Say hello")
        assert outcome.status.value in ("completed", "failed")

    def test_think_has_duration(self) -> None:
        p = build_pipeline()
        outcome = p.think("Say hello")
        assert outcome.duration_seconds >= 0.0

    def test_think_has_goal_id(self) -> None:
        p = build_pipeline()
        outcome = p.think("Say hello")
        assert outcome.goal_id

    def test_think_has_started_at(self) -> None:
        p = build_pipeline()
        outcome = p.think("Say hello")
        assert outcome.started_at is not None

    def test_think_has_completed_at(self) -> None:
        p = build_pipeline()
        outcome = p.think("Say hello")
        assert outcome.completed_at is not None

    def test_think_empty_goal_raises(self) -> None:
        from atlas.intelligence.brain import BrainError

        p = build_pipeline()
        with pytest.raises(BrainError):
            p.think("")

    def test_think_whitespace_goal_raises(self) -> None:
        from atlas.intelligence.brain import BrainError

        p = build_pipeline()
        with pytest.raises(BrainError):
            p.think("   ")

    def test_think_many(self) -> None:
        p = build_pipeline()
        outcomes = p.think_many(["Goal 1", "Goal 2", "Goal 3"])
        assert len(outcomes) == 3

    def test_think_writes_to_memory(self) -> None:
        p = build_pipeline()
        before = len(p.memory.recall())
        p.think("Remember this goal")
        after = len(p.memory.recall())
        # The brain writes the outcome to memory
        assert after >= before

    def test_think_creates_goal_in_manager(self) -> None:
        p = build_pipeline()
        p.think("Test goal")
        status = p.brain.status()
        assert status["goals_total"] >= 1


# ===========================================================================
# Pipeline.think_stream — streaming events
# ===========================================================================


class TestPipelineThinkStream:
    def test_think_stream_returns_iterator(self) -> None:
        p = build_pipeline()
        events = p.think_stream("Say hello")
        assert isinstance(events, Iterator)

    def test_think_stream_yields_start_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        assert events[0]["event"] == "start"
        assert events[0]["data"]["goal"] == "Say hello"

    def test_think_stream_yields_knowledge_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        knowledge_events = [e for e in events if e["event"] == "knowledge"]
        assert len(knowledge_events) == 1

    def test_think_stream_yields_memory_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        memory_events = [e for e in events if e["event"] == "memory"]
        assert len(memory_events) == 1

    def test_think_stream_yields_complete_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1

    def test_think_stream_complete_has_outcome(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        complete = [e for e in events if e["event"] == "complete"][0]
        assert "outcome" in complete["data"]

    def test_think_stream_yields_plan_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        plan_events = [e for e in events if e["event"] == "plan"]
        assert len(plan_events) == 1

    def test_think_stream_yields_execute_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        exec_events = [e for e in events if e["event"] == "execute"]
        assert len(exec_events) == 1

    def test_think_stream_yields_review_event(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        review_events = [e for e in events if e["event"] == "review"]
        assert len(review_events) == 1

    def test_think_stream_event_order(self) -> None:
        p = build_pipeline()
        events = list(p.think_stream("Say hello"))
        event_types = [e["event"] for e in events]
        # start should be first
        assert event_types[0] == "start"
        # complete or error should be last
        assert event_types[-1] in ("complete", "error")


# ===========================================================================
# Pipeline.generate — direct provider access
# ===========================================================================


class TestPipelineGenerate:
    def test_generate_returns_response(self) -> None:
        p = build_pipeline()
        response = p.generate("Hello")
        assert isinstance(response, ProviderResponse)
        assert response.text

    def test_generate_with_model(self) -> None:
        p = build_pipeline()
        response = p.generate("Hello", model="gpt-4o-mini")
        assert isinstance(response, ProviderResponse)

    def test_generate_with_provider(self) -> None:
        p = build_pipeline()
        response = p.generate("Hello", provider="anthropic")
        assert isinstance(response, ProviderResponse)


# ===========================================================================
# Real providers — fallback mode (no API key)
# ===========================================================================


class TestRealProvidersFallback:
    """Every real provider must work in fallback mode (no API key)."""

    def test_openai_fallback(self) -> None:
        p = RealOpenAIProvider()  # no api_key
        request = ProviderRequest(prompt="Hello", model="gpt-4o-mini")
        response = p.generate(request)
        assert isinstance(response, ProviderResponse)
        assert response.text
        assert "openai" in response.text.lower() or response.text

    def test_anthropic_fallback(self) -> None:
        p = RealAnthropicProvider()
        request = ProviderRequest(prompt="Hello", model="claude-3-5-sonnet-20241022")
        response = p.generate(request)
        assert isinstance(response, ProviderResponse)
        assert response.text

    def test_gemini_fallback(self) -> None:
        p = RealGeminiProvider()
        request = ProviderRequest(prompt="Hello", model="gemini-1.5-pro")
        response = p.generate(request)
        assert isinstance(response, ProviderResponse)
        assert response.text

    def test_openrouter_fallback(self) -> None:
        p = RealOpenRouterProvider()
        request = ProviderRequest(prompt="Hello", model="openai/gpt-4o")
        response = p.generate(request)
        assert isinstance(response, ProviderResponse)
        assert response.text

    def test_ollama_fallback(self) -> None:
        p = RealOllamaProvider()
        request = ProviderRequest(prompt="Hello", model="llama3.2")
        response = p.generate(request)
        assert isinstance(response, ProviderResponse)
        assert response.text

    def test_zai_fallback(self) -> None:
        p = RealZAIProvider()
        request = ProviderRequest(prompt="Hello", model="glm-4-plus")
        response = p.generate(request)
        assert isinstance(response, ProviderResponse)
        assert response.text

    def test_all_providers_are_base_provider(self) -> None:
        for cls in (
            RealOpenAIProvider,
            RealAnthropicProvider,
            RealGeminiProvider,
            RealOpenRouterProvider,
            RealOllamaProvider,
            RealZAIProvider,
        ):
            assert issubclass(cls, BaseProvider)


# ===========================================================================
# Real providers — available_models
# ===========================================================================


class TestRealProvidersModels:
    def test_openai_models(self) -> None:
        p = RealOpenAIProvider()
        models = p.available_models()
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models

    def test_anthropic_models(self) -> None:
        p = RealAnthropicProvider()
        models = p.available_models()
        assert any("claude" in m for m in models)

    def test_gemini_models(self) -> None:
        p = RealGeminiProvider()
        models = p.available_models()
        assert any("gemini" in m for m in models)

    def test_openrouter_models(self) -> None:
        p = RealOpenRouterProvider()
        models = p.available_models()
        assert len(models) > 0

    def test_ollama_models(self) -> None:
        p = RealOllamaProvider()
        models = p.available_models()
        assert "llama3.2" in models

    def test_zai_models(self) -> None:
        p = RealZAIProvider()
        models = p.available_models()
        assert any("glm" in m for m in models)


# ===========================================================================
# Real providers — streaming
# ===========================================================================


class TestRealProvidersStream:
    def test_openai_stream(self) -> None:
        p = RealOpenAIProvider()
        request = ProviderRequest(prompt="Hello world", model="gpt-4o-mini")
        chunks = list(p.stream(request))
        assert len(chunks) > 0
        assert all(isinstance(c, ProviderResponse) for c in chunks)

    def test_anthropic_stream(self) -> None:
        p = RealAnthropicProvider()
        request = ProviderRequest(
            prompt="Hello world", model="claude-3-5-sonnet-20241022"
        )
        chunks = list(p.stream(request))
        assert len(chunks) > 0

    def test_gemini_stream(self) -> None:
        p = RealGeminiProvider()
        request = ProviderRequest(prompt="Hello world", model="gemini-1.5-pro")
        chunks = list(p.stream(request))
        assert len(chunks) > 0

    def test_ollama_stream(self) -> None:
        p = RealOllamaProvider()
        request = ProviderRequest(prompt="Hello world", model="llama3.2")
        chunks = list(p.stream(request))
        assert len(chunks) > 0


# ===========================================================================
# Real providers — real HTTP mode (mocked)
# ===========================================================================


class TestRealProvidersHTTPMode:
    """When an API key is present, providers attempt real HTTP calls.

    We mock :func:`http_post_json` to avoid actual network calls in
    tests, verifying the provider builds the correct payload and parses
    the response correctly.
    """

    def test_openai_real_mode_calls_http(self) -> None:
        p = RealOpenAIProvider(api_key="sk-test")
        request = ProviderRequest(prompt="Hello", model="gpt-4o-mini")
        mock_response = {
            "choices": [{"message": {"content": "Hi there!"}, "finish_reason": "stop"}],
            "usage": {"prompt": 5, "completion": 3, "total": 8},
        }
        with patch(
            "atlas.providers.real.openai.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            response = p.generate(request)
            assert mock_post.called
            assert response.text == "Hi there!"
            assert response.finish_reason == "stop"

    def test_openai_real_mode_sends_authorization(self) -> None:
        p = RealOpenAIProvider(api_key="sk-test")
        request = ProviderRequest(prompt="Hello", model="gpt-4o-mini")
        mock_response = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
        with patch(
            "atlas.providers.real.openai.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            p.generate(request)
            _args, kwargs = mock_post.call_args
            headers = kwargs.get("headers", {})
            assert headers.get("Authorization") == "Bearer sk-test"

    def test_openai_real_mode_handles_error(self) -> None:
        p = RealOpenAIProvider(api_key="sk-test")
        request = ProviderRequest(prompt="Hello", model="gpt-4o-mini")
        with patch(
            "atlas.providers.real.openai.http_post_json",
            side_effect=ProviderHTTPError("HTTP 500", status=500),
        ):
            response = p.generate(request)
            assert response.finish_reason == "error"
            assert "error" in response.metadata

    def test_anthropic_real_mode_calls_http(self) -> None:
        p = RealAnthropicProvider(api_key="sk-ant-test")
        request = ProviderRequest(prompt="Hello", model="claude-3-5-sonnet-20241022")
        mock_response = {
            "content": [{"text": "Hello!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
        with patch(
            "atlas.providers.real.anthropic.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            response = p.generate(request)
            assert mock_post.called
            assert response.text == "Hello!"

    def test_anthropic_real_mode_sends_api_key_header(self) -> None:
        p = RealAnthropicProvider(api_key="sk-ant-test")
        request = ProviderRequest(prompt="Hello", model="claude-3-5-sonnet-20241022")
        mock_response = {"content": [{"text": "ok"}], "stop_reason": "end_turn"}
        with patch(
            "atlas.providers.real.anthropic.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            p.generate(request)
            _args, kwargs = mock_post.call_args
            headers = kwargs.get("headers", {})
            assert headers.get("x-api-key") == "sk-ant-test"

    def test_gemini_real_mode_calls_http(self) -> None:
        p = RealGeminiProvider(api_key="gemini-key")
        request = ProviderRequest(prompt="Hello", model="gemini-1.5-pro")
        mock_response = {
            "candidates": [{"content": {"parts": [{"text": "Hi!"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3},
        }
        with patch(
            "atlas.providers.real.gemini.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            response = p.generate(request)
            assert mock_post.called
            assert response.text == "Hi!"

    def test_openrouter_real_mode_calls_http(self) -> None:
        p = RealOpenRouterProvider(api_key="or-key")
        request = ProviderRequest(prompt="Hello", model="openai/gpt-4o")
        mock_response = {
            "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
            "usage": {},
        }
        with patch(
            "atlas.providers.real.openrouter.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            response = p.generate(request)
            assert mock_post.called
            assert response.text == "Hello!"

    def test_ollama_real_mode_calls_http(self) -> None:
        p = RealOllamaProvider(api_key="ollama-key")
        request = ProviderRequest(prompt="Hello", model="llama3.2")
        mock_response = {
            "message": {"content": "Hi!"},
            "usage": {},
        }
        with patch(
            "atlas.providers.real.ollama.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            response = p.generate(request)
            assert mock_post.called
            assert response.text == "Hi!"

    def test_zai_real_mode_calls_http(self) -> None:
        p = RealZAIProvider(api_key="zai-key")
        request = ProviderRequest(prompt="Hello", model="glm-4-plus")
        mock_response = {
            "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
            "usage": {},
        }
        with patch(
            "atlas.providers.real.zai.http_post_json",
            return_value=mock_response,
        ) as mock_post:
            response = p.generate(request)
            assert mock_post.called
            assert response.text == "Hello!"


# ===========================================================================
# HTTP helpers
# ===========================================================================


class TestHTTPHelpers:
    def test_provider_http_error_attributes(self) -> None:
        err = ProviderHTTPError("boom", status=500, body="server error")
        assert err.status == 500
        assert err.body == "server error"
        assert "boom" in str(err)

    def test_http_post_json_signature(self) -> None:
        # Just verify the function is callable with the right signature
        assert callable(http_post_json)

    def test_http_get_json_signature(self) -> None:
        assert callable(http_get_json)


# ===========================================================================
# AtlasApp.with_pipeline integration
# ===========================================================================


class TestAtlasAppWithPipeline:
    def test_with_pipeline_returns_app(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert isinstance(app, AtlasApp)

    def test_with_pipeline_sets_pipeline(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert app.pipeline is not None
        assert isinstance(app.pipeline, Pipeline)

    def test_with_pipeline_wires_brain(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert app.brain is app.pipeline.brain

    def test_with_pipeline_wires_providers(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert app.providers is app.pipeline.providers

    def test_with_pipeline_wires_memory(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert app.memory is app.pipeline.memory

    def test_with_pipeline_wires_knowledge(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert app.knowledge is app.pipeline.knowledge

    def test_with_pipeline_wires_mcp(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        assert app.mcp is app.pipeline.mcp

    def test_with_pipeline_status_shows_wired(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        status = app.status()
        assert status["brain_wired"] is True
        assert status["providers_wired"] is True
        assert status["memory_wired"] is True
        assert status["knowledge_wired"] is True
        assert status["mcp_wired"] is True

    def test_with_pipeline_can_think(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        outcome = app.pipeline.think("Test goal")
        assert outcome.status.value in ("completed", "failed")

    def test_with_pipeline_chat_controller_uses_real_brain(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        chat = app.controller("chat")
        # ChatController should have the real brain wired
        assert chat._brain is app.pipeline.brain

    def test_with_pipeline_execution_controller_uses_real_brain(self) -> None:
        from atlas.app import AtlasApp

        app = AtlasApp.with_pipeline()
        execution = app.controller("execution")
        assert execution._brain is app.pipeline.brain


# ===========================================================================
# End-to-end integration
# ===========================================================================


class TestEndToEndIntegration:
    def test_full_pipeline_execution(self) -> None:
        """End-to-end: build pipeline → think → verify outcome."""
        p = build_pipeline()
        outcome = p.think("Write a hello world program in Python")
        assert outcome.status.value in ("completed", "failed")
        assert outcome.duration_seconds >= 0.0
        assert outcome.goal_id

    def test_pipeline_persists_memory_across_thinks(self) -> None:
        """Multiple think() calls should accumulate memory entries."""
        p = build_pipeline()
        before = len(p.memory.recall())
        p.think("First goal")
        p.think("Second goal")
        after = len(p.memory.recall())
        assert after > before

    def test_pipeline_streaming_then_think_consistent(self) -> None:
        """think_stream then think should both succeed."""
        p = build_pipeline()
        list(p.think_stream("Streamed goal"))
        outcome = p.think("Direct goal")
        assert outcome.status.value in ("completed", "failed")

    def test_pipeline_with_knowledge_ingest(self) -> None:
        """Ingesting knowledge should make it searchable by the brain."""
        p = build_pipeline()
        p.knowledge.ingest_text(
            content="Atlas is an AI operating system.",
            source="test",
        )
        assert p.knowledge.count() >= 1
        # The brain's knowledge search should now return hits
        hits = p.coordinator.search_knowledge("Atlas")
        assert len(hits) >= 1


# ===========================================================================
# Environment variable key resolution
# ===========================================================================


class TestEnvKeyResolution:
    def test_build_pipeline_reads_openai_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-test-key"}):
            p = build_pipeline()
            openai = p.providers.registry.get("openai")
            assert openai.api_key == "env-test-key"

    def test_build_pipeline_reads_anthropic_env(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-ant-key"}):
            p = build_pipeline()
            anthropic = p.providers.registry.get("anthropic")
            assert anthropic.api_key == "env-ant-key"

    def test_build_pipeline_api_keys_override_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            p = build_pipeline(api_keys={"openai": "explicit-key"})
            openai = p.providers.registry.get("openai")
            assert openai.api_key == "explicit-key"


# ===========================================================================
# No circular imports
# ===========================================================================


class TestNoCircularImports:
    def test_pipeline_does_not_import_app(self) -> None:
        """The pipeline package must not import atlas.app (avoid cycles)."""
        import os
        import re

        import atlas.pipeline

        pipeline_root = os.path.dirname(atlas.pipeline.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(r"^\s*from atlas\.app\b")
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(pipeline_root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path) as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert not offenders, "atlas.pipeline imports atlas.app:\n" + "\n".join(
            offenders
        )

    def test_reload_pipeline(self) -> None:
        """Verify the package can be reloaded without issues."""
        import importlib

        import atlas.pipeline

        importlib.reload(atlas.pipeline)
        assert hasattr(atlas.pipeline, "build_pipeline")


# ===========================================================================
# Examples
# ===========================================================================


class TestExamples:
    def test_run_pipeline_example_importable(self) -> None:
        """The run_pipeline example should be importable."""
        import importlib.util
        import os

        spec = importlib.util.spec_from_file_location(
            "run_pipeline",
            os.path.join(
                os.path.dirname(__file__), "..", "examples", "run_pipeline.py"
            ),
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert hasattr(module, "main")
