"""Dependency injection container — owns every Atlas subsystem.

The :class:`DIContainer` is the single place where every Atlas subsystem
is constructed. Services are registered as :class:`ServiceDescriptor`
records (name + factory + scope + phase). Resolution is lazy by default:
a service is not constructed until the first time it is requested.

The container supports two lookup styles:

* **By name** — ``container.get("memory")`` returns the service
  registered under that exact name.
* **By interface** — ``container.get_typed(SomeClass)`` returns any
  service whose descriptor declares ``SomeClass`` in its ``interfaces``
  tuple. This enables clean dependency injection without string keys.

Singletons are cached on first resolution; transients are rebuilt every
time. Circular dependencies are detected and raise
:class:`CircularDependencyError`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, TypeVar

from atlas.core.logger import get_logger
from atlas.integration.dependency import (
    LifecyclePhase,
    ServiceAlreadyRegisteredError,
    ServiceDescriptor,
    ServiceError,
    ServiceNotFoundError,
    ServiceScope,
)

T = TypeVar("T")


class CircularDependencyError(ServiceError):
    """Raised when a dependency cycle is detected during resolution."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__("Circular dependency: " + " -> ".join(cycle))


class DIContainer:
    """In-memory dependency injection container.

    Services are registered via :meth:`register` (which accepts a
    :class:`ServiceDescriptor`) or the convenience :meth:`register_value`
    (for pre-built instances) and :meth:`register_factory` (for lazy
    factories). Resolution is via :meth:`get` (by name) or
    :meth:`get_typed` (by interface).
    """

    def __init__(self) -> None:
        self._descriptors: dict[str, ServiceDescriptor] = {}
        self._instances: dict[str, Any] = {}
        self._resolution_stack: list[str] = []
        self.logger = get_logger("integration.container")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, descriptor: ServiceDescriptor) -> DIContainer:
        """Register a :class:`ServiceDescriptor`.

        Raises:
            ServiceAlreadyRegisteredError: If a service with the same
                name is already registered.
        """
        if descriptor.name in self._descriptors:
            raise ServiceAlreadyRegisteredError(descriptor.name)
        self._descriptors[descriptor.name] = descriptor
        self.logger.debug(
            "Registered service %r (scope=%s, phase=%s)",
            descriptor.name,
            descriptor.scope.value,
            descriptor.phase.value,
        )
        return self

    def register_factory(
        self,
        name: str,
        factory: Any,
        scope: ServiceScope = ServiceScope.SINGLETON,
        phase: LifecyclePhase = LifecyclePhase.READY,
        interfaces: tuple[type, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> DIContainer:
        """Convenience wrapper for :meth:`register` with a factory."""
        return self.register(
            ServiceDescriptor(
                name=name,
                factory=factory,
                scope=scope,
                phase=phase,
                interfaces=interfaces,
                tags=tags,
            )
        )

    def register_value(
        self,
        name: str,
        value: Any,
        phase: LifecyclePhase = LifecyclePhase.READY,
        interfaces: tuple[type, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> DIContainer:
        """Register a pre-built instance as a singleton.

        The instance is stored immediately and the factory is a no-op
        that returns it. Useful for tests and for values that come from
        outside the container (e.g. a parsed config dict).
        """
        descriptor = ServiceDescriptor(
            name=name,
            factory=lambda _c: value,
            scope=ServiceScope.SINGLETON,
            phase=phase,
            interfaces=interfaces,
            tags=tags,
        )
        self.register(descriptor)
        # Pre-populate the instance cache so the factory is never called.
        self._instances[name] = value
        return self

    def unregister(self, name: str) -> bool:
        """Remove a service registration. Return ``True`` if it existed."""
        existed = self._descriptors.pop(name, None) is not None
        self._instances.pop(name, None)
        return existed

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def get(self, name: str) -> Any:
        """Resolve a service by name.

        Raises:
            ServiceNotFoundError: If no service is registered under ``name``.
            CircularDependencyError: If a dependency cycle is detected.
        """
        if name in self._instances:
            return self._instances[name]
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            raise ServiceNotFoundError(name)
        return self._resolve(descriptor)

    def get_optional(self, name: str) -> Any | None:
        """Like :meth:`get` but returns ``None`` if not registered."""
        try:
            return self.get(name)
        except ServiceNotFoundError:
            return None

    def get_typed(self, interface: type[T]) -> T | None:
        """Resolve a service by interface type.

        Returns ``None`` if no service declares ``interface`` in its
        ``interfaces`` tuple. If multiple services declare the same
        interface, the first registration wins.
        """
        for descriptor in self._descriptors.values():
            if interface in descriptor.interfaces:
                instance = self.get(descriptor.name)
                return instance  # type: ignore[return-value]
        return None

    def contains(self, name: str) -> bool:
        """Return ``True`` if a service is registered under ``name``."""
        return name in self._descriptors

    # ------------------------------------------------------------------
    # Enumeration
    # ------------------------------------------------------------------

    def names(self) -> list[str]:
        """Return every registered service name, sorted."""
        return sorted(self._descriptors)

    def descriptors(self) -> list[ServiceDescriptor]:
        """Return every registered descriptor."""
        return list(self._descriptors.values())

    def descriptors_by_phase(self, phase: LifecyclePhase) -> list[ServiceDescriptor]:
        """Return every descriptor belonging to ``phase``."""
        return [d for d in self._descriptors.values() if d.phase is phase]

    def descriptors_by_tag(self, tag: str) -> list[ServiceDescriptor]:
        """Return every descriptor tagged with ``tag``."""
        return [d for d in self._descriptors.values() if tag in d.tags]

    def phases(self) -> list[LifecyclePhase]:
        """Return every phase that has at least one service, in canonical order."""
        from atlas.integration.dependency import STARTUP_ORDER

        present = {d.phase for d in self._descriptors.values()}
        return [phase for phase in STARTUP_ORDER if phase in present]

    def __iter__(self) -> Iterator[ServiceDescriptor]:
        return iter(self._descriptors.values())

    def __len__(self) -> int:
        return len(self._descriptors)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._descriptors

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_resolved(self, name: str) -> bool:
        """Return ``True`` if ``name`` has been instantiated (singleton only)."""
        return name in self._instances

    def initialized(self) -> list[str]:
        """Return the sorted names of every instantiated singleton."""
        return sorted(self._instances)

    def clear(self) -> None:
        """Drop every registration and cached instance."""
        self._descriptors.clear()
        self._instances.clear()
        self._resolution_stack.clear()

    def __repr__(self) -> str:
        return (
            f"<DIContainer services={len(self._descriptors)} "
            f"initialized={len(self._instances)}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve(self, descriptor: ServiceDescriptor) -> Any:
        """Instantiate ``descriptor``, detecting cycles."""
        if descriptor.name in self._resolution_stack:
            cycle = self._resolution_stack[
                self._resolution_stack.index(descriptor.name) :
            ] + [descriptor.name]
            raise CircularDependencyError(cycle)
        self._resolution_stack.append(descriptor.name)
        try:
            instance = descriptor.factory(self)
        finally:
            self._resolution_stack.pop()
        if descriptor.scope is ServiceScope.SINGLETON:
            self._instances[descriptor.name] = instance
        return instance


__all__ = [
    "CircularDependencyError",
    "DIContainer",
]
