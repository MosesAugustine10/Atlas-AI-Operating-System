"""MCP session management.

An :class:`MCPSession` is a logical conversation with one or more
connectors. The :class:`SessionManager` owns the set of open sessions
and handles lifecycle (open, close, timeout, retry, reconnect).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.exceptions import MCPSessionError
from atlas.mcp.models import MCPResponse, MCPSession, MCPStatus


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class SessionManager:
    """Owns the set of open :class:`MCPSession` instances.

    Parameters:
        default_timeout_seconds: Default request timeout for new sessions.
        max_retries: Default maximum retry count for failed requests.
        retry_backoff_seconds: Base delay between retries (deterministic —
            no actual sleeping).
    """

    def __init__(
        self,
        default_timeout_seconds: float = 30.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._sessions: dict[str, MCPSession] = {}
        self.logger = get_logger("mcp.session")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(
        self,
        connector: str,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MCPSession:
        """Open a new session for ``connector``."""
        session = MCPSession(
            connector=connector,
            status=MCPStatus.CONNECTED,
            permissions=tuple(permissions or ()),
            metadata=dict(metadata or {}),
        )
        self._sessions[session.id] = session
        self.logger.info("Opened session %s for connector %s", session.id, connector)
        return session

    def close(self, session_id: str) -> MCPSession | None:
        """Close a session by id. Returns the closed session or ``None``."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        closed = dataclasses.replace(
            session,
            status=MCPStatus.DISCONNECTED,
            closed_at=_utcnow(),
        )
        self._sessions[session_id] = closed
        self.logger.info("Closed session %s", session_id)
        return closed

    def get(self, session_id: str) -> MCPSession:
        """Return the session for ``session_id``.

        Raises:
            MCPSessionError: If the session is not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise MCPSessionError(f"session not found: {session_id!r}")
        return session

    def get_optional(self, session_id: str) -> MCPSession | None:
        """Return the session for ``session_id`` or ``None``."""
        return self._sessions.get(session_id)

    def contains(self, session_id: str) -> bool:
        """Return ``True`` if ``session_id`` is a known session."""
        return session_id in self._sessions

    def list(self, include_closed: bool = False) -> list[MCPSession]:
        """Return every session, optionally including closed ones."""
        sessions = list(self._sessions.values())
        if not include_closed:
            sessions = [s for s in sessions if s.is_open()]
        return sorted(sessions, key=lambda s: s.created_at)

    def active_count(self) -> int:
        """Return the number of open sessions."""
        return sum(1 for s in self._sessions.values() if s.is_open())

    def total_count(self) -> int:
        """Return the total number of sessions (open + closed)."""
        return len(self._sessions)

    # ------------------------------------------------------------------
    # Request tracking
    # ------------------------------------------------------------------

    def record_request(self, session_id: str, response: MCPResponse) -> None:
        """Record that a request was sent on ``session_id``."""
        session = self.get(session_id)
        updated = dataclasses.replace(
            session,
            last_active_at=_utcnow(),
            request_count=session.request_count + 1,
            error_count=session.error_count + (0 if response.success else 1),
        )
        self._sessions[session_id] = updated

    def touch(self, session_id: str) -> MCPSession:
        """Update ``last_active_at`` for ``session_id``."""
        session = self.get(session_id)
        updated = dataclasses.replace(session, last_active_at=_utcnow())
        self._sessions[session_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Timeout & retry
    # ------------------------------------------------------------------

    def is_expired(self, session_id: str, timeout_seconds: float | None = None) -> bool:
        """Return ``True`` if ``session_id`` has been idle for too long."""
        session = self.get(session_id)
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.default_timeout_seconds
        )
        idle = (_utcnow() - session.last_active_at).total_seconds()
        return idle > timeout

    def expire_stale(self, timeout_seconds: float | None = None) -> list[str]:
        """Close every session that has been idle for too long.

        Returns the list of closed session ids.
        """
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.default_timeout_seconds
        )
        closed: list[str] = []
        for session_id, session in list(self._sessions.items()):
            if not session.is_open():
                continue
            if (_utcnow() - session.last_active_at).total_seconds() > timeout:
                self.close(session_id)
                closed.append(session_id)
        if closed:
            self.logger.info("Expired %d stale session(s)", len(closed))
        return closed

    def reconnect(self, session_id: str) -> MCPSession:
        """Mark a session as reconnected (status -> CONNECTED, closed_at -> None)."""
        session = self.get(session_id)
        updated = dataclasses.replace(
            session,
            status=MCPStatus.CONNECTED,
            last_active_at=_utcnow(),
            closed_at=None,
        )
        self._sessions[session_id] = updated
        self.logger.info("Reconnected session %s", session_id)
        return updated

    def clear(self) -> None:
        """Drop every session."""
        self._sessions.clear()

    def __len__(self) -> int:
        return len(self._sessions)

    def __contains__(self, session_id: object) -> bool:
        return isinstance(session_id, str) and session_id in self._sessions

    def __repr__(self) -> str:
        return (
            f"<SessionManager total={len(self._sessions)} "
            f"active={self.active_count()}>"
        )


__all__ = ["SessionManager"]
