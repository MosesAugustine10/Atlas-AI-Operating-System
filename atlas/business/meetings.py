"""Meeting management."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import Meeting, MeetingStatus, _new_id, _utcnow


class MeetingManager:
    def __init__(self) -> None:
        self._meetings: dict[str, Meeting] = {}

    def create(
        self,
        title: str = "",
        customer_id: str = "",
        project_id: str = "",
        start: Any | None = None,
        end: Any | None = None,
        location: str = "",
        attendees: tuple[str, ...] = (),
        agenda: str = "",
    ) -> Meeting:
        now = _utcnow()
        m = Meeting(
            id=_new_id("mtg"),
            title=title,
            customer_id=customer_id,
            project_id=project_id,
            start=start or now,
            end=end or now,
            location=location,
            attendees=attendees,
            agenda=agenda,
        )
        self._meetings[m.id] = m
        return m

    def get(self, mid: str) -> Meeting | None:
        return self._meetings.get(mid)

    def list(
        self,
        customer_id: str | None = None,
        project_id: str | None = None,
        status: str | None = None,
    ) -> list[Meeting]:
        ms = list(self._meetings.values())
        if customer_id is not None:
            ms = [m for m in ms if m.customer_id == customer_id]
        if project_id is not None:
            ms = [m for m in ms if m.project_id == project_id]
        if status is not None:
            ms = [m for m in ms if m.status == status]
        return sorted(ms, key=lambda m: m.start)

    def start_meeting(self, mid: str) -> Meeting | None:
        m = self._meetings.get(mid)
        if m is None:
            return None
        updated = dataclasses.replace(m, status=MeetingStatus.IN_PROGRESS.value)
        self._meetings[mid] = updated
        return updated

    def complete(self, mid: str, notes: str = "") -> Meeting | None:
        m = self._meetings.get(mid)
        if m is None:
            return None
        updated = dataclasses.replace(
            m, status=MeetingStatus.COMPLETED.value, notes=notes
        )
        self._meetings[mid] = updated
        return updated

    def cancel(self, mid: str) -> Meeting | None:
        m = self._meetings.get(mid)
        if m is None:
            return None
        updated = dataclasses.replace(m, status=MeetingStatus.CANCELLED.value)
        self._meetings[mid] = updated
        return updated

    def add_notes(self, mid: str, notes: str) -> Meeting | None:
        m = self._meetings.get(mid)
        if m is None:
            return None
        updated = dataclasses.replace(m, notes=notes)
        self._meetings[mid] = updated
        return updated

    def upcoming(self, limit: int = 10) -> list[Meeting]:
        now = _utcnow()
        future = sorted(
            [
                m
                for m in self._meetings.values()
                if m.start >= now and m.status == MeetingStatus.SCHEDULED.value
            ],
            key=lambda m: m.start,
        )
        return future[:limit]

    def count(self) -> int:
        return len(self._meetings)

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self._meetings.values():
            counts[m.status] = counts.get(m.status, 0) + 1
        return counts


__all__ = ["MeetingManager"]
