"""Team — a group of workers collaborating on a shared goal.

A :class:`Team` is a dynamic grouping of workers with a shared goal.
Teams have a lead (typically a Project Manager or CTO), a set of
members, and a lifecycle (created → active → disbanded). Temporary
teams are disbanded when their goal is achieved.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Team,
    WorkerKind,
    WorkerState,
    _new_id,
    _utcnow,
)


class TeamError(RuntimeError):
    """Raised when a team operation fails."""


class TeamManager:
    """Manages a single team's lifecycle and membership."""

    def __init__(self, team: Team) -> None:
        self._team = team
        self.logger = get_logger(f"workforce.team.{team.id}")

    @classmethod
    def create(
        cls,
        name: str,
        goal: str = "",
        lead_id: str = "",
        member_ids: tuple[str, ...] = (),
        kind: str = WorkerKind.PERMANENT.value,
    ) -> TeamManager:
        """Create a new team and return a :class:`TeamManager` for it."""
        team = Team(
            id=_new_id("team"),
            name=name,
            goal=goal,
            lead_id=lead_id,
            member_ids=member_ids,
            kind=kind,
        )
        return cls(team)

    @property
    def team(self) -> Team:
        """Return the current immutable :class:`Team`."""
        return self._team

    @property
    def id(self) -> str:
        """Return the team's id."""
        return self._team.id

    @property
    def name(self) -> str:
        """Return the team's name."""
        return self._team.name

    @property
    def goal(self) -> str:
        """Return the team's goal."""
        return self._team.goal

    @property
    def lead_id(self) -> str:
        """Return the team lead's worker id."""
        return self._team.lead_id

    @property
    def member_ids(self) -> tuple[str, ...]:
        """Return the tuple of member worker ids."""
        return self._team.member_ids

    @property
    def is_active(self) -> bool:
        """Return ``True`` if the team is still active (not disbanded)."""
        return self._team.disbanded_at is None

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def add_member(self, worker_id: str) -> Team:
        """Add ``worker_id`` to the team (idempotent)."""
        if worker_id in self._team.member_ids:
            return self._team
        new_members = (*self._team.member_ids, worker_id)
        return self._update(member_ids=new_members)

    def remove_member(self, worker_id: str) -> Team:
        """Remove ``worker_id`` from the team."""
        new_members = tuple(m for m in self._team.member_ids if m != worker_id)
        return self._update(member_ids=new_members)

    def has_member(self, worker_id: str) -> bool:
        """Return ``True`` if ``worker_id`` is a member of this team."""
        return worker_id in self._team.member_ids

    def member_count(self) -> int:
        """Return the number of members on the team."""
        return len(self._team.member_ids)

    def set_lead(self, worker_id: str) -> Team:
        """Set the team lead to ``worker_id``."""
        if worker_id not in self._team.member_ids:
            raise TeamError(f"{worker_id} is not a member of team {self._team.id}")
        return self._update(lead_id=worker_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def disband(self) -> Team:
        """Disband the team."""
        return self._update(disbanded_at=_utcnow())

    def reactivate(self) -> Team:
        """Reactivate a disbanded team."""
        return self._update(disbanded_at=None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def online_members(self, workers: list[WorkerState]) -> list[WorkerState]:
        """Return the subset of ``workers`` who are members and online."""
        member_set = set(self._team.member_ids)
        return [
            w for w in workers if w.id in member_set and w.status in ("idle", "busy")
        ]

    def available_members(self, workers: list[WorkerState]) -> list[WorkerState]:
        """Return the subset of members who are currently idle."""
        member_set = set(self._team.member_ids)
        return [w for w in workers if w.id in member_set and w.status == "idle"]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _update(self, **changes: Any) -> Team:
        self._team = dataclasses.replace(self._team, **changes)
        return self._team


__all__ = ["TeamError", "TeamManager"]
