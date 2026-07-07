"""CRM — interactions and customer lifecycle tracking."""

from __future__ import annotations

from atlas.business.customers import CustomerManager
from atlas.business.models import (
    CustomerStatus,
    Interaction,
    _new_id,
)


class CRMManager:
    def __init__(self, customers: CustomerManager | None = None) -> None:
        self.customers = customers or CustomerManager()
        self._interactions: dict[str, Interaction] = {}

    def log_interaction(
        self,
        customer_id: str,
        channel: str = "email",
        direction: str = "outbound",
        subject: str = "",
        body: str = "",
    ) -> Interaction:
        i = Interaction(
            id=_new_id("inter"),
            customer_id=customer_id,
            channel=channel,
            direction=direction,
            subject=subject,
            body=body,
        )
        self._interactions[i.id] = i
        return i

    def get_interaction(self, iid: str) -> Interaction | None:
        return self._interactions.get(iid)

    def interactions_for(self, customer_id: str) -> list[Interaction]:
        return sorted(
            [i for i in self._interactions.values() if i.customer_id == customer_id],
            key=lambda i: i.timestamp,
        )

    def advance_stage(self, customer_id: str) -> str | None:
        c = self.customers.get(customer_id)
        if c is None:
            return None
        stages = [
            CustomerStatus.LEAD.value,
            CustomerStatus.PROSPECT.value,
            CustomerStatus.ACTIVE.value,
        ]
        try:
            idx = stages.index(c.status)
        except ValueError:
            return c.status
        if idx < len(stages) - 1:
            self.customers.update(customer_id, status=stages[idx + 1])
            return stages[idx + 1]
        return c.status

    def churn(self, customer_id: str) -> str | None:
        self.customers.update(customer_id, status=CustomerStatus.CHURNED.value)
        return CustomerStatus.CHURNED.value

    def interaction_count(self, customer_id: str | None = None) -> int:
        if customer_id is None:
            return len(self._interactions)
        return len(self.interactions_for(customer_id))

    def count_by_channel(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for i in self._interactions.values():
            counts[i.channel] = counts.get(i.channel, 0) + 1
        return counts


__all__ = ["CRMManager"]
