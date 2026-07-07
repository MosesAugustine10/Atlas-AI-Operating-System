"""Marketing campaign management."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import Campaign, CampaignStatus, _new_id


class MarketingManager:
    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}

    def create(
        self,
        name: str,
        description: str = "",
        budget: float = 0.0,
        start_date: Any | None = None,
        end_date: Any | None = None,
    ) -> Campaign:
        c = Campaign(
            id=_new_id("camp"),
            name=name,
            description=description,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
        )
        self._campaigns[c.id] = c
        return c

    def get(self, cid: str) -> Campaign | None:
        return self._campaigns.get(cid)

    def list(self, status: str | None = None) -> list[Campaign]:
        cs = list(self._campaigns.values())
        if status is not None:
            cs = [c for c in cs if c.status == status]
        return cs

    def update(self, cid: str, **changes: Any) -> Campaign:
        c = self._require(cid)
        updated = dataclasses.replace(c, **changes)
        self._campaigns[cid] = updated
        return updated

    def activate(self, cid: str) -> Campaign:
        return self.update(cid, status=CampaignStatus.ACTIVE.value)

    def pause(self, cid: str) -> Campaign:
        return self.update(cid, status=CampaignStatus.PAUSED.value)

    def complete(self, cid: str) -> Campaign:
        return self.update(cid, status=CampaignStatus.COMPLETED.value)

    def add_spend(self, cid: str, amount: float) -> Campaign:
        c = self._require(cid)
        return self.update(cid, spent=c.spent + amount)

    def active_campaigns(self) -> list[Campaign]:
        return self.list(status=CampaignStatus.ACTIVE.value)

    def total_budget(self) -> float:
        return sum(c.budget for c in self._campaigns.values())

    def total_spent(self) -> float:
        return sum(c.spent for c in self._campaigns.values())

    def count(self) -> int:
        return len(self._campaigns)

    def _require(self, cid: str) -> Campaign:
        c = self._campaigns.get(cid)
        if c is None:
            raise KeyError(f"campaign {cid} not found")
        return c


__all__ = ["MarketingManager"]
