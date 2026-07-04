"""Unified registry exposing providers, agents, tools, skills, and workflows.

The :class:`UnifiedRegistry` is a read-only facade over the per-subsystem
registries (``ProviderRegistry``, ``ToolRegistry``, ``WorkflowRegistry``,
etc.). It does not own any state of its own — it delegates to the
registries that the container has wired into it. This means there is
exactly one source of truth per subsystem, and the unified registry is
just a convenient query surface for orchestrators, dashboards, and
diagnostics.

Lookups are supported by name (string) or by type (the registered
service's class). The registry also exposes ``count()`` helpers for
health reporting.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class Named(Protocol):
    """Anything with a ``name`` attribute — used for type-safe lookups."""

    name: str


class UnifiedRegistry:
    """Read-only facade over every per-subsystem registry.

    Parameters:
        providers: The provider registry (or any object with ``all()``,
            ``names()``, ``get(name)``, ``__len__``).
        tools: The tool registry.
        workflows: The workflow registry.
        agents: Optional agent registry. Atlas does not yet ship one; if
            ``None``, agent queries return empty.
        skills: Optional skill registry. Atlas does not yet ship one; if
            ``None``, skill queries return empty.
    """

    def __init__(
        self,
        providers: Any = None,
        tools: Any = None,
        workflows: Any = None,
        agents: Any = None,
        skills: Any = None,
    ) -> None:
        self._registries: dict[str, Any] = {
            "providers": providers,
            "tools": tools,
            "workflows": workflows,
            "agents": agents,
            "skills": skills,
        }

    # ------------------------------------------------------------------
    # Generic lookup
    # ------------------------------------------------------------------

    def get(self, kind: str, name: str) -> Any | None:
        """Look up an item by kind and name.

        Args:
            kind: One of ``"providers"``, ``"tools"``, ``"workflows"``,
                ``"agents"``, ``"skills"``.
            name: The item name.

        Returns:
            The registered item, or ``None`` if not found.
        """
        registry = self._registries.get(kind)
        if registry is None:
            return None
        getter = getattr(registry, "get", None)
        if getter is None:
            return None
        return getter(name)

    def list(self, kind: str) -> list[Any]:
        """Return every registered item of ``kind``."""
        registry = self._registries.get(kind)
        if registry is None:
            return []
        all_method = getattr(registry, "all", None)
        if callable(all_method):
            return list(all_method())
        return []

    def names(self, kind: str) -> list[str]:
        """Return the sorted names of every registered item of ``kind``."""
        registry = self._registries.get(kind)
        if registry is None:
            return []
        names_method = getattr(registry, "names", None)
        if callable(names_method):
            return list(names_method())
        # Fallback: derive names from ``all()``.
        items = self.list(kind)
        return sorted(getattr(item, "name", getattr(item, "id", "")) for item in items)

    def count(self, kind: str) -> int:
        """Return the number of registered items of ``kind``."""
        registry = self._registries.get(kind)
        if registry is None:
            return 0
        len_fn = registry.__len__
        try:
            return len_fn()
        except TypeError:
            return len(self.list(kind))

    def contains(self, kind: str, name: str) -> bool:
        """Return ``True`` if ``name`` is registered under ``kind``."""
        return self.get(kind, name) is not None

    # ------------------------------------------------------------------
    # Typed convenience accessors
    # ------------------------------------------------------------------

    def providers(self) -> list[Any]:
        """Return every registered provider."""
        return self.list("providers")

    def tools(self) -> list[Any]:
        """Return every registered tool."""
        return self.list("tools")

    def workflows(self) -> list[Any]:
        """Return every registered workflow definition."""
        return self.list("workflows")

    def agents(self) -> list[Any]:
        """Return every registered agent."""
        return self.list("agents")

    def skills(self) -> list[Any]:
        """Return every registered skill."""
        return self.list("skills")

    def provider(self, name: str) -> Any | None:
        """Look up a provider by name."""
        return self.get("providers", name)

    def tool(self, name: str) -> Any | None:
        """Look up a tool by name."""
        return self.get("tools", name)

    def workflow(self, name: str) -> Any | None:
        """Look up a workflow by id."""
        return self.get("workflows", name)

    def agent(self, name: str) -> Any | None:
        """Look up an agent by name."""
        return self.get("agents", name)

    def skill(self, name: str) -> Any | None:
        """Look up a skill by name."""
        return self.get("skills", name)

    # ------------------------------------------------------------------
    # Aggregate reporting
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, int]:
        """Return a ``{kind: count}`` summary of every registry."""
        return {kind: self.count(kind) for kind in self._registries}

    def kinds(self) -> list[str]:
        """Return every registry kind known to this facade."""
        return list(self._registries)

    def __iter__(self) -> Iterator[tuple[str, list[Any]]]:
        for kind in self._registries:
            yield kind, self.list(kind)

    def __repr__(self) -> str:
        counts = self.summary()
        return (
            "<UnifiedRegistry " + " ".join(f"{k}={v}" for k, v in counts.items()) + ">"
        )


__all__ = ["Named", "UnifiedRegistry"]
