"""Customer management."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import (
    Customer,
    CustomerStatus,
    LeadSource,
    _new_id,
    _utcnow,
)


class CustomerManager:
    def __init__(self) -> None:
        self._customers: dict[str, Customer] = {}

    def create(
        self,
        name: str,
        email: str = "",
        phone: str = "",
        company: str = "",
        status: str = CustomerStatus.LEAD.value,
        source: str = LeadSource.OTHER.value,
        tags: tuple[str, ...] = (),
        notes: str = "",
    ) -> Customer:
        c = Customer(
            id=_new_id("cust"),
            name=name,
            email=email,
            phone=phone,
            company=company,
            status=status,
            source=source,
            tags=tags,
            notes=notes,
        )
        self._customers[c.id] = c
        return c

    def get(self, cid: str) -> Customer | None:
        return self._customers.get(cid)

    def list(self, status: str | None = None, tag: str | None = None) -> list[Customer]:
        cs = list(self._customers.values())
        if status is not None:
            cs = [c for c in cs if c.status == status]
        if tag is not None:
            cs = [c for c in cs if tag in c.tags]
        return cs

    def update(self, cid: str, **changes: Any) -> Customer:
        c = self._require(cid)
        updated = dataclasses.replace(c, **changes, updated_at=_utcnow())
        self._customers[cid] = updated
        return updated

    def delete(self, cid: str) -> bool:
        return self._customers.pop(cid, None) is not None

    def add_tag(self, cid: str, tag: str) -> Customer:
        c = self._require(cid)
        if tag in c.tags:
            return c
        return self.update(cid, tags=(*c.tags, tag))

    def search(self, query: str) -> list[Customer]:
        q = query.lower()
        return [
            c
            for c in self._customers.values()
            if q in c.name.lower() or q in c.email.lower() or q in c.company.lower()
        ]

    def count(self) -> int:
        return len(self._customers)

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self._customers.values():
            counts[c.status] = counts.get(c.status, 0) + 1
        return counts

    def _require(self, cid: str) -> Customer:
        c = self._customers.get(cid)
        if c is None:
            raise KeyError(f"customer {cid} not found")
        return c


__all__ = ["CustomerManager"]
