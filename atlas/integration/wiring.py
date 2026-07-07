"""Dependency wiring — registers every Atlas subsystem in the container.

The :class:`Wiring` class is the single place that knows how to construct
every Atlas subsystem and wire it into the :class:`DIContainer`. It is
the only module in the integration package that imports from every
Atlas subsystem; the rest of the integration package is subsystem-agnostic.

Wiring is *declarative*: each ``register_*`` method adds one or more
:class:`ServiceDescriptor` records to the container. The services are
not instantiated until they are first requested (lazy by default). The
order of registration does not matter for resolution, but it does
matter for the startup/shutdown managers, which walk descriptors in
:class:`LifecyclePhase` order.

A minimal skill abstraction (:class:`SkillManager`) is provided here
because Atlas does not yet ship one. It is intentionally simple — a
registry of named callables — so future skill implementations can
replace it without touching the integration layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.core.config import Config
from atlas.core.logger import get_logger
from atlas.core.router import Router
from atlas.integration.container import DIContainer
from atlas.integration.dependency import (
    LifecyclePhase,
    ServiceDescriptor,
    ServiceScope,
)
from atlas.integration.registry import UnifiedRegistry

# ---------------------------------------------------------------------------
# Minimal skill manager (placeholder for a future atlas/skills/ package)
# ---------------------------------------------------------------------------


class SkillManager:
    """Minimal in-memory skill registry.

    A skill is a named callable that can be invoked by the runtime. This
    is a placeholder; a future ``atlas/skills/`` package can replace it
    without changing the integration layer's contract.
    """

    def __init__(self) -> None:
        self._skills: dict[str, Callable[..., Any]] = {}
        self.logger = get_logger("integration.skills")

    def register(self, name: str, skill: Callable[..., Any]) -> SkillManager:
        """Register a skill callable under ``name``."""
        if not name or not name.strip():
            raise ValueError("Skill name must be non-empty.")
        if not callable(skill):
            raise TypeError("Skill must be callable.")
        self._skills[name] = skill
        return self

    def unregister(self, name: str) -> bool:
        """Remove a skill by name. Return ``True`` if it existed."""
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> Callable[..., Any] | None:
        """Look up a skill by name."""
        return self._skills.get(name)

    def contains(self, name: str) -> bool:
        """Return ``True`` if ``name`` is registered."""
        return name in self._skills

    def names(self) -> list[str]:
        """Return a sorted list of registered skill names."""
        return sorted(self._skills)

    def all(self) -> list[Callable[..., Any]]:
        """Return every registered skill callable."""
        return [self._skills[name] for name in self.names()]

    def count(self) -> int:
        """Return the number of registered skills."""
        return len(self._skills)

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a registered skill by name.

        Raises:
            KeyError: If the skill is not registered.
        """
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"Skill not registered: {name!r}")
        return skill(*args, **kwargs)

    def __len__(self) -> int:
        return len(self._skills)

    def __repr__(self) -> str:
        return f"<SkillManager skills={len(self)}>"


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class Wiring:
    """Registers every Atlas subsystem into a :class:`DIContainer`.

    Every ``register_*`` method returns ``self`` for chaining. The
    :meth:`wire_all` convenience method registers every subsystem with
    sensible deterministic defaults.

    The wiring is intentionally explicit: each subsystem is registered
    with a stable name, a factory that receives the container (so it can
    resolve dependencies), and the appropriate :class:`LifecyclePhase`.
    """

    def __init__(self, container: DIContainer | None = None) -> None:
        self.container = container if container is not None else DIContainer()
        self.logger = get_logger("integration.wiring")

    # ------------------------------------------------------------------
    # Core infrastructure
    # ------------------------------------------------------------------

    def register_config(self, config: Config | dict[str, Any] | None = None) -> Wiring:
        """Register the Atlas configuration."""

        def factory(_c: DIContainer) -> Any:
            if config is not None:
                return config
            return Config()

        self.container.register(
            ServiceDescriptor(
                name="config",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.CONFIG,
                interfaces=(Config,),
            )
        )
        return self

    def register_logger(self) -> Wiring:
        """Register the root Atlas logger."""

        def factory(_c: DIContainer) -> Any:
            return get_logger("atlas")

        self.container.register(
            ServiceDescriptor(
                name="logger",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.LOGGER,
            )
        )
        return self

    # ------------------------------------------------------------------
    # Subsystems
    # ------------------------------------------------------------------

    def register_memory(self) -> Wiring:
        """Register the :class:`MemoryEngine`."""

        def factory(_c: DIContainer) -> Any:
            from atlas.memory import MemoryEngine

            return MemoryEngine()

        self.container.register(
            ServiceDescriptor(
                name="memory",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.MEMORY,
                interfaces=(MemoryEnginePlaceholder,),
            )
        )
        return self

    def register_knowledge(self) -> Wiring:
        """Register the :class:`KnowledgeEngine`."""

        def factory(_c: DIContainer) -> Any:
            from atlas.knowledge import KnowledgeEngine

            return KnowledgeEngine()

        self.container.register(
            ServiceDescriptor(
                name="knowledge",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.KNOWLEDGE,
                interfaces=(KnowledgeEnginePlaceholder,),
            )
        )
        return self

    def register_providers(self) -> Wiring:
        """Register the :class:`ProviderManager` and all 9 built-in providers."""

        def factory(c: DIContainer) -> Any:
            from atlas.providers import (
                AnthropicProvider,
                GeminiProvider,
                GroqProvider,
                LMStudioProvider,
                NvidiaProvider,
                OllamaProvider,
                OpenAIProvider,
                OpenRouterProvider,
                ProviderManager,
                ZAIProvider,
            )

            manager = ProviderManager()
            for provider_cls in (
                ZAIProvider,
                OpenAIProvider,
                AnthropicProvider,
                GeminiProvider,
                GroqProvider,
                NvidiaProvider,
                OpenRouterProvider,
                OllamaProvider,
                LMStudioProvider,
            ):
                try:
                    provider = provider_cls()
                    make_default = provider_cls is ZAIProvider
                    manager.register(provider, make_default=make_default)
                except Exception as exc:  # noqa: BLE001 — keep wiring resilient
                    self.logger.warning(
                        "Failed to register provider %s: %s",
                        provider_cls.__name__,
                        exc,
                    )
            return manager

        self.container.register(
            ServiceDescriptor(
                name="providers",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.PROVIDERS,
                interfaces=(ProviderManagerPlaceholder,),
            )
        )
        return self

    def register_tools(self) -> Wiring:
        """Register the :class:`ToolManager`."""

        def factory(_c: DIContainer) -> Any:
            from atlas.tools import ToolManager

            return ToolManager()

        self.container.register(
            ServiceDescriptor(
                name="tools",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.TOOLS,
                interfaces=(ToolManagerPlaceholder,),
            )
        )
        return self

    def register_skills(self) -> Wiring:
        """Register the :class:`SkillManager`."""

        def factory(_c: DIContainer) -> SkillManager:
            return SkillManager()

        self.container.register(
            ServiceDescriptor(
                name="skills",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.SKILLS,
                interfaces=(SkillManager,),
            )
        )
        return self

    def register_agents(self) -> Wiring:
        """Register the agent manager (currently the kernel's :class:`Router`)."""

        def factory(_c: DIContainer) -> Any:
            return Router()

        self.container.register(
            ServiceDescriptor(
                name="agents",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.AGENTS,
                interfaces=(Router,),
            )
        )
        return self

    def register_workflows(self) -> Wiring:
        """Register the :class:`WorkflowEngine`."""

        def factory(_c: DIContainer) -> Any:
            from atlas.workflows import WorkflowEngine

            return WorkflowEngine()

        self.container.register(
            ServiceDescriptor(
                name="workflows",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.WORKFLOWS,
                interfaces=(WorkflowEnginePlaceholder,),
            )
        )
        return self

    def register_runtime(self) -> Wiring:
        """Register the :class:`Runtime` as the single execution entry point."""

        def factory(_c: DIContainer) -> Any:
            from atlas.runtime import Runtime

            return Runtime()

        self.container.register(
            ServiceDescriptor(
                name="runtime",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.RUNTIME,
                interfaces=(RuntimePlaceholder,),
            )
        )
        return self

    def register_telemetry(self) -> Wiring:
        """Register the runtime's :class:`TelemetryCollector`."""

        def factory(c: DIContainer) -> Any:
            runtime = c.get_optional("runtime")
            if runtime is None:
                return None
            return getattr(runtime, "telemetry", None)

        self.container.register(
            ServiceDescriptor(
                name="telemetry",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.TELEMETRY,
            )
        )
        return self

    def register_health(self) -> Wiring:
        """Register the :class:`HealthMonitor`."""

        def factory(c: DIContainer) -> Any:
            from atlas.integration.health import HealthMonitor

            return HealthMonitor(c)

        self.container.register(
            ServiceDescriptor(
                name="health",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.HEALTH,
                interfaces=(HealthMonitorPlaceholder,),
            )
        )
        return self

    def register_registry(self) -> Wiring:
        """Register the :class:`UnifiedRegistry` facade over subsystem registries."""

        def factory(c: DIContainer) -> UnifiedRegistry:
            providers = c.get_optional("providers")
            tools = c.get_optional("tools")
            workflows = c.get_optional("workflows")
            agents = c.get_optional("agents")
            skills = c.get_optional("skills")
            return UnifiedRegistry(
                providers=(
                    getattr(providers, "registry", providers) if providers else None
                ),
                tools=getattr(tools, "registry", tools) if tools else None,
                workflows=(
                    getattr(workflows, "registry", workflows) if workflows else None
                ),
                agents=agents,
                skills=skills,
            )

        self.container.register(
            ServiceDescriptor(
                name="registry",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.HEALTH,
                interfaces=(UnifiedRegistry,),
            )
        )
        return self

    def register_diagnostics(
        self,
        started_at: Any | None = None,
        startup_time_seconds: float = 0.0,
    ) -> Wiring:
        """Register the :class:`DiagnosticsCollector`."""

        def factory(c: DIContainer) -> Any:
            from atlas.integration.diagnostics import DiagnosticsCollector

            return DiagnosticsCollector(
                c,
                started_at=started_at,
                startup_time_seconds=startup_time_seconds,
            )

        self.container.register(
            ServiceDescriptor(
                name="diagnostics",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.HEALTH,
            )
        )
        return self

    def register_locator(self) -> Wiring:
        """Register the :class:`ServiceLocator`."""

        def factory(c: DIContainer) -> Any:
            from atlas.integration.service_locator import ServiceLocator

            return ServiceLocator(c)

        self.container.register(
            ServiceDescriptor(
                name="locator",
                factory=factory,
                scope=ServiceScope.SINGLETON,
                phase=LifecyclePhase.READY,
            )
        )
        return self

    # ------------------------------------------------------------------
    # Bulk wiring
    # ------------------------------------------------------------------

    def wire_all(self, config: Config | dict[str, Any] | None = None) -> Wiring:
        """Register every Atlas subsystem with deterministic defaults.

        This is the canonical way to build a fully-wired container. The
        order of registration follows the canonical startup order.
        """
        (
            self.register_config(config)
            .register_logger()
            .register_memory()
            .register_knowledge()
            .register_providers()
            .register_tools()
            .register_skills()
            .register_agents()
            .register_workflows()
            .register_runtime()
            .register_telemetry()
            .register_health()
            .register_registry()
            .register_locator()
        )
        self.logger.info("Wired %d services into container", len(self.container))
        return self


