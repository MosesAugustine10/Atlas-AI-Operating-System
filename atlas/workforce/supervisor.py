"""Supervisor — oversight, escalation, conflict resolution, intervention.

The :class:`Supervisor` is the workforce's authority figure. Workers
escalate problems to the supervisor when they cannot resolve them
internally. The supervisor also detects and resolves conflicts
between workers, and can intervene to reassign tasks or pause work.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Conflict,
    ConflictKind,
    ConflictResolution,
    Escalation,
    EscalationLevel,
    Task,
    _new_id,
    _utcnow,
)


class Supervisor:
    """Oversees the workforce, handles escalations and conflicts."""

    def __init__(self, supervisor_id: str = "supervisor") -> None:
        self._supervisor_id = supervisor_id
        self._escalations: dict[str, Escalation] = {}
        self._conflicts: dict[str, Conflict] = {}
        self.logger = get_logger("workforce.supervisor")

    @property
    def id(self) -> str:
        """Return the supervisor's worker id."""
        return self._supervisor_id

    # ------------------------------------------------------------------
    # Escalations
    # ------------------------------------------------------------------

    def escalate(
        self,
        from_worker_id: str,
        message: str,
        task_id: str = "",
        level: str = EscalationLevel.LOW.value,
    ) -> Escalation:
        """Record an escalation from a worker."""
        escalation = Escalation(
            id=_new_id("escalation"),
            from_worker_id=from_worker_id,
            supervisor_id=self._supervisor_id,
            task_id=task_id,
            level=level,
            message=message,
        )
        self._escalations[escalation.id] = escalation
        self.logger.info(
            "Escalation %s from %s (level=%s): %s",
            escalation.id,
            from_worker_id,
            level,
            message[:60],
        )
        return escalation

    def get_escalation(self, escalation_id: str) -> Escalation | None:
        """Return the escalation with ``escalation_id`` or ``None``."""
        return self._escalations.get(escalation_id)

    def resolve_escalation(
        self,
        escalation_id: str,
        resolution: str = "",
    ) -> Escalation:
        """Mark an escalation as resolved."""
        escalation = self._require_escalation(escalation_id)
        updated = dataclasses.replace(
            escalation,
            resolved=True,
            resolved_at=_utcnow(),
            resolution=resolution,
        )
        self._escalations[escalation_id] = updated
        return updated

    def pending_escalations(self) -> list[Escalation]:
        """Return all unresolved escalations (highest level first)."""
        pending = [e for e in self._escalations.values() if not e.resolved]
        pending.sort(
            key=lambda e: (
                0 if e.level == EscalationLevel.CRITICAL.value else 1,
                e.timestamp,
            )
        )
        return pending

    def resolved_escalations(self) -> list[Escalation]:
        """Return all resolved escalations."""
        return [e for e in self._escalations.values() if e.resolved]

    def escalations_by_worker(self, worker_id: str) -> list[Escalation]:
        """Return all escalations from ``worker_id``."""
        return [e for e in self._escalations.values() if e.from_worker_id == worker_id]

    def escalations_by_level(self, level: str) -> list[Escalation]:
        """Return all escalations at ``level``."""
        return [e for e in self._escalations.values() if e.level == level]

    def escalation_count(self) -> int:
        """Return the total number of escalations."""
        return len(self._escalations)

    def pending_count(self) -> int:
        """Return the number of unresolved escalations."""
        return sum(1 for e in self._escalations.values() if not e.resolved)

    # ------------------------------------------------------------------
    # Conflicts
    # ------------------------------------------------------------------

    def report_conflict(
        self,
        kind: str = ConflictKind.RESOURCE.value,
        worker_ids: tuple[str, ...] = (),
        task_ids: tuple[str, ...] = (),
        description: str = "",
    ) -> Conflict:
        """Record a conflict between workers."""
        conflict = Conflict(
            id=_new_id("conflict"),
            kind=kind,
            worker_ids=worker_ids,
            task_ids=task_ids,
            description=description,
        )
        self._conflicts[conflict.id] = conflict
        self.logger.info(
            "Conflict %s reported: %s (workers=%s)",
            conflict.id,
            kind,
            worker_ids,
        )
        return conflict

    def get_conflict(self, conflict_id: str) -> Conflict | None:
        """Return the conflict with ``conflict_id`` or ``None``."""
        return self._conflicts.get(conflict_id)

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str = ConflictResolution.MEDIATED.value,
        notes: str = "",
    ) -> Conflict:
        """Resolve a conflict."""
        conflict = self._require_conflict(conflict_id)
        updated = dataclasses.replace(
            conflict,
            resolution=resolution,
            resolved=True,
            resolved_at=_utcnow(),
            resolution_notes=notes,
        )
        self._conflicts[conflict_id] = updated
        return updated

    def pending_conflicts(self) -> list[Conflict]:
        """Return all unresolved conflicts."""
        return [c for c in self._conflicts.values() if not c.resolved]

    def resolved_conflicts(self) -> list[Conflict]:
        """Return all resolved conflicts."""
        return [c for c in self._conflicts.values() if c.resolved]

    def conflicts_involving(self, worker_id: str) -> list[Conflict]:
        """Return all conflicts involving ``worker_id``."""
        return [c for c in self._conflicts.values() if worker_id in c.worker_ids]

    def conflict_count(self) -> int:
        """Return the total number of conflicts."""
        return len(self._conflicts)

    def count_by_kind(self) -> dict[str, int]:
        """Return a dict of conflict counts by kind."""
        counts: dict[str, int] = {}
        for c in self._conflicts.values():
            counts[c.kind] = counts.get(c.kind, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Intervention
    # ------------------------------------------------------------------

    def reassign_task(
        self,
        task: Task,
        new_assignee_id: str,
        reason: str = "",
    ) -> Task:
        """Intervene by reassigning ``task`` to ``new_assignee_id``."""

        return dataclasses.replace(
            task,
            assignee_id=new_assignee_id,
            metadata=task.metadata
            + (("reassigned_by", self._supervisor_id), ("reassign_reason", reason)),
        )

    def cancel_task(self, task: Task, reason: str = "") -> Task:
        """Intervene by cancelling ``task``."""
        import atlas.workforce.models as models

        return dataclasses.replace(
            task,
            status=models.TaskStatus.CANCELLED.value,
            completed_at=_utcnow(),
            metadata=task.metadata
            + (("cancelled_by", self._supervisor_id), ("cancel_reason", reason)),
        )

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return a summary of the supervisor's state."""
        return {
            "supervisor_id": self._supervisor_id,
            "pending_escalations": self.pending_count(),
            "total_escalations": self.escalation_count(),
            "pending_conflicts": len(self.pending_conflicts()),
            "total_conflicts": self.conflict_count(),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_escalation(self, escalation_id: str) -> Escalation:
        escalation = self._escalations.get(escalation_id)
        if escalation is None:
            raise KeyError(f"escalation {escalation_id} not found")
        return escalation

    def _require_conflict(self, conflict_id: str) -> Conflict:
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            raise KeyError(f"conflict {conflict_id} not found")
        return conflict


__all__ = ["Supervisor"]
