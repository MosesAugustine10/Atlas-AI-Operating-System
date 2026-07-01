"""Tool registry — the catalog of tools available to the Kernel.

The :class:`ToolRegistry` holds the set of registered :class:`BaseTool`
instances and supports lookup by name. Registration is explicit so that
tools are only available when they have been deliberately added — matching
Atlas's allowlist philosophy.
"""

from __future__ import annotations

from collections.abc import Iterator

from atlas.tools.base import BaseTool


class ToolRegistry:
    """In-memory catalog of registered tools.

    Tools are keyed by their unique ``name``. Registering a duplicate name
    raises :class:`ValueError` to prevent silent shadowing.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> ToolRegistry:
        """Register a tool. Returns self for chaining.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name!r}")
        self._tools[tool.name] = tool
        return self

    def unregister(self, name: str) -> ToolRegistry:
        """Remove a tool by name. Returns self for chaining."""
        self._tools.pop(name, None)
        return self

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name, returning ``None`` if not found."""
        return self._tools.get(name)

    def contains(self, name: str) -> bool:
        """Return ``True`` if a tool with ``name`` is registered."""
        return name in self._tools

    def names(self) -> list[str]:
        """Return a sorted list of all registered tool names."""
        return sorted(self._tools)

    def all(self) -> list[BaseTool]:
        """Return every registered tool, ordered by name."""
        return [self._tools[name] for name in self.names()]

    def __iter__(self) -> Iterator[BaseTool]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._tools)
