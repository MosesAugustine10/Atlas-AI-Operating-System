"""Deterministic in-memory workflow scheduler.

The :class:`InMemoryScheduler` is the default :class:`BaseScheduler`
implementation. It keeps every :class:`WorkflowSchedule` in memory and
answers "due?" queries deterministically by comparing each schedule's
:attr:`next_run_at` to the supplied "now" timestamp.

This is a placeholder scheduler: it does not integrate with any external
cron daemon or job queue, and it does not persist schedules across
process restarts. Its job is to give the engine a deterministic, testable
notion of "what should fire now" so that scheduled execution can be
exercised end-to-end without external dependencies.

Supported schedule kinds:

* :attr:`ScheduleKind.ONE_TIME` — fires once at :attr:`run_at`. After
  firing, the schedule is disabled (``enabled = False``).
* :attr:`ScheduleKind.INTERVAL` — fires every :attr:`interval_seconds`
  starting at :attr:`next_run_at` (or ``now`` if unset). After firing,
  :attr:`next_run_at` is advanced by :attr:`interval_seconds`.
* :attr:`ScheduleKind.CRON` — placeholder. The cron expression is parsed
  minimally: if :attr:`next_run_at` is set, the schedule fires at that
  time and is then advanced by a fixed 24 hours (so daily cadences work
  for testing). A full cron parser can be swapped in later without
  changing the engine contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atlas.workflows.base import BaseScheduler
from atlas.workflows.models import ScheduleKind, WorkflowSchedule


class InMemoryScheduler(BaseScheduler):
    """Deterministic in-memory scheduler.

    Schedules are keyed by their unique ``id``. Registering a duplicate id
    raises :class:`ValueError`.
    """

    def __init__(self) -> None:
        super().__init__(name="in_memory")
        self._schedules: dict[str, WorkflowSchedule] = {}

    def register(self, schedule: WorkflowSchedule) -> None:
        """Add ``schedule`` to the scheduler.

        Raises:
            ValueError: If a schedule with the same id is already registered.
        """
        if schedule.id in self._schedules:
            raise ValueError(f"Schedule already registered: {schedule.id!r}")
        normalized = self._normalize(schedule)
        self._schedules[schedule.id] = normalized
        self.logger.info(
            "Registered schedule %s (kind=%s, next=%s)",
            schedule.id,
            schedule.kind.value,
            normalized.next_run_at.isoformat() if normalized.next_run_at else "none",
        )

    def unregister(self, schedule_id: str) -> bool:
        """Remove a schedule by id. Return ``True`` if it existed."""
        existed = self._schedules.pop(schedule_id, None) is not None
        if existed:
            self.logger.info("Unregistered schedule: %s", schedule_id)
        return existed

    def get(self, schedule_id: str) -> WorkflowSchedule | None:
        """Look up a schedule by id, returning ``None`` if not found."""
        return self._schedules.get(schedule_id)

    def contains(self, schedule_id: str) -> bool:
        """Return ``True`` if a schedule with ``schedule_id`` is registered."""
        return schedule_id in self._schedules

    def all(self) -> list[WorkflowSchedule]:
        """Return every registered schedule, ordered by id."""
        return [self._schedules[sid] for sid in sorted(self._schedules)]

    def names(self) -> list[str]:
        """Return a sorted list of all registered schedule ids."""
        return sorted(self._schedules)

    def due(self, now: datetime | None = None) -> list[WorkflowSchedule]:
        """Return schedules that should fire at or before ``now``.

        A schedule is due if all of the following hold:

        * ``enabled`` is ``True``;
        * ``next_run_at`` is set and not in the future relative to ``now``.
        """
        moment = now or datetime.now(UTC)
        return [
            schedule
            for schedule in self.all()
            if schedule.enabled
            and schedule.next_run_at is not None
            and schedule.next_run_at <= moment
        ]

    def mark_run(self, schedule_id: str, ran_at: datetime) -> WorkflowSchedule | None:
        """Record a firing and advance the schedule's state.

        See module docstring for the per-kind advancement rules.
        """
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return None

        updated: WorkflowSchedule
        if schedule.kind is ScheduleKind.ONE_TIME:
            updated = schedule.__class__(
                **{
                    **schedule.__dict__,
                    "last_run_at": ran_at,
                    "next_run_at": None,
                    "enabled": False,
                }
            )
        elif schedule.kind is ScheduleKind.INTERVAL:
            interval = schedule.interval_seconds or 0
            next_at = ran_at + timedelta(seconds=interval)
            updated = schedule.__class__(
                **{
                    **schedule.__dict__,
                    "last_run_at": ran_at,
                    "next_run_at": next_at,
                }
            )
        elif schedule.kind is ScheduleKind.CRON:
            # Placeholder advancement: 24 hours forward.
            next_at = ran_at + timedelta(hours=24)
            updated = schedule.__class__(
                **{
                    **schedule.__dict__,
                    "last_run_at": ran_at,
                    "next_run_at": next_at,
                }
            )
        else:  # pragma: no cover — defensive
            return schedule

        self._schedules[schedule_id] = updated
        self.logger.debug(
            "Advanced schedule %s: next_run_at=%s",
            schedule_id,
            updated.next_run_at.isoformat() if updated.next_run_at else "none",
        )
        return updated

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(schedule: WorkflowSchedule) -> WorkflowSchedule:
        """Fill in a sensible ``next_run_at`` if none was supplied."""
        if schedule.next_run_at is not None:
            return schedule
        now = datetime.now(UTC)
        if schedule.kind is ScheduleKind.ONE_TIME:
            if schedule.run_at is None:
                return schedule
            return schedule.__class__(
                **{**schedule.__dict__, "next_run_at": schedule.run_at}
            )
        if schedule.kind is ScheduleKind.INTERVAL:
            return schedule.__class__(**{**schedule.__dict__, "next_run_at": now})
        return schedule

    def __len__(self) -> int:
        return len(self._schedules)

    def __repr__(self) -> str:
        return f"<InMemoryScheduler count={len(self)}>"


__all__ = ["InMemoryScheduler"]
