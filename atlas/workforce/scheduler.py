"""Scheduler — shifts, availability, and load balancing.

The :class:`Scheduler` manages worker shifts and decides which worker
should pick up the next task. It respects worker availability (only
idle workers are eligible) and balances load by preferring the worker
with the fewest completed tasks (simple round-robin-like balancing).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Shift,
    ShiftStatus,
    WorkerState,
    WorkerStatus,
    _new_id,
    _utcnow,
)


class Scheduler:
    """Manages worker shifts and task assignment."""

    def __init__(self) -> None:
        self._shifts: dict[str, Shift] = {}
        self.logger = get_logger("workforce.scheduler")

    # ------------------------------------------------------------------
    # Shifts
    # ------------------------------------------------------------------

    def schedule_shift(
        self,
        worker_id: str,
        start: Any | None = None,
        end: Any | None = None,
    ) -> Shift:
        """Schedule a new shift for ``worker_id``."""
        start_dt = start or _utcnow()
        end_dt = end or start_dt
        shift = Shift(
            id=_new_id("shift"),
            worker_id=worker_id,
            start=start_dt,
            end=end_dt,
            status=ShiftStatus.SCHEDULED.value,
        )
        self._shifts[shift.id] = shift
        return shift

    def start_shift(self, shift_id: str) -> Shift:
        """Mark a shift as active."""
        shift = self._require(shift_id)
        updated = dataclasses.replace(shift, status=ShiftStatus.ACTIVE.value)
        self._shifts[shift_id] = updated
        return updated

    def complete_shift(self, shift_id: str, tasks_completed: int = 0) -> Shift:
        """Mark a shift as completed."""
        shift = self._require(shift_id)
        updated = dataclasses.replace(
            shift,
            status=ShiftStatus.COMPLETED.value,
            tasks_completed=tasks_completed,
        )
        self._shifts[shift_id] = updated
        return updated

    def cancel_shift(self, shift_id: str) -> Shift:
        """Cancel a shift."""
        shift = self._require(shift_id)
        updated = dataclasses.replace(shift, status=ShiftStatus.CANCELLED.value)
        self._shifts[shift_id] = updated
        return updated

    def get_shift(self, shift_id: str) -> Shift | None:
        """Return the shift with ``shift_id`` or ``None``."""
        return self._shifts.get(shift_id)

    def shifts_for(self, worker_id: str) -> list[Shift]:
        """Return all shifts for ``worker_id`` (chronological)."""
        shifts = [s for s in self._shifts.values() if s.worker_id == worker_id]
        shifts.sort(key=lambda s: s.start)
        return shifts

    def active_shifts(self) -> list[Shift]:
        """Return all currently-active shifts."""
        return [
            s for s in self._shifts.values() if s.status == ShiftStatus.ACTIVE.value
        ]

    def active_shift_for(self, worker_id: str) -> Shift | None:
        """Return the active shift for ``worker_id`` or ``None``."""
        for s in self._shifts.values():
            if s.worker_id == worker_id and s.status == ShiftStatus.ACTIVE.value:
                return s
        return None

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def pick_worker(
        self,
        candidates: list[WorkerState],
        required_role: str = "",
        required_skills: tuple[str, ...] = (),
    ) -> WorkerState | None:
        """Pick the best worker from ``candidates`` for the next task.

        Selection criteria:
        1. Worker must be IDLE.
        2. If ``required_role`` is given, worker's role must match.
        3. If ``required_skills`` is given, worker must have all of them
           at level ≥ 0.3.
        4. Among eligible workers, prefer the one with the fewest
           completed tasks (load balancing).
        """
        eligible: list[WorkerState] = []
        for worker in candidates:
            if worker.status != WorkerStatus.IDLE.value:
                continue
            if required_role and worker.role != required_role:
                continue
            if required_skills and not self._has_skills(worker, required_skills):
                continue
            eligible.append(worker)
        if not eligible:
            return None
        # Prefer fewest completed tasks (load balancing)
        eligible.sort(key=lambda w: (w.tasks_completed, w.last_active_at or _utcnow()))
        return eligible[0]

    def available_workers(
        self,
        workers: list[WorkerState],
    ) -> list[WorkerState]:
        """Return the subset of ``workers`` that are currently available."""
        return [w for w in workers if w.status == WorkerStatus.IDLE.value]

    def workload(
        self,
        workers: list[WorkerState],
    ) -> dict[str, int]:
        """Return a ``{worker_id: tasks_completed}`` dict for load display."""
        return {w.id: w.tasks_completed for w in workers}

    def balance_score(self, workers: list[WorkerState]) -> float:
        """Return a load-balance score (0.0 = perfect, 1.0 = worst).

        Computed as the standard deviation of completed-task counts
        across online workers, normalised to [0, 1].
        """
        online = [
            w.tasks_completed
            for w in workers
            if w.status in (WorkerStatus.IDLE.value, WorkerStatus.BUSY.value)
        ]
        if len(online) < 2:
            return 0.0
        mean = sum(online) / len(online)
        variance = sum((x - mean) ** 2 for x in online) / len(online)
        # Normalise: assume max meaningful variance is mean^2
        if mean == 0:
            return 0.0
        return min(1.0, (variance**0.5) / mean)

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def shift_count(self) -> int:
        """Return the total number of shifts."""
        return len(self._shifts)

    def count_by_status(self) -> dict[str, int]:
        """Return a dict of shift counts by status."""
        counts: dict[str, int] = {}
        for s in self._shifts.values():
            counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _has_skills(worker: WorkerState, required: tuple[str, ...]) -> bool:
        skill_names = {s.name for s in worker.skills}
        return all(r in skill_names for r in required)

    def _require(self, shift_id: str) -> Shift:
        shift = self._shifts.get(shift_id)
        if shift is None:
            raise KeyError(f"shift {shift_id} not found")
        return shift


__all__ = ["Scheduler"]
