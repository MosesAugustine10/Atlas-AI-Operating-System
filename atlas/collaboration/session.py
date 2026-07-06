"""Collaboration session — the top-level container for multi-agent work.

The :class:`SessionManager` owns :class:`CollaborationSession` instances
and manages their lifecycle: create, start, pause, resume, complete,
fail, cancel, archive. Agents join and leave sessions.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    CollaborationSession,
    SessionStatus,
    _new_id,
    _utcnow,
)


class SessionError(RuntimeError):
    """Raised when a session operation fails."""


class SessionManager:
    """Manages collaboration sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, CollaborationSession] = {}
        self._participants: dict[str, set[str]] = {}  # session_id -> agent_ids

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create(
        self,
        name: str = "",
        goal: str = "",
        coordinator_id: str = "",
        participant_ids: tuple[str, ...] = (),
    ) -> CollaborationSession:
        """Create a new collaboration session."""
        session = CollaborationSession(
            id=_new_id("session"),
            name=name,
            goal=goal,
            coordinator_id=coordinator_id,
            participant_ids=participant_ids,
        )
        self._sessions[session.id] = session
        self._participants[session.id] = set(participant_ids)
        if coordinator_id:
            self._participants[session.id].add(coordinator_id)
        return session

    def get(self, session_id: str) -> CollaborationSession | None:
        """Return the session with ``session_id`` or ``None``."""
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        status: str | None = None,
    ) -> list[CollaborationSession]:
        """List sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status is not None:
            sessions = [s for s in sessions if s.status == status]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def start(self, session_id: str) -> CollaborationSession:
        """Start a pending session."""
        session = self._require(session_id)
        if session.status != SessionStatus.PENDING.value:
            raise SessionError(
                f"session {session_id} is {session.status}, cannot start"
            )
        return self._update(
            session_id,
            status=SessionStatus.ACTIVE.value,
            started_at=_utcnow(),
        )

    def pause(self, session_id: str) -> CollaborationSession:
        """Pause an active session."""
        session = self._require(session_id)
        if session.status != SessionStatus.ACTIVE.value:
            raise SessionError(
                f"session {session_id} is {session.status}, cannot pause"
            )
        return self._update(session_id, status=SessionStatus.PAUSED.value)

    def resume(self, session_id: str) -> CollaborationSession:
        """Resume a paused session."""
        session = self._require(session_id)
        if session.status != SessionStatus.PAUSED.value:
            raise SessionError(
                f"session {session_id} is {session.status}, cannot resume"
            )
        return self._update(session_id, status=SessionStatus.ACTIVE.value)

    def complete(self, session_id: str) -> CollaborationSession:
        """Mark a session as completed."""
        session = self._require(session_id)
        return self._update(
            session_id,
            status=SessionStatus.COMPLETED.value,
            completed_at=_utcnow(),
        )

    def fail(self, session_id: str) -> CollaborationSession:
        """Mark a session as failed."""
        session = self._require(session_id)
        return self._update(
            session_id,
            status=SessionStatus.FAILED.value,
            completed_at=_utcnow(),
        )

    def cancel(self, session_id: str) -> CollaborationSession:
        """Cancel a session."""
        session = self._require(session_id)
        return self._update(
            session_id,
            status=SessionStatus.CANCELLED.value,
            completed_at=_utcnow(),
        )

    def archive(self, session_id: str) -> CollaborationSession:
        """Archive a completed session."""
        session = self._require(session_id)
        return self._update(session_id, status=SessionStatus.ARCHIVED.value)

    # ------------------------------------------------------------------
    # Participants
    # ------------------------------------------------------------------

    def join(self, session_id: str, agent_id: str) -> CollaborationSession:
        """Add ``agent_id`` to the session."""
        session = self._require(session_id)
        participants = self._participants.setdefault(session_id, set())
        if agent_id not in participants:
            participants.add(agent_id)
            return self._update(
                session_id,
                participant_ids=tuple(sorted(participants)),
            )
        return session

    def leave(self, session_id: str, agent_id: str) -> CollaborationSession:
        """Remove ``agent_id`` from the session."""
        session = self._require(session_id)
        participants = self._participants.setdefault(session_id, set())
        participants.discard(agent_id)
        return self._update(
            session_id,
            participant_ids=tuple(sorted(participants)),
        )

    def participants(self, session_id: str) -> set[str]:
        """Return the set of agent ids in ``session_id``."""
        return set(self._participants.get(session_id, set()))

    def is_participant(self, session_id: str, agent_id: str) -> bool:
        """Return ``True`` if ``agent_id`` is in ``session_id``."""
        return agent_id in self.participants(session_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def active_sessions(self) -> list[CollaborationSession]:
        """Return all active sessions."""
        return self.list_sessions(status=SessionStatus.ACTIVE.value)

    def completed_sessions(self) -> list[CollaborationSession]:
        """Return all completed sessions."""
        return self.list_sessions(status=SessionStatus.COMPLETED.value)

    def count(self) -> int:
        """Return the total number of sessions."""
        return len(self._sessions)

    def count_by_status(self) -> dict[str, int]:
        """Return a dict of session counts by status."""
        counts: dict[str, int] = {}
        for s in self._sessions.values():
            counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, session_id: str) -> CollaborationSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionError(f"session {session_id} not found")
        return session

    def _update(self, session_id: str, **changes: Any) -> CollaborationSession:
        session = self._sessions[session_id]
        updated = dataclasses.replace(session, **changes)
        self._sessions[session_id] = updated
        return updated


__all__ = ["SessionError", "SessionManager"]
