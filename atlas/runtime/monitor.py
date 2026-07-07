"""System monitor for the Atlas Runtime.

The :class:`SystemMonitor` watches the runtime's health: queue depth,
active executions, failure rate, and per-phase latencies. It exposes a
snapshot :class:`HealthReport` that the runtime can use to decide whether
to admit new requests, shed load, or alert an operator.

The monitor is a passive observer: it pulls data from the
:class:`TelemetryCollector` and the :class:`ExecutionQueue` on demand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.queue import ExecutionQueue
from atlas.runtime.telemetry import TelemetryCollector


@dataclass(frozen=True)
class HealthReport:
    """A point-in-time snapshot of runtime health.

    Attributes:
        timestamp: When the report was generated.
        queue_depth: Number of pending requests.
        active_executions: Number of executions currently in flight.
        completed_executions: Total executions that have completed.
        failed_executions: Total executions that have failed.
        cancelled_executions: Total executions that have been cancelled.
        failure_rate: ``failed / (completed + failed)``. ``0.0`` if no data.
        avg_planning_seconds: Average planning phase duration.
        avg_executing_seconds: Average executing phase duration.
        avg_reviewing_seconds: Average reviewing phase duration.
        status: One of ``"healthy"``, ``"degraded"``, ``"unhealthy"``.
        warnings: List of human-readable warning messages.
    """

    timestamp: datetime
    queue_depth: int = 0
    active_executions: int = 0
    completed_executions: int = 0
    failed_executions: int = 0
    cancelled_executions: int = 0
    failure_rate: float = 0.0
    avg_planning_seconds: float = 0.0
    avg_executing_seconds: float = 0.0
    avg_reviewing_seconds: float = 0.0
    status: str = "healthy"
    warnings: list[str] = field(default_factory=list)


class SystemMonitor:
    """Watches runtime health and produces :class:`HealthReport` snapshots.

    Parameters:
        telemetry: The :class:`TelemetryCollector` to pull metrics from.
        queue: The :class:`ExecutionQueue` to pull depth from.
        failure_rate_threshold: Failure rate above which the status is
            ``"degraded"``. Defaults to ``0.2``.
        unhealthy_failure_rate: Failure rate above which the status is
            ``"unhealthy"``. Defaults to ``0.5``.
        max_active_executions: Soft cap on active executions. Exceeding
            this triggers a warning. Defaults to ``100``.
    """

    def __init__(
        self,
        telemetry: TelemetryCollector,
        queue: ExecutionQueue,
        failure_rate_threshold: float = 0.2,
        unhealthy_failure_rate: float = 0.5,
        max_active_executions: int = 100,
    ) -> None:
        self.telemetry = telemetry
        self.queue = queue
        self.failure_rate_threshold = failure_rate_threshold
        self.unhealthy_failure_rate = unhealthy_failure_rate
        self.max_active_executions = max_active_executions
        self.logger = get_logger("runtime.monitor")

    def snapshot(self) -> HealthReport:
        """Produce a :class:`HealthReport` reflecting the current state."""
        from datetime import UTC, datetime

        summary = self.telemetry.summary()
        completed = summary.get("executions_completed", 0)
        failed = summary.get("executions_failed", 0)
        cancelled = summary.get("executions_cancelled", 0)
        observed = summary.get("executions_observed", 0)
        active = max(0, observed - completed - failed - cancelled)

        settled = completed + failed
        failure_rate = failed / settled if settled > 0 else 0.0

        # Average phase durations across completed executions.
        planning_durations: list[float] = []
        executing_durations: list[float] = []
        reviewing_durations: list[float] = []
        for metrics in self.telemetry.all_metrics():
            planning_durations.append(metrics.planning_duration_seconds)
            executing_durations.append(metrics.executing_duration_seconds)
            reviewing_durations.append(metrics.reviewing_duration_seconds)

        avg_planning = (
            sum(planning_durations) / len(planning_durations)
            if planning_durations
            else 0.0
        )
        avg_executing = (
            sum(executing_durations) / len(executing_durations)
            if executing_durations
            else 0.0
        )
        avg_reviewing = (
            sum(reviewing_durations) / len(reviewing_durations)
            if reviewing_durations
            else 0.0
        )

        warnings: list[str] = []
        status = "healthy"
        if failure_rate >= self.unhealthy_failure_rate and settled > 0:
            status = "unhealthy"
            warnings.append(
                f"failure_rate={failure_rate:.2f} exceeds "
                f"unhealthy threshold {self.unhealthy_failure_rate:.2f}"
            )
        elif failure_rate >= self.failure_rate_threshold and settled > 0:
            status = "degraded"
            warnings.append(
                f"failure_rate={failure_rate:.2f} exceeds "
                f"degraded threshold {self.failure_rate_threshold:.2f}"
            )
        if active > self.max_active_executions:
            if status == "healthy":
                status = "degraded"
            warnings.append(
                f"active_executions={active} exceeds soft cap "
                f"{self.max_active_executions}"
            )

        return HealthReport(
            timestamp=datetime.now(UTC),
            queue_depth=len(self.queue),
            active_executions=active,
            completed_executions=completed,
            failed_executions=failed,
            cancelled_executions=cancelled,
            failure_rate=failure_rate,
            avg_planning_seconds=avg_planning,
            avg_executing_seconds=avg_executing,
            avg_reviewing_seconds=avg_reviewing,
            status=status,
            warnings=warnings,
        )

    def is_healthy(self) -> bool:
        """Return ``True`` if the latest snapshot's status is ``"healthy"``."""
        return self.snapshot().status == "healthy"

    def to_dict(self) -> dict[str, Any]:
        """Return the latest snapshot as a flat dict (for logging / export)."""
        report = self.snapshot()
        return {
            "status": report.status,
            "queue_depth": report.queue_depth,
            "active_executions": report.active_executions,
            "completed_executions": report.completed_executions,
            "failed_executions": report.failed_executions,
            "cancelled_executions": report.cancelled_executions,
            "failure_rate": report.failure_rate,
            "avg_planning_seconds": report.avg_planning_seconds,
            "avg_executing_seconds": report.avg_executing_seconds,
            "avg_reviewing_seconds": report.avg_reviewing_seconds,
            "warnings": list(report.warnings),
        }

    def __repr__(self) -> str:
        return f"<SystemMonitor status={self.snapshot().status!r}>"


__all__ = ["HealthReport", "SystemMonitor"]
