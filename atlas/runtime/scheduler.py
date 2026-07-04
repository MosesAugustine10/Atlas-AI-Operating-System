"""Runtime scheduler — triggers executions on a cadence.

The :class:`RuntimeScheduler` is a thin wrapper around an
:class:`ExecutionQueue` that enqueues :class:`ScheduledTask` items at the
appropriate time. It is the runtime analog of the workflow engine's
:class:`InMemoryScheduler`, but instead of triggering workflow runs it
enqueues arbitrary request strings into the runtime's queue.

Supported cadences:

* :attr:`ScheduleKind.ONE_TIME` — enqueue once at ``run_at``.
* :attr:`ScheduleKind.INTERVAL` — enqueue every ``interval_seconds``
  starting at ``next_run_at``.
* :attr:`ScheduleKind.CRON` — placeholder; advances 24 hours per fire.

The scheduler is in-process and deterministic. For production use, wrap
it in a concrete adapter that delegates to APScheduler / Celery beat /
Kubernetes CronJobs / etc.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.queue import ExecutionQueue, ExecutionRequest


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "sched") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


class ScheduleKind(enum.StrEnum):
    """Trigger kinds supported by the runtime scheduler.

    Attributes:
        ONE_TIME: Fire once at a fixed timestamp.
        INTERVAL: Fire on a fixed cadence (every ``interval_seconds``).
        CRON: Fire according to a (simplified) cron expression.
    """

    ONE_TIME = "one_time"
    INTERVAL = "interval"
    CRON = "cron"


@dataclass
class ScheduledTask:
    """A scheduled trigger that enqueues a request on a cadence.

    Attributes:
        id: Unique schedule identifier.
        request: The request string to enqueue when the schedule fires.
        kind: The :class:`ScheduleKind` governing when the schedule fires.
        interval_seconds: Cadence in seconds when ``kind`` is INTERVAL.
        run_at: Trigger timestamp when ``kind`` is ONE_TIME.
        cron_expr: Cron expression when ``kind`` is CRON.
        next_run_at: When the schedule should next fire. ``None`` disables it.
        last_run_at: When the schedule last fired.
        enabled: Master toggle for the schedule.
        metadata: Free-form metadata propagated to enqueued requests.
    """

    id: str = field(default_factory=lambda: _new_id("sched"))
    request: str = ""
    kind: ScheduleKind = ScheduleKind.ONE_TIME
    interval_seconds: int | None = None
    run_at: datetime | None = None
    cron_expr: str | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeScheduler:
    """In-process scheduler that enqueues :class:`ExecutionRequest` items.

    Parameters:
        queue: The :class:`ExecutionQueue` to enqueue into on tick.
    """

    def __init__(self, queue: ExecutionQueue) -> None:
        self.queue = queue
        self._schedules: dict[str, ScheduledTask] = {}
        self.logger = get_logger("runtime.scheduler")

    def register(self, task: ScheduledTask) -> ScheduledTask:
        """Register ``task`` with the scheduler.

        Raises:
            ValueError: If a task with the same id is already registered.
        """
        if task.id in self._schedules:
            raise ValueError(f"Schedule already registered: {task.id!r}")
        normalized = self._normalize(task)
        self._schedules[task.id] = normalized
        self.logger.info(
            "Registered schedule %s (kind=%s, next=%s)",
            task.id,
            task.kind.value,
            normalized.next_run_at.isoformat() if normalized.next_run_at else "none",
        )
        return normalized

    def unregister(self, task_id: str) -> bool:
        """Remove a schedule by id. Return ``True`` if it existed."""
        existed = self._schedules.pop(task_id, None) is not None
        if existed:
            self.logger.info("Unregistered schedule: %s", task_id)
        return existed

    def get(self, task_id: str) -> ScheduledTask | None:
        """Look up a schedule by id."""
        return self._schedules.get(task_id)

    def contains(self, task_id: str) -> bool:
        """Return ``True`` if a schedule with ``task_id`` is registered."""
        return task_id in self._schedules

    def all(self) -> list[ScheduledTask]:
        """Return every registered schedule, ordered by id."""
        return [self._schedules[sid] for sid in sorted(self._schedules)]

    def names(self) -> list[str]:
        """Return a sorted list of all registered schedule ids."""
        return sorted(self._schedules)

    def due(self, now: datetime | None = None) -> list[ScheduledTask]:
        """Return schedules that should fire at or before ``now``."""
        moment = now or _utcnow()
        return [
            task
            for task in self.all()
            if task.enabled
            and task.next_run_at is not None
            and task.next_run_at <= moment
        ]

    def tick(self, now: datetime | None = None) -> list[ExecutionRequest]:
        """Fire every due schedule and return the enqueued requests.

        For each due schedule, the scheduler:

        1. Enqueues an :class:`ExecutionRequest` carrying the schedule's
           request string and metadata.
        2. Advances the schedule's state (disabled for ONE_TIME, advanced
           for INTERVAL / CRON).
        """
        moment = now or _utcnow()
        enqueued: list[ExecutionRequest] = []
        for task in self.due(moment):
            request = ExecutionRequest(
                request=task.request,
                metadata={
                    **task.metadata,
                    "schedule_id": task.id,
                    "scheduled_at": (
                        task.next_run_at.isoformat() if task.next_run_at else None
                    ),
                },
            )
            enqueued.append(self.queue.enqueue(request))
            self._advance(task.id, moment)
        return enqueued

    def __len__(self) -> int:
        return len(self._schedules)

    def __repr__(self) -> str:
        return f"<RuntimeScheduler count={len(self)}>"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(task: ScheduledTask) -> ScheduledTask:
        """Fill in a sensible ``next_run_at`` if none was supplied."""
        if task.next_run_at is not None:
            return task
        if task.kind is ScheduleKind.ONE_TIME:
            if task.run_at is None:
                return task
            return ScheduledTask(**{**task.__dict__, "next_run_at": task.run_at})
        if task.kind is ScheduleKind.INTERVAL:
            return ScheduledTask(**{**task.__dict__, "next_run_at": _utcnow()})
        return task

    def _advance(self, task_id: str, ran_at: datetime) -> ScheduledTask | None:
        task = self._schedules.get(task_id)
        if task is None:
            return None
        if task.kind is ScheduleKind.ONE_TIME:
            updated = ScheduledTask(
                **{
                    **task.__dict__,
                    "last_run_at": ran_at,
                    "next_run_at": None,
                    "enabled": False,
                }
            )
        elif task.kind is ScheduleKind.INTERVAL:
            interval = task.interval_seconds or 0
            next_at = ran_at + timedelta(seconds=interval)
            updated = ScheduledTask(
                **{
                    **task.__dict__,
                    "last_run_at": ran_at,
                    "next_run_at": next_at,
                }
            )
        else:  # CRON placeholder — advance 24h
            next_at = ran_at + timedelta(hours=24)
            updated = ScheduledTask(
                **{
                    **task.__dict__,
                    "last_run_at": ran_at,
                    "next_run_at": next_at,
                }
            )
        self._schedules[task_id] = updated
        return updated


__all__ = ["RuntimeScheduler", "ScheduleKind", "ScheduledTask"]
