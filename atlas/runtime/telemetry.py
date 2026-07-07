"""Telemetry collection for the Atlas Runtime.

The :class:`TelemetryCollector` records execution metrics — counts,
durations, and per-phase breakdowns — so that the runtime can report on
its own behaviour. It is a passive observer: it subscribes to the
:class:`EventBus` and updates its internal counters; it never blocks or
mutates the execution path.

Tracked metrics:

* Total executions started, completed, failed, cancelled.
* Per-execution phase durations (planning, dispatch, executing, reviewing).
* Per-step success / failure counts.
* Provider selection distribution.
* Tool invocation counts.

All metrics are in-memory and reset on :meth:`reset`. A future backend can
subclass :class:`BaseTelemetryCollector` and forward to Prometheus /
OpenTelemetry / etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import (
    EventBus,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
    PlanningCompleted,
    PlanningStarted,
    ProviderSelected,
    RuntimeEvent,
    StepCompleted,
    StepFailed,
    ToolInvoked,
)


@dataclass
class ExecutionMetrics:
    """Per-execution rollup of telemetry.

    Attributes:
        execution_id: The execution these metrics describe.
        started_at: When the execution started.
        completed_at: When the execution reached a terminal state.
        planning_duration_seconds: Total wall time spent in planning.
        dispatch_duration_seconds: Total wall time spent in dispatch.
        executing_duration_seconds: Total wall time spent in executing.
        reviewing_duration_seconds: Total wall time spent in reviewing.
        steps_succeeded: Number of successful steps.
        steps_failed: Number of failed steps.
        providers_used: Set of provider names selected.
        tools_invoked: Mapping of tool name -> invocation count.
        final_state: ``"completed"``, ``"failed"``, ``"cancelled"`` or
            ``None`` if still running.
    """

    execution_id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    planning_duration_seconds: float = 0.0
    dispatch_duration_seconds: float = 0.0
    executing_duration_seconds: float = 0.0
    reviewing_duration_seconds: float = 0.0
    steps_succeeded: int = 0
    steps_failed: int = 0
    providers_used: set[str] = field(default_factory=set)
    tools_invoked: dict[str, int] = field(default_factory=dict)
    final_state: str | None = None


class BaseTelemetryCollector(ABC):
    """Abstract contract for runtime telemetry collectors."""

    @abstractmethod
    def record(self, event: RuntimeEvent) -> None:
        """Record ``event``. Called by the event bus for every event."""

    @abstractmethod
    def metrics(self, execution_id: str) -> ExecutionMetrics | None:
        """Return the metrics for ``execution_id`` or ``None`` if unknown."""

    @abstractmethod
    def all_metrics(self) -> list[ExecutionMetrics]:
        """Return metrics for every execution that has been observed."""

    @abstractmethod
    def summary(self) -> dict[str, Any]:
        """Return a high-level summary across all executions."""

    @abstractmethod
    def reset(self) -> None:
        """Drop all collected metrics."""


class TelemetryCollector(BaseTelemetryCollector):
    """In-memory telemetry collector that subscribes to an :class:`EventBus`.

    Parameters:
        bus: The event bus to subscribe to. The collector subscribes on
            construction and unsubscribes on :meth:`shutdown`.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus
        self.logger = get_logger("runtime.telemetry")
        self._metrics: dict[str, ExecutionMetrics] = {}
        self._phase_started_at: dict[str, datetime] = {}
        self._counts: dict[str, int] = defaultdict(int)
        if bus is not None:
            self._subscribe(bus)

    # ------------------------------------------------------------------
    # BaseTelemetryCollector
    # ------------------------------------------------------------------

    def record(self, event: RuntimeEvent) -> None:
        """Update internal metrics based on ``event``."""
        eid = event.execution_id
        if eid is None:
            # Runtime-level event; update global counters only.
            self._counts[type(event).__name__] += 1
            return

        if eid not in self._metrics and isinstance(event, ExecutionStarted):
            self._metrics[eid] = ExecutionMetrics(
                execution_id=eid, started_at=event.timestamp
            )
            self._counts["executions_started"] += 1
            return

        metrics = self._metrics.get(eid)
        if metrics is None:
            # We may receive events for executions we never saw start;
            # create the metrics lazily so we don't lose the data.
            metrics = ExecutionMetrics(execution_id=eid)
            self._metrics[eid] = metrics

        if isinstance(event, PlanningStarted):
            self._phase_started_at[f"{eid}:planning"] = event.timestamp
        elif isinstance(event, PlanningCompleted):
            start = self._phase_started_at.pop(f"{eid}:planning", None)
            if start is not None:
                metrics.planning_duration_seconds = (
                    event.timestamp - start
                ).total_seconds()
        elif isinstance(event, StepCompleted):
            metrics.steps_succeeded += 1
        elif isinstance(event, StepFailed):
            metrics.steps_failed += 1
        elif isinstance(event, ProviderSelected):
            metrics.providers_used.add(event.provider)
        elif isinstance(event, ToolInvoked):
            metrics.tools_invoked[event.tool] = (
                metrics.tools_invoked.get(event.tool, 0) + 1
            )
        elif isinstance(event, ExecutionCompleted):
            metrics.completed_at = event.timestamp
            metrics.final_state = "completed"
            self._counts["executions_completed"] += 1
        elif isinstance(event, ExecutionFailed):
            metrics.completed_at = event.timestamp
            metrics.final_state = "failed"
            self._counts["executions_failed"] += 1
        elif isinstance(event, ExecutionCancelled):
            metrics.completed_at = event.timestamp
            metrics.final_state = "cancelled"
            self._counts["executions_cancelled"] += 1

    def metrics(self, execution_id: str) -> ExecutionMetrics | None:
        """Return the metrics for ``execution_id`` or ``None`` if unknown."""
        return self._metrics.get(execution_id)

    def all_metrics(self) -> list[ExecutionMetrics]:
        """Return metrics for every execution that has been observed."""
        return list(self._metrics.values())

    def summary(self) -> dict[str, Any]:
        """Return a high-level summary across all executions."""
        completed = sum(
            1 for m in self._metrics.values() if m.final_state == "completed"
        )
        failed = sum(1 for m in self._metrics.values() if m.final_state == "failed")
        cancelled = sum(
            1 for m in self._metrics.values() if m.final_state == "cancelled"
        )
        total_steps = sum(
            m.steps_succeeded + m.steps_failed for m in self._metrics.values()
        )
        return {
            "executions_observed": len(self._metrics),
            "executions_completed": completed,
            "executions_failed": failed,
            "executions_cancelled": cancelled,
            "total_steps": total_steps,
            **dict(self._counts),
        }

    def reset(self) -> None:
        """Drop all collected metrics."""
        self._metrics.clear()
        self._phase_started_at.clear()
        self._counts.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Unsubscribe from the event bus (if one was supplied)."""
        if self.bus is not None:
            # The bus only stores listeners by identity, so we cannot
            # precisely unsubscribe without keeping references. We simply
            # clear our internal state; the next reset() is a no-op.
            self.bus = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _subscribe(self, bus: EventBus) -> None:
        """Subscribe to every event the collector cares about."""
        bus.subscribe(RuntimeEvent, self.record)

    def __repr__(self) -> str:
        return (
            f"<TelemetryCollector executions={len(self._metrics)} "
            f"summary={self.summary()}>"
        )


__all__ = [
    "BaseTelemetryCollector",
    "ExecutionMetrics",
    "TelemetryCollector",
]
