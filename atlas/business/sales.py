"""Sales pipeline and deal management."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import Deal, DealStage, _new_id, _utcnow


class SalesManager:
    def __init__(self) -> None:
        self._deals: dict[str, Deal] = {}

    def create(
        self,
        customer_id: str,
        title: str = "",
        value: float = 0.0,
        stage: str = DealStage.LEAD.value,
        probability: float = 0.0,
        expected_close: Any | None = None,
    ) -> Deal:
        d = Deal(
            id=_new_id("deal"),
            customer_id=customer_id,
            title=title,
            value=value,
            stage=stage,
            probability=probability,
            expected_close=expected_close,
        )
        self._deals[d.id] = d
        return d

    def get(self, did: str) -> Deal | None:
        return self._deals.get(did)

    def list(
        self, stage: str | None = None, customer_id: str | None = None
    ) -> list[Deal]:
        ds = list(self._deals.values())
        if stage is not None:
            ds = [d for d in ds if d.stage == stage]
        if customer_id is not None:
            ds = [d for d in ds if d.customer_id == customer_id]
        return ds

    def update(self, did: str, **changes: Any) -> Deal:
        d = self._require(did)
        updated = dataclasses.replace(d, **changes, updated_at=_utcnow())
        self._deals[did] = updated
        return updated

    def advance(self, did: str) -> Deal:
        d = self._require(did)
        stages = [
            DealStage.LEAD.value,
            DealStage.QUALIFIED.value,
            DealStage.PROPOSAL.value,
            DealStage.NEGOTIATION.value,
            DealStage.CLOSED_WON.value,
        ]
        try:
            idx = stages.index(d.stage)
        except ValueError:
            return d
        if idx < len(stages) - 1:
            return self.update(did, stage=stages[idx + 1])
        return d

    def lose(self, did: str) -> Deal:
        return self.update(did, stage=DealStage.CLOSED_LOST.value)

    def delete(self, did: str) -> bool:
        return self._deals.pop(did, None) is not None

    def pipeline_value(self) -> float:
        return sum(
            d.value
            for d in self._deals.values()
            if d.stage not in (DealStage.CLOSED_WON.value, DealStage.CLOSED_LOST.value)
        )

    def won_value(self) -> float:
        return sum(
            d.value
            for d in self._deals.values()
            if d.stage == DealStage.CLOSED_WON.value
        )

    def count(self) -> int:
        return len(self._deals)

    def count_by_stage(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self._deals.values():
            counts[d.stage] = counts.get(d.stage, 0) + 1
        return counts

    def win_rate(self) -> float:
        closed = [
            d
            for d in self._deals.values()
            if d.stage in (DealStage.CLOSED_WON.value, DealStage.CLOSED_LOST.value)
        ]
        if not closed:
            return 0.0
        won = sum(1 for d in closed if d.stage == DealStage.CLOSED_WON.value)
        return won / len(closed)

    def _require(self, did: str) -> Deal:
        d = self._deals.get(did)
        if d is None:
            raise KeyError(f"deal {did} not found")
        return d


__all__ = ["SalesManager"]
