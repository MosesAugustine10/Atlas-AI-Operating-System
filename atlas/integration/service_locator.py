"""Service locator — lazy, typed access to container services.

The :class:`ServiceLocator` is a thin typed wrapper over the
:class:`DIContainer`. It exposes attribute-style access to commonly-used
Atlas subsystems (``locator.runtime``, ``locator.memory``, etc.) while
delegating resolution to the container. This gives orchestrators and
wiring code a clean, IDE-friendly surface without hard-coding service
names as strings everywhere.

The locator does *not* own any state. If a subsystem is not registered
in the container, the corresponding locator property returns ``None``
(so callers can decide how to handle missing dependencies).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from atlas.integration.container import DIContainer

T = TypeVar("T")


class ServiceLocator:
    """Typed lazy accessor over a :class:`DIContainer`.

    Parameters:
        container: The backing container. All property accessors
            delegate to ``container.get(name)``.
    """

    def __init__(self, container: DIContainer) -> None:
        self._container = container

    @property
    def container(self) -> DIContainer:
        """Return the backing container."""
        return self._container

    # ------------------------------------------------------------------
    # Core infrastructure
    # ------------------------------------------------------------------

    @property
    def config(self) -> Any | None:
        """The Atlas :class:`Config`."""
        return self._container.get_optional("config")

    @property
    def logger(self) -> Any | None:
        """The root Atlas logger."""
        return self._container.get_optional("logger")

    # ------------------------------------------------------------------
    # Subsystems
    # ------------------------------------------------------------------

    @property
    def memory(self) -> Any | None:
        """The :class:`MemoryEngine`."""
        return self._container.get_optional("memory")

    @property
    def knowledge(self) -> Any | None:
        """The :class:`KnowledgeEngine`."""
        return self._container.get_optional("knowledge")

    @property
    def providers(self) -> Any | None:
        """The :class:`ProviderManager`."""
        return self._container.get_optional("providers")

    @property
    def tools(self) -> Any | None:
        """The :class:`ToolManager`."""
        return self._container.get_optional("tools")

    @property
    def agents(self) -> Any | None:
        """The agent manager (currently the kernel's ``Router``)."""
        return self._container.get_optional("agents")

    @property
    def skills(self) -> Any | None:
        """The skill manager."""
        return self._container.get_optional("skills")

    @property
    def workflows(self) -> Any | None:
        """The :class:`WorkflowEngine`."""
        return self._container.get_optional("workflows")

    @property
    def runtime(self) -> Any | None:
        """The :class:`Runtime`."""
        return self._container.get_optional("runtime")

    @property
    def kernel(self) -> Any | None:
        """The legacy :class:`Kernel` (kept for backward compatibility)."""
        return self._container.get_optional("kernel")

    @property
    def telemetry(self) -> Any | None:
        """The :class:`TelemetryCollector`."""
        return self._container.get_optional("telemetry")

    @property
    def health(self) -> Any | None:
        """The :class:`HealthMonitor`."""
        return self._container.get_optional("health")

    @property
    def registry(self) -> Any | None:
        """The :class:`UnifiedRegistry`."""
        return self._container.get_optional("registry")

    # ------------------------------------------------------------------
    # Generic access
    # ------------------------------------------------------------------

    def get(self, name: str) -> Any | None:
        """Resolve any service by name."""
        return self._container.get(name)

    def get_typed(self, interface: type[T]) -> T | None:
        """Resolve a service by interface type."""
        return self._container.get_typed(interface)

    def __repr__(self) -> str:
        return f"<ServiceLocator container={self._container!r}>"


__all__ = ["ServiceLocator"]
