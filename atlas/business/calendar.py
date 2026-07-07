"""Calendar and event management."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from atlas.business.models import CalendarEvent, _new_id, _utcnow


class CalendarManager:
    def __init__(self) -> None:
        self._events: dict[str, CalendarEvent] = {}

    def create(
        self,
        title: str,
        start: datetime | None = None,
        end: datetime | None = None,
        location: str = "",
        attendees: tuple[str, ...] = (),
        project_id: str = "",
        customer_id: str = "",
        description: str = "",
    ) -> CalendarEvent:
        now = _utcnow()
        e = CalendarEvent(
            id=_new_id("evt"),
            title=title,
            description=description,
            start=start or now,
            end=end or now,
            location=location,
            attendees=attendees,
            project_id=project_id,
            customer_id=customer_id,
        )
        self._events[e.id] = e
        return e

    def get(self, eid: str) -> CalendarEvent | None:
        return self._events.get(eid)

    def list(
        self, project_id: str | None = None, customer_id: str | None = None
    ) -> list[CalendarEvent]:
        es = list(self._events.values())
        if project_id is not None:
            es = [e for e in es if e.project_id == project_id]
        if customer_id is not None:
            es = [e for e in es if e.customer_id == customer_id]
        return sorted(es, key=lambda e: e.start)

    def upcoming(self, limit: int = 10) -> list[CalendarEvent]:
        now = _utcnow()
        future = sorted(
            [e for e in self._events.values() if e.start >= now], key=lambda e: e.start
        )
        return future[:limit]

    def in_range(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        return sorted(
            [e for e in self._events.values() if e.start >= start and e.start <= end],
            key=lambda e: e.start,
        )

    def update(self, eid: str, **changes: Any) -> CalendarEvent:
        e = self._require(eid)
        updated = dataclasses.replace(e, **changes)
        self._events[eid] = updated
        return updated

    def delete(self, eid: str) -> bool:
        return self._events.pop(eid, None) is not None

    def count(self) -> int:
        return len(self._events)

    def _require(self, eid: str) -> CalendarEvent:
        e = self._events.get(eid)
        if e is None:
            raise KeyError(f"event {eid} not found")
        return e


__all__ = ["CalendarManager"]
