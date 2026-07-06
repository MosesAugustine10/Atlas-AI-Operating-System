"""Atlas live execution pipeline — the single composition root for real AI.

This module wires together every existing Atlas subsystem into one live
execution pipeline:

    brain.think(goal)
        → Coordinator
            → KnowledgeEngine.search()
            → MemoryEngine.recall()
            → ExecutionEngine.run(goal)
                → ExecutionPlanner → ExecutionDispatcher → ExecutionExecutor
                    → ProviderManager.generate()  (real LLM call)
                    → MCPManager.execute_capability()  (real tool call)
            → MemoryEngine.remember(outcome)

The :func:`build_pipeline` factory constructs a fully-wired
:class:`Pipeline` with real (or deterministic-fallback) subsystems.
The :class:`Pipeline` exposes a single :meth:`think` method that
runs the entire chain end-to-end and returns a real
:class:`~atlas.intelligence.models.ExecutionOutcome`.

This is **Phase 2** of the production rollout: every placeholder is
replaced with a real subsystem instance. The only remaining fallbacks
are the LLM providers themselves — they make real HTTP calls when an
API key is present, and fall back to deterministic mode when no key is
available (so the pipeline always works in tests and on air-gapped
hosts).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from atlas.core.logger import get_logger
from atlas.execution.engine import ExecutionEngine
from atlas.intelligence.brain import Brain
from atlas.intelligence.coordinator import Coordinator
from atlas.intelligence.models import ExecutionOutcome, GoalPriority, GoalScope
from atlas.knowledge.engine import KnowledgeEngine
from atlas.mcp.manager import MCPManager
from atlas.memory.engine import MemoryEngine
from atlas.providers.manager import ProviderManager
from atlas.providers.models import ProviderResponse
from atlas.providers.registry import ProviderRegistry
from atlas.providers.router import ProviderRouter
from atlas.workflows.engine import WorkflowEngine


class Pipeline:
    """The live Atlas execution pipeline.

    Owns every subsystem instance and exposes a single :meth:`think`
    entry point that runs the full brain → coordinator → execution →
    memory → knowledge chain.

    Attributes:
        brain: The :class:`~atlas.intelligence.brain.Brain`.
        coordinator: The :class:`~atlas.intelligence.coordinator.Coordinator`.
        execution: The :class:`~atlas.execution.engine.ExecutionEngine`.
        providers: The :class:`~atlas.providers.manager.ProviderManager`.
        memory: The :class:`~atlas.memory.engine.MemoryEngine`.
        knowledge: The :class:`~atlas.knowledge.engine.KnowledgeEngine`.
        mcp: The :class:`~atlas.mcp.manager.MCPManager`.
        workflows: The :class:`~atlas.workflows.engine.WorkflowEngine`.
    """

    def __init__(
        self,
        brain: Brain,
        coordinator: Coordinator,
        execution: ExecutionEngine,
        providers: ProviderManager,
        memory: MemoryEngine,
        knowledge: KnowledgeEngine,
        mcp: MCPManager,
        workflows: WorkflowEngine,
    ) -> None:
        self.brain = brain
        self.coordinator = coordinator
        self.execution = execution
        self.providers = providers
        self.memory = memory
        self.knowledge = knowledge
        self.mcp = mcp
        self.workflows = workflows
        self.logger = get_logger("pipeline")

    # ------------------------------------------------------------------
    # Think
    # ------------------------------------------------------------------

    def think(
        self,
        goal: str,
        scope: GoalScope = GoalScope.SHORT_TERM,
        priority: GoalPriority = GoalPriority.NORMAL,
    ) -> ExecutionOutcome:
        """Run the full thinking pipeline for ``goal``.

        This is the canonical entry point. It delegates to
        :meth:`Brain.think` which runs the 12-stage pipeline:
        understand → search knowledge → recall memory → reason → plan →
        decide → execute → review → reflect → learn → remember → return.
        """
        self.logger.info("Pipeline.think: %r", goal[:80])
        return self.brain.think(goal, scope=scope, priority=priority)

    def think_many(self, goals: list[str]) -> list[ExecutionOutcome]:
        """Run :meth:`think` for each goal in ``goals``."""
        return [self.think(g) for g in goals]

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def think_stream(self, goal: str) -> Iterator[dict[str, Any]]:
        """Stream live events from the thinking pipeline.

        Yields dicts with ``event`` and ``data`` keys:
            ``{"event": "start", "data": {"goal": goal}}``
            ``{"event": "knowledge", "data": {"hits": [...]}}``
            ``{"event": "memory", "data": {"hits": [...]}}``
            ``{"event": "plan", "data": {"tasks": [...]}}``
            ``{"event": "execute", "data": {"result": ...}}``
            ``{"event": "review", "data": {"quality": ...}}``
            ``{"event": "complete", "data": {"outcome": ...}}``
        """
        self.logger.info("Pipeline.think_stream: %r", goal[:80])
        yield {"event": "start", "data": {"goal": goal}}
        try:
            # Knowledge search
            knowledge_hits = self.coordinator.search_knowledge(goal)
            yield {"event": "knowledge", "data": {"hits": len(knowledge_hits)}}

            # Memory recall
            memory_hits = self.coordinator.recall_memory(goal)
            yield {"event": "memory", "data": {"hits": len(memory_hits)}}

            # Think (runs plan + execute + review + reflect)
            outcome = self.brain.think(goal)
            yield {"event": "plan", "data": {"tasks": len(outcome.plan.tasks)}}
            yield {
                "event": "execute",
                "data": {"result": str(outcome.result)[:200]},
            }
            yield {
                "event": "review",
                "data": {"quality": outcome.critique.quality_score},
            }
            yield {"event": "complete", "data": {"outcome": outcome}}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": {"error": str(exc)}}

    # ------------------------------------------------------------------
    # Direct generation (bypass the brain — used by the chat page)
    # ------------------------------------------------------------------

    def generate(self, prompt: str, **kwargs: Any) -> ProviderResponse:
        """Generate text directly via the Provider Manager.

        This bypasses the Brain and is used by the chat page for simple
        prompt → response turns.
        """
        return self.providers.generate(prompt, **kwargs)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return a dict describing the pipeline's wiring state."""
        return {
            "brain": self.brain.status(),
            "providers": {
                "registered": len(self.providers.registry.all()),
                "health": self.providers.health(),
            },
            "memory": {
                "wired": self.coordinator.has_memory(),
            },
            "knowledge": {
                "wired": self.coordinator.has_knowledge(),
                "documents": (
                    self.knowledge.count() if hasattr(self.knowledge, "count") else 0
                ),
            },
            "execution": {
                "wired": self.coordinator.has_execution(),
            },
            "mcp": {
                "wired": self.coordinator.has_mcp(),
            },
            "workflows": {
                "wired": self.coordinator.has_workflows(),
            },
        }


