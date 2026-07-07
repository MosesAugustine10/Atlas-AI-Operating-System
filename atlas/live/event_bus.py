"""Unified event bus — wires every Atlas subsystem to emit events.

The :class:`LiveEventBus` extends the runtime :class:`EventBus` with
domain-specific event types and convenience methods for emitting them.
Every subsystem can publish events without knowing about each other.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import EventBus, RuntimeEvent


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str = "evt") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Live event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LiveEvent(RuntimeEvent):
    """Base class for live runtime events."""


@dataclass(frozen=True)
class GoalStarted(LiveEvent):
    """Emitted when a goal starts execution."""

    goal_id: str = ""
    description: str = ""


@dataclass(frozen=True)
class GoalFinished(LiveEvent):
    """Emitted when a goal finishes execution."""

    goal_id: str = ""
    status: str = ""
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class TaskStarted(LiveEvent):
    """Emitted when a task starts."""

    task_id: str = ""
    capability: str = ""


@dataclass(frozen=True)
class TaskCompleted(LiveEvent):
    """Emitted when a task completes."""

    task_id: str = ""
    success: bool = True
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class ProviderSelected(LiveEvent):
    """Emitted when a provider is selected."""

    provider: str = ""
    capability: str = ""


@dataclass(frozen=True)
class ProviderFailed(LiveEvent):
    """Emitted when a provider fails."""

    provider: str = ""
    error: str = ""


@dataclass(frozen=True)
class MemoryStored(LiveEvent):
    """Emitted when content is stored in memory."""

    category: str = ""
    entry_id: str = ""


@dataclass(frozen=True)
class KnowledgeIndexed(LiveEvent):
    """Emitted when content is indexed in knowledge."""

    document_id: str = ""
    source: str = ""


@dataclass(frozen=True)
class WorkflowStarted(LiveEvent):
    """Emitted when a workflow starts."""

    workflow_id: str = ""


@dataclass(frozen=True)
class WorkflowFinished(LiveEvent):
    """Emitted when a workflow finishes."""

    workflow_id: str = ""
    status: str = ""


@dataclass(frozen=True)
class ConnectorConnected(LiveEvent):
    """Emitted when an MCP connector connects."""

    connector: str = ""


@dataclass(frozen=True)
class ConnectorDisconnected(LiveEvent):
    """Emitted when an MCP connector disconnects."""

    connector: str = ""


@dataclass(frozen=True)
class ArtifactCreated(LiveEvent):
    """Emitted when an artifact is created."""

    artifact_id: str = ""
    artifact_type: str = ""


@dataclass(frozen=True)
class StreamProgress(LiveEvent):
    """Emitted for streaming progress updates."""

    stage: str = ""
    message: str = ""
    progress: float = 0.0


# ---------------------------------------------------------------------------
# Live event bus
# ---------------------------------------------------------------------------


class LiveEventBus:
    """Unified event bus for the live runtime.

    Wraps a runtime :class:`EventBus` and adds convenience methods for
    emitting live events.

    Parameters:
        bus: Optional existing :class:`EventBus`. A new one is created
            if omitted.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus if bus is not None else EventBus()
        self.logger = get_logger("live.event_bus")

    def publish(self, event: RuntimeEvent) -> None:
        """Publish ``event`` on the underlying bus."""
        self.bus.publish(event)

    def emit_goal_started(self, goal_id: str, description: str) -> None:
        self.publish(
            GoalStarted(
                execution_id=goal_id,
                goal_id=goal_id,
                description=description,
            )
        )

    def emit_goal_finished(
        self, goal_id: str, status: str, duration: float = 0.0
    ) -> None:
        self.publish(
            GoalFinished(
                execution_id=goal_id,
                goal_id=goal_id,
                status=status,
                duration_seconds=duration,
            )
        )

    def emit_task_started(self, task_id: str, capability: str) -> None:
        self.publish(
            TaskStarted(
                execution_id=None,
                task_id=task_id,
                capability=capability,
            )
        )

    def emit_task_completed(
        self, task_id: str, success: bool = True, duration: float = 0.0
    ) -> None:
        self.publish(
            TaskCompleted(
                execution_id=None,
                task_id=task_id,
                success=success,
                duration_seconds=duration,
            )
        )

    def emit_provider_selected(self, provider: str, capability: str = "") -> None:
        self.publish(
            ProviderSelected(
                execution_id=None,
                provider=provider,
                capability=capability,
            )
        )

    def emit_provider_failed(self, provider: str, error: str = "") -> None:
        self.publish(
            ProviderFailed(
                execution_id=None,
                provider=provider,
                error=error,
            )
        )

    def emit_memory_stored(self, category: str, entry_id: str = "") -> None:
        self.publish(
            MemoryStored(
                execution_id=None,
                category=category,
                entry_id=entry_id,
            )
        )

    def emit_knowledge_indexed(self, document_id: str, source: str = "") -> None:
        self.publish(
            KnowledgeIndexed(
                execution_id=None,
                document_id=document_id,
                source=source,
            )
        )

    def emit_workflow_started(self, workflow_id: str) -> None:
        self.publish(
            WorkflowStarted(
                execution_id=None,
                workflow_id=workflow_id,
            )
        )

    def emit_workflow_finished(self, workflow_id: str, status: str = "") -> None:
        self.publish(
            WorkflowFinished(
                execution_id=None,
                workflow_id=workflow_id,
                status=status,
            )
        )

    def emit_connector_connected(self, connector: str) -> None:
        self.publish(
            ConnectorConnected(
                execution_id=None,
                connector=connector,
            )
        )

    def emit_connector_disconnected(self, connector: str) -> None:
        self.publish(
            ConnectorDisconnected(
                execution_id=None,
                connector=connector,
            )
        )

    def emit_artifact_created(self, artifact_id: str, artifact_type: str = "") -> None:
        self.publish(
            ArtifactCreated(
                execution_id=None,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
            )
        )

    def emit_stream_progress(
        self, stage: str, message: str = "", progress: float = 0.0
    ) -> None:
        self.publish(
            StreamProgress(
                execution_id=None,
                stage=stage,
                message=message,
                progress=progress,
            )
        )

    def subscribe(self, topic: Any, listener: Any) -> None:
        """Subscribe a listener to a topic on the underlying bus."""
        self.bus.subscribe(topic, listener)

    def history(self) -> list[RuntimeEvent]:
        """Return every event ever published."""
        return self.bus.history()

    def history_for(self, execution_id: str) -> list[RuntimeEvent]:
        """Return every event for ``execution_id``."""
        return self.bus.history_for(execution_id)

    def clear(self) -> None:
        """Clear the bus history and listeners."""
        self.bus.clear()

    def __len__(self) -> int:
        return len(self.bus.history())

    def __repr__(self) -> str:
        return f"<LiveEventBus events={len(self)}>"


__all__ = [
    "ArtifactCreated",
    "ConnectorConnected",
    "ConnectorDisconnected",
    "GoalFinished",
    "GoalStarted",
    "KnowledgeIndexed",
    "LiveEvent",
    "LiveEventBus",
    "MemoryStored",
    "ProviderFailed",
    "ProviderSelected",
    "StreamProgress",
    "TaskCompleted",
    "TaskStarted",
    "WorkflowFinished",
    "WorkflowStarted",
]
