"""Communication history across channels."""

from __future__ import annotations

from atlas.business.models import (
    Channel,
    Communication,
    CommunicationDirection,
    _new_id,
)


class CommunicationManager:
    def __init__(self) -> None:
        self._comms: dict[str, Communication] = {}

    def log(
        self,
        customer_id: str = "",
        channel: str = Channel.EMAIL.value,
        direction: str = CommunicationDirection.OUTBOUND.value,
        subject: str = "",
        body: str = "",
    ) -> Communication:
        c = Communication(
            id=_new_id("comm"),
            customer_id=customer_id,
            channel=channel,
            direction=direction,
            subject=subject,
            body=body,
        )
        self._comms[c.id] = c
        return c

    def get(self, cid: str) -> Communication | None:
        return self._comms.get(cid)

    def list(
        self,
        customer_id: str | None = None,
        channel: str | None = None,
        direction: str | None = None,
    ) -> list[Communication]:
        cs = list(self._comms.values())
        if customer_id is not None:
            cs = [c for c in cs if c.customer_id == customer_id]
        if channel is not None:
            cs = [c for c in cs if c.channel == channel]
        if direction is not None:
            cs = [c for c in cs if c.direction == direction]
        return sorted(cs, key=lambda c: c.timestamp, reverse=True)

    def search(self, query: str) -> list[Communication]:
        q = query.lower()
        return [
            c
            for c in self._comms.values()
            if q in c.subject.lower() or q in c.body.lower()
        ]

    def count(self) -> int:
        return len(self._comms)

    def count_by_channel(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self._comms.values():
            counts[c.channel] = counts.get(c.channel, 0) + 1
        return counts

    def for_customer(self, customer_id: str) -> list[Communication]:
        return self.list(customer_id=customer_id)


__all__ = ["CommunicationManager"]
