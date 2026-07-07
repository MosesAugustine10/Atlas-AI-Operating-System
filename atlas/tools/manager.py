"""Tool manager — the controlled gateway for tool execution.

The :class:`ToolManager` is the single entry point through which the Kernel
and agents invoke tools. It enforces permission checks before any dispatch,
logs each invocation, and returns a :class:`~atlas.tools.result.ToolResult`
for every call — including permission denials and unknown-tool lookups.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.tools.base import BaseTool
from atlas.tools.permissions import Permission, Permissions
from atlas.tools.registry import ToolRegistry
from atlas.tools.result import ToolResult


class ToolManager:
    """Gateway that dispatches tool calls after enforcing permissions.

    Parameters:
        registry: The tool registry. A new empty one is created if omitted.
        permissions: The permission model. A default-USE model is created
            if omitted.
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        permissions: Permissions | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.permissions = permissions or Permissions()
        self.logger = get_logger("tool.manager")

    def register(self, tool: BaseTool) -> ToolManager:
        """Register a tool with the manager's registry."""
        self.registry.register(tool)
        self.logger.info("Registered tool: %s", tool.name)
        return self

    def grant(self, tool: str, level: Permission) -> ToolManager:
        """Grant a permission level for a tool."""
        self.permissions.grant(tool, level)
        return self

    def check(self, tool: str, required: Permission | None = None) -> bool:
        """Return ``True`` if ``tool`` may be invoked at the required level.

        If ``required`` is ``None``, the tool's own
        :attr:`~atlas.tools.base.BaseTool.required_permission` is used.
        """
        instance = self.registry.get(tool)
        if instance is None:
            return False
        required_level = (
            required if required is not None else instance.required_permission
        )
        return self.permissions.check(tool, required_level)

    def execute(self, tool: str, **kwargs: Any) -> ToolResult:
        """Invoke ``tool`` with ``kwargs`` after passing the permission gate.

        Returns a :class:`ToolResult` in all cases:

        - Unknown tool → ``ToolResult.fail``.
        - Permission denied → ``ToolResult.fail``.
        - Successful run → the tool's own :class:`ToolResult`.
        - Tool raises → ``ToolResult.fail`` capturing the exception message.
        """
        instance = self.registry.get(tool)
        if instance is None:
            self.logger.warning("Unknown tool requested: %s", tool)
            return ToolResult.fail(f"Unknown tool: {tool}")

        if not self.check(tool):
            self.logger.warning("Permission denied for tool: %s", tool)
            return ToolResult.fail(f"Permission denied for tool: {tool}")

        self.logger.info("Executing tool: %s", tool)
        try:
            return instance.execute(**kwargs)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Tool %s raised: %s", tool, exc)
            return ToolResult.fail(f"{type(exc).__name__}: {exc}")