# ---------------------------------------------------------------------------
# Placeholder interfaces for typed lookups
# ---------------------------------------------------------------------------


class MemoryEnginePlaceholder:
    """Typing placeholder for :class:`atlas.memory.MemoryEngine`.

    Used as an ``interfaces`` entry so callers can do
    ``container.get_typed(MemoryEnginePlaceholder)`` without importing the
    real engine at module load time.
    """


class KnowledgeEnginePlaceholder:
    """Typing placeholder for :class:`atlas.knowledge.KnowledgeEngine`."""


class ProviderManagerPlaceholder:
    """Typing placeholder for :class:`atlas.providers.ProviderManager`."""


class ToolManagerPlaceholder:
    """Typing placeholder for :class:`atlas.tools.ToolManager`."""


class WorkflowEnginePlaceholder:
    """Typing placeholder for :class:`atlas.workflows.WorkflowEngine`."""


class RuntimePlaceholder:
    """Typing placeholder for :class:`atlas.runtime.Runtime`."""


class HealthMonitorPlaceholder:
    """Typing placeholder for :class:`atlas.integration.health.HealthMonitor`."""


__all__ = [
    "HealthMonitorPlaceholder",
    "KnowledgeEnginePlaceholder",
    "MemoryEnginePlaceholder",
    "ProviderManagerPlaceholder",
    "RuntimePlaceholder",
    "SkillManager",
    "ToolManagerPlaceholder",
    "Wiring",
    "WorkflowEnginePlaceholder",
]
