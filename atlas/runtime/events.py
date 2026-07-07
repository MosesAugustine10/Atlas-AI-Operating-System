"""Runtime lifecycle events and the in-process event bus.

This module is a *leaf* in the runtime package dependency graph. It defines:

* :class:`RuntimeEvent` — the frozen dataclass that every emitted event
  inherits from.
* Concrete event types for every lifecycle phase
  (:class:`RequestReceived`, :class:`PlanningStarted`, etc.).
* :class:`EventBus` — a synchronous in-process pub/sub bus with topic
  filtering and ordered, exception-isolated dispatch.

The bus is deliberately synchronous and in-process. It is not a message
queue and it does not guarantee at-least-once delivery across process
boundaries. For cross-process eventing, wrap the bus in a concrete
adapter that forwards to Kafka / RabbitMQ / etc.

Listeners are plain callables that accept a :class:`RuntimeEvent`. They are
invoked in registration order; a raising listener is logged and skipped
but does not stop the dispatch to subsequent listeners.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from atlas.core.logger import get_logger


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "evt") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeEvent:
    """Base class for every runtime event.

    Attributes:
        event_id: Unique identifier for this event.
        execution_id: Identifier of the execution this event belongs to.
            ``None`` for runtime-level events (e.g. scheduler ticks).
        timestamp: When the event was emitted.
        payload: Free-form event-specific payload.
    """

    event_id: str = field(default_factory=lambda: _new_id("evt"))
    execution_id: str | None = None
    timestamp: datetime = field(default_factory=_utcnow)
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Concrete lifecycle events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RequestReceived(RuntimeEvent):
    """Emitted when the runtime accepts a new user request."""

    request: str = ""


@dataclass(frozen=True)
class ContextCreated(RuntimeEvent):
    """Emitted when an execution context has been assembled."""


@dataclass(frozen=True)
class SessionOpened(RuntimeEvent):
    """Emitted when an execution session has been opened."""


@dataclass(frozen=True)
class PlanningStarted(RuntimeEvent):
    """Emitted before the planner decomposes the goal."""


@dataclass(frozen=True)
class PlanningCompleted(RuntimeEvent):
    """Emitted after the planner has produced a task list."""

    task_count: int = 0


@dataclass(frozen=True)
class DispatchStarted(RuntimeEvent):
    """Emitted before the dispatcher selects agents / workflows / providers."""


@dataclass(frozen=True)
class DispatchCompleted(RuntimeEvent):
    """Emitted after dispatch decisions have been made."""


@dataclass(frozen=True)
class ExecutionStarted(RuntimeEvent):
    """Emitted before the executor runs the first step."""


@dataclass(frozen=True)
class StepStarted(RuntimeEvent):
    """Emitted before a single step is executed."""

    step_id: str = ""


@dataclass(frozen=True)
class StepCompleted(RuntimeEvent):
    """Emitted after a single step finishes successfully."""

    step_id: str = ""
    output: Any = None


@dataclass(frozen=True)
class StepFailed(RuntimeEvent):
    """Emitted when a single step raises or returns an error."""

    step_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class ExecutionPaused(RuntimeEvent):
    """Emitted when the execution is paused."""


@dataclass(frozen=True)
class ExecutionResumed(RuntimeEvent):
    """Emitted when the execution is resumed."""


@dataclass(frozen=True)
class ReviewStarted(RuntimeEvent):
    """Emitted before the review / reflection phase."""


@dataclass(frozen=True)
class ReviewCompleted(RuntimeEvent):
    """Emitted after the review / reflection phase."""


@dataclass(frozen=True)
class ExecutionCompleted(RuntimeEvent):
    """Emitted when the execution finishes successfully."""

    response: Any = None


@dataclass(frozen=True)
class ExecutionFailed(RuntimeEvent):
    """Emitted when the execution fails terminally."""

    error: str = ""


@dataclass(frozen=True)
class ExecutionCancelled(RuntimeEvent):
    """Emitted when the execution is cancelled by an operator."""


@dataclass(frozen=True)
class MemoryUpdated(RuntimeEvent):
    """Emitted after the memory engine has been updated."""

    category: str = ""


@dataclass(frozen=True)
class KnowledgeUpdated(RuntimeEvent):
    """Emitted after the knowledge engine has been updated."""


@dataclass(frozen=True)
class ReflectionTriggered(RuntimeEvent):
    """Emitted when a reflection cycle is requested."""


@dataclass(frozen=True)
class ProviderSelected(RuntimeEvent):
    """Emitted after a provider has been selected for a request."""

    provider: str = ""


@dataclass(frozen=True)
class ToolInvoked(RuntimeEvent):
    """Emitted after a tool has been invoked."""

    tool: str = ""
    success: bool = True


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


Listener = Callable[[RuntimeEvent], None]
E = TypeVar("E", bound=RuntimeEvent)
Topic = type[RuntimeEvent] | str


class EventBus:
    """Synchronous in-process event bus with topic filtering.

    Listeners can subscribe to:

    * A specific event type (e.g. ``StepCompleted``) — they will only be
      invoked for events of that type or its subclasses.
    * A string topic — they will only be invoked for events whose
      ``event_id`` matches the topic (rarely used).
    * The wildcard ``"*"`` — they will be invoked for every event.

    Listeners are invoked in registration order. A raising listener is
    logged and skipped but does not stop the dispatch to subsequent
    listeners.
    """

    def __init__(self) -> None:
        self._listeners: dict[Topic, list[Listener]] = defaultdict(list)
        self._history: list[RuntimeEvent] = []
        self.logger = get_logger("runtime.events")
        self._suspended: bool = False

    def subscribe(self, topic: Topic, listener: Listener) -> None:
        """Register ``listener`` to receive events matching ``topic``.

        Raises:
            TypeError: If ``listener`` is not callable.
        """
        if not callable(listener):
            raise TypeError("listener must be callable")
        self._listeners[topic].append(listener)
        self.logger.debug(
            "Subscribed listener %s to topic %s",
            getattr(listener, "__name__", repr(listener)),
            self._topic_name(topic),
        )

    def unsubscribe(self, topic: Topic, listener: Listener) -> bool:
        """Remove ``listener`` from ``topic``. Return ``True`` if it was registered."""
        bucket = self._listeners.get(topic, [])
        try:
            bucket.remove(listener)
        except ValueError:
            return False
        return True

    def publish(self, event: RuntimeEvent) -> None:
        """Dispatch ``event`` to every matching listener.

        If the bus is suspended (see :meth:`suspend`), the event is recorded
        in history but not dispatched. This is useful for replay scenarios.
        """
        self._history.append(event)
        if self._suspended:
            return
        invoked = 0
        for topic in self._matching_topics(event):
            for listener in list(self._listeners.get(topic, [])):
                try:
                    listener(event)
                except Exception as exc:  # noqa: BLE001 — isolate listeners
                    self.logger.warning(
                        "Listener %s raised on event %s: %s",
                        getattr(listener, "__name__", repr(listener)),
                        type(event).__name__,
                        exc,
                    )
                invoked += 1
        self.logger.debug(
            "Published %s to %d listener(s)",
            type(event).__name__,
            invoked,
        )

    def history(self) -> list[RuntimeEvent]:
        """Return a copy of every event ever published."""
        return list(self._history)

    def history_for(self, execution_id: str) -> list[RuntimeEvent]:
        """Return every event for a given execution."""
        return [event for event in self._history if event.execution_id == execution_id]

    def clear(self) -> None:
        """Drop history and all listener subscriptions."""
        self._listeners.clear()
        self._history.clear()

    def suspend(self) -> None:
        """Suspend dispatch. Events are still recorded in history."""
        self._suspended = True

    def resume_dispatch(self) -> None:
        """Resume dispatch after :meth:`suspend`."""
        self._suspended = False

    def listener_count(self, topic: Topic | None = None) -> int:
        """Return the number of registered listeners.

        If ``topic`` is ``None``, returns the total across all topics.
        """
        if topic is None:
            return sum(len(v) for v in self._listeners.values())
        return len(self._listeners.get(topic, []))

    def topics(self) -> list[Topic]:
        """Return every topic that has at least one listener."""
        return [t for t, bucket in self._listeners.items() if bucket]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _topic_name(topic: Topic) -> str:
        if isinstance(topic, str):
            return topic
        return topic.__name__

    def _matching_topics(self, event: RuntimeEvent) -> Iterable[Topic]:
        """Yield every topic that ``event`` matches."""
        yield "*"
        for topic in self._listeners:
            if topic == "*":
                continue
            if isinstance(topic, str):
                # String topics only match exact event_id (rarely used).
                if event.event_id == topic:
                    yield topic
            else:
                if isinstance(event, topic):
                    yield topic

    def __repr__(self) -> str:
        return (
            f"<EventBus listeners={self.listener_count()} "
            f"history={len(self._history)}>"
        )


__all__ = [
    "ContextCreated",
    "DispatchCompleted",
    "DispatchStarted",
    "EventBus",
    "ExecutionCancelled",
    "ExecutionCompleted",
    "ExecutionFailed",
    "ExecutionPaused",
    "ExecutionResumed",
    "ExecutionStarted",
    "KnowledgeUpdated",
    "MemoryUpdated",
    "PlanningCompleted",
    "PlanningStarted",
    "ProviderSelected",
    "ReflectionTriggered",
    "RequestReceived",
    "ReviewCompleted",
    "ReviewStarted",
    "RuntimeEvent",
    "SessionOpened",
    "StepCompleted",
    "StepFailed",
    "StepStarted",
    "ToolInvoked",
]