def build_pipeline(
    *,
    register_providers: bool = True,
    api_keys: dict[str, str | None] | None = None,
    memory: MemoryEngine | None = None,
    knowledge: KnowledgeEngine | None = None,
    providers: ProviderManager | None = None,
    mcp: MCPManager | None = None,
    workflows: WorkflowEngine | None = None,
    execution: ExecutionEngine | None = None,
) -> Pipeline:
    """Build a fully-wired :class:`Pipeline`.

    All parameters are optional — sensible defaults are created for any
    that are omitted. The result is a pipeline where
    ``pipeline.think(goal)`` actually executes.

    Parameters:
        register_providers: When ``True`` (default), register every
            built-in provider (OpenAI, Anthropic, Gemini, OpenRouter,
            Ollama, Z.ai) with the ProviderManager. Providers make real
            HTTP calls when their API key is present and fall back to
            deterministic mode otherwise.
        api_keys: Optional dict mapping provider names to API keys.
            When omitted, keys are read from environment variables
            (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, etc.).
        memory: Optional MemoryEngine. Created fresh when omitted.
        knowledge: Optional KnowledgeEngine. Created fresh when omitted.
        providers: Optional ProviderManager. Created fresh when omitted.
        mcp: Optional MCPManager. Created fresh when omitted.
        workflows: Optional WorkflowEngine. Created fresh when omitted.
        execution: Optional ExecutionEngine. Created fresh when omitted.
    """
    # Subsystems
    memory = memory or MemoryEngine()
    knowledge = knowledge or KnowledgeEngine()
    if providers is None:
        if register_providers:
            providers = _build_provider_manager(api_keys or {})
        else:
            from atlas.providers.manager import ProviderManager as _PM

            providers = _PM()
    mcp = mcp or MCPManager()
    workflows = workflows or WorkflowEngine()

    # Execution engine (depends on providers, memory, knowledge)
    execution = execution or ExecutionEngine(
        providers=providers,
        memory=memory,
        knowledge=knowledge,
    )

    # Coordinator (wires execution + providers + memory + knowledge + mcp + workflows)
    coordinator = Coordinator(
        execution=execution,
        providers=providers,
        memory=memory,
        knowledge=knowledge,
        mcp=mcp,
        workflows=workflows,
    )

    # Brain (uses coordinator for knowledge/memory/execution)
    brain = Brain(coordinator=coordinator)

    return Pipeline(
        brain=brain,
        coordinator=coordinator,
        execution=execution,
        providers=providers,
        memory=memory,
        knowledge=knowledge,
        mcp=mcp,
        workflows=workflows,
    )


def _build_provider_manager(api_keys: dict[str, str | None]) -> ProviderManager:
    """Build a :class:`ProviderManager` with every real provider registered.

    Each provider is constructed with its API key (from ``api_keys`` or
    environment variables). Providers make real HTTP calls when a key is
    present; otherwise they run in deterministic fallback mode.
    """
    from atlas.providers.real.anthropic import RealAnthropicProvider
    from atlas.providers.real.gemini import RealGeminiProvider
    from atlas.providers.real.ollama import RealOllamaProvider
    from atlas.providers.real.openai import RealOpenAIProvider
    from atlas.providers.real.openrouter import RealOpenRouterProvider
    from atlas.providers.real.zai import RealZAIProvider

    registry = ProviderRegistry()
    router = ProviderRouter(registry)
    manager = ProviderManager(registry=registry, router=router)

    def _key(name: str, env_var: str) -> str | None:
        if name in api_keys:
            return api_keys[name]
        return os.environ.get(env_var)

    # Register every real provider (activates HTTP mode when key present)
    providers_to_register = [
        (RealOpenAIProvider(_key("openai", "OPENAI_API_KEY")), "openai"),
        (RealAnthropicProvider(_key("anthropic", "ANTHROPIC_API_KEY")), "anthropic"),
        (RealGeminiProvider(_key("gemini", "GEMINI_API_KEY")), "gemini"),
        (
            RealOpenRouterProvider(_key("openrouter", "OPENROUTER_API_KEY")),
            "openrouter",
        ),
        (RealOllamaProvider(_key("ollama", "OLLAMA_API_KEY")), "ollama"),
        (RealZAIProvider(_key("zai", "ZAI_API_KEY")), "zai"),
    ]

    first = True
    for provider, _name in providers_to_register:
        try:
            manager.register(provider, make_default=first)
            first = False
        except Exception:  # noqa: BLE001 — skip duplicate registrations
            pass

    return manager


__all__ = ["Pipeline", "build_pipeline"]
