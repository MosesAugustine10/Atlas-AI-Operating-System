"""Delegation engine — task delegation between agents.

The :class:`DelegationEngine` records and tracks delegations from one
agent to another. Delegations can be accepted, rejected, completed,
or failed.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    Delegation,
    DelegationStatus,
    _new_id,
    _utcnow,
)


class DelegationError(RuntimeError):
    """Raised when a delegation operation fails."""


class DelegationEngine:
    """Manages inter-agent delegations."""

    def __init__(self) -> None:
        self._delegations: dict[str, Delegation] = {}

    def delegate(
        self,
        session_id: str,
        from_agent_id: str,
        to_agent_id: str,
        task_description: str = "",
        reason: str = "",
    ) -> Delegation:
        """Create a new delegation."""
        if from_agent_id == to_agent_id:
            raise DelegationError("cannot delegate to self")
        delegation = Delegation(
            id=_new_id("delegation"),
            session_id=session_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task_description=task_description,
            reason=reason,
        )
        self._delegations[delegation.id] = delegation
        return delegation

    def accept(self, delegation_id: str) -> Delegation:
        """Accept a delegation."""
        d = self._require(delegation_id)
        return self._update(
            delegation_id,
            status=DelegationStatus.ACCEPTED.value,
            decided_at=_utcnow(),
        )

    def reject(self, delegation_id: str) -> Delegation:
        """Reject a delegation."""
        d = self._require(delegation_id)
        return self._update(
            delegation_id,
            status=DelegationStatus.REJECTED.value,
            decided_at=_utcnow(),
        )

    def complete(self, delegation_id: str, result: str = "") -> Delegation:
        """Mark a delegation as completed."""
        d = self._require(delegation_id)
        return self._update(
            delegation_id,
            status=DelegationStatus.COMPLETED.value,
            completed_at=_utcnow(),
            result=result,
        )

    def fail(self, delegation_id: str, error: str = "") -> Delegation:
        """Mark a delegation as failed."""
        d = self._require(delegation_id)
        return self._update(
            delegation_id,
            status=DelegationStatus.FAILED.value,
            completed_at=_utcnow(),
            result=error,
        )

    def cancel(self, delegation_id: str) -> Delegation:
        """Cancel a delegation."""
        d = self._require(delegation_id)
        return self._update(
            delegation_id,
            status=DelegationStatus.CANCELLED.value,
            decided_at=_utcnow(),
        )

    def get(self, delegation_id: str) -> Delegation | None:
        """Return the delegation with ``delegation_id`` or ``None``."""
        return self._delegations.get(delegation_id)

    def list_delegations(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[Delegation]:
        """List delegations with optional filters."""
        delegations = list(self._delegations.values())
        if session_id is not None:
            delegations = [d for d in delegations if d.session_id == session_id]
        if status is not None:
            delegations = [d for d in delegations if d.status == status]
        return delegations

    def by_delegator(self, agent_id: str) -> list[Delegation]:
        """Return delegations made by ``agent_id``."""
        return [d for d in self._delegations.values() if d.from_agent_id == agent_id]

    def by_delegatee(self, agent_id: str) -> list[Delegation]:
        """Return delegations received by ``agent_id``."""
        return [d for d in self._delegations.values() if d.to_agent_id == agent_id]

    def pending(self) -> list[Delegation]:
        """Return all pending delegations."""
        return self.list_delegations(status=DelegationStatus.PENDING.value)

    def accepted(self) -> list[Delegation]:
        """Return all accepted delegations."""
        return self.list_delegations(status=DelegationStatus.ACCEPTED.value)

    def completed(self) -> list[Delegation]:
        """Return all completed delegations."""
        return self.list_delegations(status=DelegationStatus.COMPLETED.value)

    def count(self) -> int:
        """Return the total number of delegations."""
        return len(self._delegations)

    def acceptance_rate(self) -> float:
        """Return the fraction of decided delegations that were accepted."""
        decided = [
            d
            for d in self._delegations.values()
            if d.status
            in (DelegationStatus.ACCEPTED.value, DelegationStatus.REJECTED.value)
        ]
        if not decided:
            return 0.0
        accepted = sum(
            1 for d in decided if d.status == DelegationStatus.ACCEPTED.value
        )
        return accepted / len(decided)

    def _require(self, delegation_id: str) -> Delegation:
        d = self._delegations.get(delegation_id)
        if d is None:
            raise DelegationError(f"delegation {delegation_id} not found")
        return d

    def _update(self, delegation_id: str, **changes: Any) -> Delegation:
        d = self._delegations[delegation_id]
        updated = dataclasses.replace(d, **changes)
        self._delegations[delegation_id] = updated
        return updated


__all__ = ["DelegationEngine", "DelegationError"]
