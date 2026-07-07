"""The Atlas Integration Layer.

The integration layer is the dependency wiring heart that connects every
Atlas subsystem into one coherent AI Operating System. It owns:

* A dependency injection :class:`DIContainer` that constructs every
  subsystem exactly once.
* A :class:`Wiring` registrar that knows how to build every subsystem.
* A :class:`StartupManager` that instantiates every service in canonical
  phase order.
* A :class:`ShutdownManager` that tears services down in reverse order.
* A :class:`HealthMonitor` that aggregates per-subsystem health signals.
* A :class:`DiagnosticsCollector` that captures startup time, loaded
  resources, and per-subsystem statistics.
* A :class:`UnifiedRegistry` that exposes providers, agents, tools,
  skills, and workflows through a single query surface.
* A :class:`Bootstrap` that turns a config into a running Atlas.
* An :class:`Orchestrator` façade that users interact with.

The integration layer is **provider-agnostic**, **tool-agnostic**,
**agent-agnostic**, **workflow-agnostic**, and **runtime-agnostic**.
It is designed so future modules (Dashboard, MCP Layer, Desktop App,
Social Media Automation, Vision, Voice, Blender, Surpac, QGIS, AutoCAD,
Remotion, Hyperframes, Ollama) plug in without modifying existing code.

Dependency graph (acyclic):

* ``dependency`` — leaf (DI descriptors + lifecycle phases).
* ``registry`` — leaf (unified registry facade).
* ``container`` — depends on ``dependency``.
* ``service_locator`` — depends on ``container``.
* ``health`` — depends on ``container``.
* ``diagnostics`` — depends on ``container``.
* ``wiring`` — depends on ``container``, ``dependency``, ``registry``
  + every Atlas subsystem (lazy imports).
* ``startup`` — depends on ``container``, ``dependency``.
* ``shutdown`` — depends on ``container``, ``dependency``.
* ``bootstrap`` — depends on ``container``, ``wiring``, ``startup``,
  ``health``.
* ``orchestrator`` — depends on ``bootstrap``, ``container``, ``health``,
  ``diagnostics``, ``startup``, ``shutdown``.
"""

from __future__ import annotations

from atlas.integration.bootstrap import Bootstrap, BootstrappedAtlas
from atlas.integration.container import (
    CircularDependencyError,
    DIContainer,
)
from atlas.integration.dependency import (
    SHUTDOWN_ORDER,
    STARTUP_ORDER,
    LifecyclePhase,
    ServiceAlreadyRegisteredError,
    ServiceDescriptor,
    ServiceError,
    ServiceFactory,
    ServiceNotFoundError,
    ServiceScope,
)
from atlas.integration.diagnostics import (
    DiagnosticsCollector,
    DiagnosticsReport,
)
from atlas.integration.health import (
    HealthMonitor,
    HealthReport,
    HealthStatus,
    SubsystemHealth,
)
from atlas.integration.orchestrator import (
    Orchestrator,
    OrchestratorError,
    OrchestratorState,
)
from atlas.integration.registry import Named, UnifiedRegistry
from atlas.integration.service_locator import ServiceLocator
from atlas.integration.shutdown import (
    ShutdownManager,
    ShutdownReport,
    ShutdownStepResult,
)
from atlas.integration.startup import (
    StartupManager,
    StartupReport,
    StartupStepResult,
)
from atlas.integration.wiring import (
    HealthMonitorPlaceholder,
    KnowledgeEnginePlaceholder,
    MemoryEnginePlaceholder,
    ProviderManagerPlaceholder,
    RuntimePlaceholder,
    SkillManager,
    ToolManagerPlaceholder,
    Wiring,
    WorkflowEnginePlaceholder,
)

__all__ = [
    "Bootstrap",
    "BootstrappedAtlas",
    "CircularDependencyError",
    "DIContainer",
    "DiagnosticsCollector",
    "DiagnosticsReport",
    "HealthMonitor",
    "HealthMonitorPlaceholder",
    "HealthReport",
    "HealthStatus",
    "KnowledgeEnginePlaceholder",
    "LifecyclePhase",
    "MemoryEnginePlaceholder",
    "Named",
    "Orchestrator",
    "OrchestratorError",
    "OrchestratorState",
    "ProviderManagerPlaceholder",
    "RuntimePlaceholder",
    "SHUTDOWN_ORDER",
    "STARTUP_ORDER",
    "ServiceAlreadyRegisteredError",
    "ServiceDescriptor",
    "ServiceError",
    "ServiceFactory",
    "ServiceLocator",
    "ServiceNotFoundError",
    "ServiceScope",
    "ShutdownManager",
    "ShutdownReport",
    "ShutdownStepResult",
    "SkillManager",
    "StartupManager",
    "StartupReport",
    "StartupStepResult",
    "SubsystemHealth",
    "ToolManagerPlaceholder",
    "UnifiedRegistry",
    "Wiring",
    "WorkflowEnginePlaceholder",
]
