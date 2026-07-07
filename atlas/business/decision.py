"""Decision engine — records reasons for autonomous decisions."""

from __future__ import annotations

import dataclasses

from atlas.business.models import Decision, DecisionStatus, _new_id, _utcnow


class DecisionManager:
    def __init__(self) -> None:
        self._decisions: dict[str, Decision] = {}

    def propose(
        self,
        title: str,
        description: str = "",
        reasoning: str = "",
        alternatives: tuple[str, ...] = (),
        impact: str = "",
        decided_by: str = "",
    ) -> Decision:
        d = Decision(
            id=_new_id("dec"),
            title=title,
            description=description,
            reasoning=reasoning,
            alternatives=alternatives,
            impact=impact,
            decided_by=decided_by,
        )
        self._decisions[d.id] = d
        return d

    def get(self, did: str) -> Decision | None:
        return self._decisions.get(did)

    def list(self, status: str | None = None) -> list[Decision]:
        ds = list(self._decisions.values())
        if status is not None:
            ds = [d for d in ds if d.status == status]
        return sorted(ds, key=lambda d: d.created_at, reverse=True)

    def approve(self, did: str, decided_by: str = "") -> Decision | None:
        d = self._decisions.get(did)
        if d is None:
            return None
        updated = dataclasses.replace(
            d,
            status=DecisionStatus.APPROVED.value,
            decided_by=decided_by,
            decided_at=_utcnow(),
        )
        self._decisions[did] = updated
        return updated

    def reject(self, did: str, decided_by: str = "") -> Decision | None:
        d = self._decisions.get(did)
        if d is None:
            return None
        updated = dataclasses.replace(
            d,
            status=DecisionStatus.REJECTED.value,
            decided_by=decided_by,
            decided_at=_utcnow(),
        )
        self._decisions[did] = updated
        return updated

    def execute(self, did: str) -> Decision | None:
        d = self._decisions.get(did)
        if d is None:
            return None
        if d.status != DecisionStatus.APPROVED.value:
            return None
        updated = dataclasses.replace(d, status=DecisionStatus.EXECUTED.value)
        self._decisions[did] = updated
        return updated

    def revert(self, did: str) -> Decision | None:
        d = self._decisions.get(did)
        if d is None:
            return None
        updated = dataclasses.replace(d, status=DecisionStatus.REVERTED.value)
        self._decisions[did] = updated
        return updated

    def pending(self) -> list[Decision]:
        return self.list(status=DecisionStatus.PROPOSED.value)

    def count(self) -> int:
        return len(self._decisions)

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self._decisions.values():
            counts[d.status] = counts.get(d.status, 0) + 1
        return counts


__all__ = ["DecisionManager"]
