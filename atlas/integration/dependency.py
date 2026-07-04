"""Dependency injection descriptors and lifecycle phases.

This module is a *leaf* in the integration package dependency graph: it
depends only on the standard library. It defines:

* :class:`ServiceScope` — singleton vs. transient lifecycle.
* :class:`ServiceDescriptor` — the immutable registration record stored
  by the :class:`DIContainer`.
* :class:`LifecyclePhase` — the ordered phases every Atlas subsystem
  passes through during startup and shutdown.
* :class:`ServiceError` — base exception for container failures.

These primitives are intentionally decoupled from any concrete Atlas
subsystem so that the container can be reused for any dependency graph.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class ServiceScope(enum.StrEnum):
    """Lifecycle scope of a registered service.

    Attributes:
        SINGLETON: One instance shared across the entire container.
        TRANSIENT: A fresh instance is produced on every resolution.
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"


class LifecyclePhase(enum.StrEnum):
    """Ordered phases every Atlas subsystem passes through.

    The startup manager walks these phases in declaration order; the
    shutdown manager walks them in reverse. Each phase is a stable
    identifier that subsystems can subscribe to via the container.
    """

    CONFIG = "config"
    LOGGER = "logger"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    PROVIDERS = "providers"
    TOOLS = "tools"
    SKILLS = "skills"
    AGENTS = "agents"
    WORKFLOWS = "workflows"
    RUNTIME = "runtime"
    TELEMETRY = "telemetry"
    DASHBOARD = "dashboard"
    HEALTH = "health"
    READY = "ready"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


#: The canonical startup order. Index 0 starts first.
STARTUP_ORDER: tuple[LifecyclePhase, ...] = (
    LifecyclePhase.CONFIG,
    LifecyclePhase.LOGGER,
    LifecyclePhase.MEMORY,
    LifecyclePhase.KNOWLEDGE,
    LifecyclePhase.PROVIDERS,
    LifecyclePhase.TOOLS,
    LifecyclePhase.SKILLS,
    LifecyclePhase.AGENTS,
    LifecyclePhase.WORKFLOWS,
    LifecyclePhase.RUNTIME,
    LifecyclePhase.TELEMETRY,
    LifecyclePhase.DASHBOARD,
    LifecyclePhase.HEALTH,
    LifecyclePhase.READY,
)

#: The canonical shutdown order — reverse of :data:`STARTUP_ORDER`
#: (excluding ``READY`` which is a state, not a service).
SHUTDOWN_ORDER: tuple[LifecyclePhase, ...] = tuple(
    phase for phase in reversed(STARTUP_ORDER) if phase is not LifecyclePhase.READY
)


class ServiceError(RuntimeError):
    """Base exception raised by the dependency injection container."""


class ServiceNotFoundError(ServiceError):
    """Raised when a requested service is not registered."""


class ServiceAlreadyRegisteredError(ServiceError):
    """Raised when registering a service name that already exists."""


#: A factory callable that produces a service instance. Receives the
#: container so it can resolve dependencies.
ServiceFactory = Callable[[Any], Any]


@dataclass(frozen=True)
class ServiceDescriptor:
    """Immutable registration record for a single service.

    Attributes:
        name: Unique service name (the lookup key).
        factory: Callable ``(container) -> instance`` that produces the
            service. Required.
        scope: :class:`ServiceScope` controlling lifecycle.
        phase: :class:`LifecyclePhase` this service belongs to. Used by
            the startup/shutdown managers to order initialization.
        interfaces: Tuple of types the service satisfies. Enables
            ``container.get(SomeInterface)`` lookups in addition to
            ``container.get("name")``.
        tags: Free-form labels for grouping (e.g. ``"provider"``,
            ``"tool"``).
    """

    name: str
    factory: ServiceFactory
    scope: ServiceScope = ServiceScope.SINGLETON
    phase: LifecyclePhase = LifecyclePhase.READY
    interfaces: tuple[type, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "LifecyclePhase",
    "ServiceAlreadyRegisteredError",
    "ServiceDescriptor",
    "ServiceError",
    "ServiceFactory",
    "ServiceNotFoundError",
    "ServiceScope",
    "SHUTDOWN_ORDER",
    "STARTUP_ORDER",
]
