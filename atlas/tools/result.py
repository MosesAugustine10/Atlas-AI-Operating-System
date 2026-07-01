"""Tool execution result model.

The :class:`ToolResult` is the canonical return type for every tool
invocation in Atlas. Returning a structured result — rather than a raw
value — lets the Kernel and Tool Manager handle success and failure
uniformly and lets results be inspected, logged, and routed downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """The outcome of a single tool invocation.

    Attributes:
        success: Whether the tool call completed without error.
        output: The primary payload returned by the tool on success.
        error: Error message populated when ``success`` is ``False``.
        metadata: Free-form diagnostic information (latency, source, etc.).
    """

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: Any = None, **metadata: Any) -> ToolResult:
        """Build a successful result."""
        return cls(success=True, output=output, metadata=dict(metadata))

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> ToolResult:
        """Build a failed result with a descriptive error."""
        return cls(success=False, error=error, metadata=dict(metadata))

    def is_ok(self) -> bool:
        """Return ``True`` when the result represents success."""
        return self.success

    def is_error(self) -> bool:
        """Return ``True`` when the result represents a failure."""
        return not self.success
