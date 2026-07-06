"""Conflict engine — detection and resolution.

The :class:`ConflictEngine` records :class:`Conflict` instances and
provides resolution methods (mediation, voting, escalation,
auto-resolution, splitting, deferral).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    Conflict,
    ConflictKind,
    ConflictResolution,
    _new_id,
    _utcnow,
)


class ConflictError(RuntimeError):
    """Raised when a conflict operation fails."""


class ConflictEngine:
    """Manages conflicts between agents."""

    def __init__(self) -> None:
        self._conflicts: dict[str, Conflict] = {}

    def report(
        self,
        session_id: str,
        kind: str = ConflictKind.DISAGREEMENT.value,
        agent_ids: tuple[str, ...] = (),
        description: str = "",
    ) -> Conflict:
        """Report a new conflict."""
        conflict = Conflict(
            id=_new_id("conflict"),
            session_id=session_id,
            kind=kind,
            agent_ids=agent_ids,
            description=description,
        )
        self._conflicts[conflict.id] = conflict
        return conflict

    def resolve(
        self,
        conflict_id: str,
        resolution: str = ConflictResolution.MEDIATED.value,
        notes: str = "",
    ) -> Conflict:
        """Resolve a conflict."""
        c = self._require(conflict_id)
        return self._update(
            conflict_id,
            status="resolved",
            resolution=resolution,
            resolved_at=_utcnow(),
            resolution_notes=notes,
        )

    def get(self, conflict_id: str) -> Conflict | None:
        """Return the conflict with ``conflict_id`` or ``None``."""
        return self._conflicts.get(conflict_id)

    def list_conflicts(
        self,
        session_id: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ) -> list[Conflict]:
        """List conflicts with optional filters."""
        conflicts = list(self._conflicts.values())
        if session_id is not None:
            conflicts = [c for c in conflicts if c.session_id == session_id]
        if status is not None:
            conflicts = [c for c in conflicts if c.status == status]
        if kind is not None:
            conflicts = [c for c in conflicts if c.kind == kind]
        return conflicts

    def open_conflicts(self) -> list[Conflict]:
        """Return all unresolved conflicts."""
        return self.list_conflicts(status="open")

    def resolved_conflicts(self) -> list[Conflict]:
        """Return all resolved conflicts."""
        return self.list_conflicts(status="resolved")

    def conflicts_involving(self, agent_id: str) -> list[Conflict]:
        """Return all conflicts involving ``agent_id``."""
        return [c for c in self._conflicts.values() if agent_id in c.agent_ids]

    def count(self) -> int:
        """Return the total number of conflicts."""
        return len(self._conflicts)

    def open_count(self) -> int:
        """Return the number of open conflicts."""
        return len(self.open_conflicts())

    def count_by_kind(self) -> dict[str, int]:
        """Return a dict of conflict counts by kind."""
        counts: dict[str, int] = {}
        for c in self._conflicts.values():
            counts[c.kind] = counts.get(c.kind, 0) + 1
        return counts

    def count_by_resolution(self) -> dict[str, int]:
        """Return a dict of resolved-conflict counts by resolution."""
        counts: dict[str, int] = {}
        for c in self._conflicts.values():
            if c.resolution:
                counts[c.resolution] = counts.get(c.resolution, 0) + 1
        return counts

    def _require(self, conflict_id: str) -> Conflict:
        c = self._conflicts.get(conflict_id)
        if c is None:
            raise ConflictError(f"conflict {conflict_id} not found")
        return c

    def _update(self, conflict_id: str, **changes: Any) -> Conflict:
        c = self._conflicts[conflict_id]
        updated = dataclasses.replace(c, **changes)
        self._conflicts[conflict_id] = updated
        return updated


__all__ = ["ConflictEngine", "ConflictError"]
