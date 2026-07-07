"""Delegation engine — autonomous task delegation between workers.

The :class:`DelegationEngine` records and resolves delegations. When
a worker cannot (or should not) perform a task, they delegate it to
another worker. The engine records the delegation, notifies the
receiving worker, and tracks whether the delegation was accepted.

Delegation respects the chain of command: workers can only delegate
*downward* (to workers of lower authority) or *sideways* (to workers
of equal authority). Upward delegation is treated as an escalation
and should go through the supervisor.
"""

from __future__ import annotations

import dataclasses

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Delegation,
    _new_id,
    _utcnow,
)
from atlas.workforce.roles import chain_of_command_rank


class DelegationError(RuntimeError):
    """Raised when a delegation is invalid."""


class DelegationEngine:
    """Records and resolves worker delegations."""

    def __init__(self) -> None:
        self._delegations: dict[str, Delegation] = {}
        self.logger = get_logger("workforce.delegation")

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def delegate(
        self,
        from_worker_id: str,
        to_worker_id: str,
        task_id: str,
        from_role: str = "",
        to_role: str = "",
        reason: str = "",
    ) -> Delegation:
        """Delegate ``task_id`` from one worker to another.

        Raises :class:`DelegationError` if the delegation violates the
        chain of command (upward delegation is not allowed — use
        :class:`~atlas.workforce.supervisor.Supervisor` for escalations).
        """
        if from_worker_id == to_worker_id:
            raise DelegationError("cannot delegate to self")
        if from_role and to_role:
            from_rank = chain_of_command_rank(from_role)
            to_rank = chain_of_command_rank(to_role)
            if to_rank < from_rank:
                raise DelegationError(
                    f"cannot delegate upward from {from_role} (rank {from_rank}) "
                    f"to {to_role} (rank {to_rank}) — use escalation instead"
                )
        delegation = Delegation(
            id=_new_id("delegation"),
            from_worker_id=from_worker_id,
            to_worker_id=to_worker_id,
            task_id=task_id,
            reason=reason,
        )
        self._delegations[delegation.id] = delegation
        self.logger.info(
            "Delegated task %s from %s to %s",
            task_id,
            from_worker_id,
            to_worker_id,
        )
        return delegation

    def accept(self, delegation_id: str) -> Delegation:
        """Mark a delegation as accepted by the receiving worker."""
        delegation = self._require(delegation_id)
        updated = dataclasses.replace(
            delegation,
            accepted=True,
            accepted_at=_utcnow(),
        )
        self._delegations[delegation_id] = updated
        return updated

    def reject(self, delegation_id: str) -> Delegation:
        """Mark a delegation as rejected (accepted stays False)."""
        delegation = self._require(delegation_id)
        updated = dataclasses.replace(delegation, accepted=False, accepted_at=_utcnow())
        self._delegations[delegation_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, delegation_id: str) -> Delegation | None:
        """Return the delegation with ``delegation_id`` or ``None``."""
        return self._delegations.get(delegation_id)

    def by_delegator(self, worker_id: str) -> list[Delegation]:
        """Return all delegations made by ``worker_id``."""
        return [d for d in self._delegations.values() if d.from_worker_id == worker_id]

    def by_delegatee(self, worker_id: str) -> list[Delegation]:
        """Return all delegations received by ``worker_id``."""
        return [d for d in self._delegations.values() if d.to_worker_id == worker_id]

    def for_task(self, task_id: str) -> list[Delegation]:
        """Return all delegations for ``task_id``."""
        return [d for d in self._delegations.values() if d.task_id == task_id]

    def pending(self) -> list[Delegation]:
        """Return all delegations that have not been accepted or rejected."""
        return [d for d in self._delegations.values() if d.accepted_at is None]

    def accepted(self) -> list[Delegation]:
        """Return all accepted delegations."""
        return [d for d in self._delegations.values() if d.accepted]

    def rejected(self) -> list[Delegation]:
        """Return all rejected delegations (accepted=False and decided)."""
        return [
            d
            for d in self._delegations.values()
            if d.accepted_at is not None and not d.accepted
        ]

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the total number of delegations."""
        return len(self._delegations)

    def count_for(self, worker_id: str) -> tuple[int, int]:
        """Return ``(delegations_made, delegations_received)`` for a worker."""
        made = sum(
            1 for d in self._delegations.values() if d.from_worker_id == worker_id
        )
        received = sum(
            1 for d in self._delegations.values() if d.to_worker_id == worker_id
        )
        return (made, received)

    def acceptance_rate(self) -> float:
        """Return the fraction of decided delegations that were accepted."""
        decided = [d for d in self._delegations.values() if d.accepted_at is not None]
        if not decided:
            return 0.0
        accepted = sum(1 for d in decided if d.accepted)
        return accepted / len(decided)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, delegation_id: str) -> Delegation:
        delegation = self._delegations.get(delegation_id)
        if delegation is None:
            raise DelegationError(f"delegation {delegation_id} not found")
        return delegation


__all__ = ["DelegationEngine", "DelegationError"]
