"""Handoff engine — work handoffs with context transfer.

The :class:`HandoffEngine` manages :class:`Handoff` instances. When
one agent hands work off to another, it transfers a
:class:`HandoffContext` (summary, artifacts, notes, state).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    Handoff,
    HandoffContext,
    HandoffStatus,
    _new_id,
    _utcnow,
)


class HandoffError(RuntimeError):
    """Raised when a handoff operation fails."""


class HandoffEngine:
    """Manages work handoffs between agents."""

    def __init__(self) -> None:
        self._handoffs: dict[str, Handoff] = {}

    def initiate(
        self,
        session_id: str,
        from_agent_id: str,
        to_agent_id: str,
        task_description: str = "",
        context: HandoffContext | None = None,
    ) -> Handoff:
        """Initiate a handoff."""
        if from_agent_id == to_agent_id:
            raise HandoffError("cannot hand off to self")
        handoff = Handoff(
            id=_new_id("handoff"),
            session_id=session_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task_description=task_description,
            context=context or HandoffContext(),
        )
        self._handoffs[handoff.id] = handoff
        return handoff

    def accept(self, handoff_id: str) -> Handoff:
        """Accept a handoff."""
        h = self._require(handoff_id)
        return self._update(
            handoff_id,
            status=HandoffStatus.ACCEPTED.value,
            decided_at=_utcnow(),
        )

    def reject(self, handoff_id: str) -> Handoff:
        """Reject a handoff."""
        h = self._require(handoff_id)
        return self._update(
            handoff_id,
            status=HandoffStatus.REJECTED.value,
            decided_at=_utcnow(),
        )

    def complete(self, handoff_id: str, result: str = "") -> Handoff:
        """Mark a handoff as completed."""
        h = self._require(handoff_id)
        return self._update(
            handoff_id,
            status=HandoffStatus.COMPLETED.value,
            completed_at=_utcnow(),
            result=result,
        )

    def fail(self, handoff_id: str, error: str = "") -> Handoff:
        """Mark a handoff as failed."""
        h = self._require(handoff_id)
        return self._update(
            handoff_id,
            status=HandoffStatus.FAILED.value,
            completed_at=_utcnow(),
            result=error,
        )

    def get(self, handoff_id: str) -> Handoff | None:
        """Return the handoff with ``handoff_id`` or ``None``."""
        return self._handoffs.get(handoff_id)

    def list_handoffs(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[Handoff]:
        """List handoffs with optional filters."""
        handoffs = list(self._handoffs.values())
        if session_id is not None:
            handoffs = [h for h in handoffs if h.session_id == session_id]
        if status is not None:
            handoffs = [h for h in handoffs if h.status == status]
        return handoffs

    def by_sender(self, agent_id: str) -> list[Handoff]:
        """Return handoffs initiated by ``agent_id``."""
        return [h for h in self._handoffs.values() if h.from_agent_id == agent_id]

    def by_receiver(self, agent_id: str) -> list[Handoff]:
        """Return handoffs received by ``agent_id``."""
        return [h for h in self._handoffs.values() if h.to_agent_id == agent_id]

    def pending(self) -> list[Handoff]:
        """Return all initiated-but-not-decided handoffs."""
        return self.list_handoffs(status=HandoffStatus.INITIATED.value)

    def accepted(self) -> list[Handoff]:
        """Return all accepted handoffs."""
        return self.list_handoffs(status=HandoffStatus.ACCEPTED.value)

    def completed(self) -> list[Handoff]:
        """Return all completed handoffs."""
        return self.list_handoffs(status=HandoffStatus.COMPLETED.value)

    def count(self) -> int:
        """Return the total number of handoffs."""
        return len(self._handoffs)

    def acceptance_rate(self) -> float:
        """Return the fraction of decided handoffs that were accepted."""
        decided = [
            h
            for h in self._handoffs.values()
            if h.status in (HandoffStatus.ACCEPTED.value, HandoffStatus.REJECTED.value)
        ]
        if not decided:
            return 0.0
        accepted = sum(1 for h in decided if h.status == HandoffStatus.ACCEPTED.value)
        return accepted / len(decided)

    def _require(self, handoff_id: str) -> Handoff:
        h = self._handoffs.get(handoff_id)
        if h is None:
            raise HandoffError(f"handoff {handoff_id} not found")
        return h

    def _update(self, handoff_id: str, **changes: Any) -> Handoff:
        h = self._handoffs[handoff_id]
        updated = dataclasses.replace(h, **changes)
        self._handoffs[handoff_id] = updated
        return updated


__all__ = ["HandoffEngine", "HandoffError"]
