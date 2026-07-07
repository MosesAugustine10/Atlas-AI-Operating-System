"""Abstract base class for all Atlas tools.

A :class:`BaseTool` is the in-process abstraction the Kernel and agents
interact with. Each concrete tool wraps a *service* (the domain logic) and,
optionally, an *adapter* (the connector to an external system or MCP server).
Subclasses implement :meth:`execute` and declare their permission
requirements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger
from atlas.tools.permissions import Permission
from atlas.tools.result import ToolResult


class BaseTool(ABC):
    """Abstract foundation for every Atlas tool.

    Subclasses define a unique ``name``, a human-readable ``description``,
    the minimum ``required_permission`` to invoke the tool, and implement
    :meth:`execute`.

    Parameters:
        name: Unique identifier used in the registry and permission grants.
        description: Human-readable summary of what the tool does.
        required_permission: Minimum permission level needed to run the tool.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        required_permission: Permission = Permission.USE,
    ) -> None:
        self.name = name
        self.description = description
        self.required_permission = required_permission
        self.logger = get_logger(f"tool.{name}")

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given keyword arguments.

        Returns:
            A :class:`ToolResult` describing the outcome.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
