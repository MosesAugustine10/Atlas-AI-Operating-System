"""Memory integration — auto-store everything in the Memory Engine.

The :class:`MemoryIntegrator` wraps the :class:`MemoryEngine` and
provides convenience methods for storing execution outcomes, reasoning
chains, tool outputs, provider outputs, errors, and lessons. Every
call emits a :class:`MemoryStored` event on the live event bus.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.live.event_bus import LiveEventBus


class MemoryIntegrator:
    """Auto-stores execution data in the Memory Engine.

    Parameters:
        memory: The :class:`MemoryEngine` (or compatible). Must have a
            ``remember(content, category, source, tags, **metadata)``
            method.
        event_bus: Optional :class:`LiveEventBus` for emitting events.
    """

    def __init__(
        self,
        memory: Any = None,
        event_bus: LiveEventBus | None = None,
    ) -> None:
        self.memory = memory
        self.event_bus = event_bus if event_bus is not None else LiveEventBus()
        self.logger = get_logger("live.memory")

    def store_goal(
        self,
        goal_id: str,
        description: str,
        status: str,
    ) -> None:
        """Store a goal in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={"goal_id": goal_id, "description": description, "status": status},
            source="live.memory",
            tags=["goal", status],
        )
        self.event_bus.emit_memory_stored("goal", goal_id)

    def store_plan(self, goal_id: str, plan: Any) -> None:
        """Store an execution plan in memory."""
        if self.memory is None:
            return
        tasks = getattr(plan, "tasks", [])
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "plan_id": getattr(plan, "id", ""),
                "task_count": len(tasks),
                "task_descriptions": [getattr(t, "description", "") for t in tasks],
            },
            source="live.memory",
            tags=["plan"],
        )
        self.event_bus.emit_memory_stored("plan", getattr(plan, "id", ""))

    def store_reasoning(self, goal_id: str, chain: Any) -> None:
        """Store a reasoning chain in memory."""
        if self.memory is None:
            return
        steps = getattr(chain, "steps", [])
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "chain_id": getattr(chain, "id", ""),
                "conclusion": getattr(chain, "conclusion", ""),
                "step_count": len(steps),
                "confidence": getattr(chain, "overall_confidence", 0.0),
            },
            source="live.memory",
            tags=["reasoning"],
        )
        self.event_bus.emit_memory_stored("reasoning", getattr(chain, "id", ""))

    def store_tool_output(
        self,
        goal_id: str,
        tool: str,
        output: Any,
        success: bool = True,
    ) -> None:
        """Store a tool output in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "tool": tool,
                "output": str(output)[:500],
                "success": success,
            },
            source="live.memory",
            tags=["tool_output", tool, "success" if success else "failure"],
        )
        self.event_bus.emit_memory_stored("tool_output")

    def store_provider_output(
        self,
        goal_id: str,
        provider: str,
        text: str,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Store a provider output in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "provider": provider,
                "text": text[:500],
                "usage": usage or {},
            },
            source="live.memory",
            tags=["provider_output", provider],
        )
        self.event_bus.emit_memory_stored("provider_output")

    def store_error(
        self,
        goal_id: str,
        error: str,
        context: str = "",
    ) -> None:
        """Store an error in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "error": error,
                "context": context,
            },
            source="live.memory",
            tags=["error"],
        )
        self.event_bus.emit_memory_stored("error")

    def store_lesson(
        self,
        lesson_id: str,
        content: str,
        category: str,
    ) -> None:
        """Store a lesson in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={
                "lesson_id": lesson_id,
                "content": content,
                "category": category,
            },
            source="live.memory",
            tags=["lesson", category],
        )
        self.event_bus.emit_memory_stored("lesson", lesson_id)

    def store_artifact(
        self,
        goal_id: str,
        artifact_id: str,
        name: str,
        artifact_type: str,
    ) -> None:
        """Store an artifact reference in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "artifact_id": artifact_id,
                "name": name,
                "type": artifact_type,
            },
            source="live.memory",
            tags=["artifact", artifact_type],
        )
        self.event_bus.emit_memory_stored("artifact", artifact_id)

    def store_metrics(
        self,
        goal_id: str,
        duration: float,
        tasks_completed: int,
        tasks_failed: int,
    ) -> None:
        """Store execution metrics in memory."""
        if self.memory is None:
            return
        self.memory.remember(
            content={
                "goal_id": goal_id,
                "duration_seconds": duration,
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
            },
            source="live.memory",
            tags=["metrics"],
        )
        self.event_bus.emit_memory_stored("metrics")

    def __repr__(self) -> str:
        return f"<MemoryIntegrator has_memory={self.memory is not None}>"


__all__ = ["MemoryIntegrator"]
