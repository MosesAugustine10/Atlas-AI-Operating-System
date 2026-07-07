"""Shared collaboration memory — distinct from the Atlas Memory Engine.

The :class:`SharedMemory` is a key-value store scoped to a
collaboration session. Agents write :class:`SharedMemoryEntry`
instances to share context, decisions, and intermediate results.
This is NOT a replacement for the Atlas Memory Engine — it is a
lightweight, session-scoped scratchpad for collaboration.
"""

from __future__ import annotations

from atlas.collaboration.models import (
    SharedMemoryEntry,
    _new_id,
)


class SharedMemory:
    """Session-scoped shared memory for collaboration."""

    def __init__(self) -> None:
        self._entries: dict[str, SharedMemoryEntry] = {}
        # session_id -> {key: entry_id}
        self._by_session: dict[str, dict[str, str]] = {}

    def write(
        self,
        session_id: str,
        key: str,
        value: str = "",
        author_id: str = "",
        tags: tuple[str, ...] = (),
    ) -> SharedMemoryEntry:
        """Write a value under ``key`` for ``session_id``.

        If the key already exists, it is overwritten.
        """
        # Remove existing entry with the same key
        existing = self._by_session.get(session_id, {}).get(key)
        if existing is not None:
            self._entries.pop(existing, None)
        entry = SharedMemoryEntry(
            id=_new_id("mem"),
            session_id=session_id,
            key=key,
            value=value,
            author_id=author_id,
            tags=tags,
        )
        self._entries[entry.id] = entry
        self._by_session.setdefault(session_id, {})[key] = entry.id
        return entry

    def read(self, session_id: str, key: str) -> str | None:
        """Return the value for ``key`` in ``session_id`` or ``None``."""
        entry_id = self._by_session.get(session_id, {}).get(key)
        if entry_id is None:
            return None
        entry = self._entries.get(entry_id)
        return entry.value if entry else None

    def get_entry(self, session_id: str, key: str) -> SharedMemoryEntry | None:
        """Return the full :class:`SharedMemoryEntry` for ``key`` or ``None``."""
        entry_id = self._by_session.get(session_id, {}).get(key)
        if entry_id is None:
            return None
        return self._entries.get(entry_id)

    def delete(self, session_id: str, key: str) -> bool:
        """Delete ``key`` from ``session_id``. Returns ``True`` if deleted."""
        entry_id = self._by_session.get(session_id, {}).pop(key, None)
        if entry_id is None:
            return False
        self._entries.pop(entry_id, None)
        return True

    def keys(self, session_id: str) -> list[str]:
        """Return all keys for ``session_id``."""
        return list(self._by_session.get(session_id, {}))

    def entries(self, session_id: str) -> list[SharedMemoryEntry]:
        """Return all entries for ``session_id``."""
        session_map = self._by_session.get(session_id, {})
        return [
            self._entries[eid] for eid in session_map.values() if eid in self._entries
        ]

    def search(
        self,
        session_id: str,
        query: str,
    ) -> list[SharedMemoryEntry]:
        """Return entries whose key or value contains ``query``."""
        q = query.lower()
        return [
            e
            for e in self.entries(session_id)
            if q in e.key.lower() or q in e.value.lower()
        ]

    def by_tag(
        self,
        session_id: str,
        tag: str,
    ) -> list[SharedMemoryEntry]:
        """Return entries with ``tag`` in ``session_id``."""
        return [e for e in self.entries(session_id) if tag in e.tags]

    def count(self, session_id: str | None = None) -> int:
        """Return the number of entries (optionally per session)."""
        if session_id is None:
            return len(self._entries)
        return len(self._by_session.get(session_id, {}))

    def clear(self, session_id: str) -> int:
        """Clear all entries for ``session_id``. Returns the count cleared."""
        session_map = self._by_session.pop(session_id, {})
        count = 0
        for entry_id in session_map.values():
            if self._entries.pop(entry_id, None) is not None:
                count += 1
        return count


__all__ = ["SharedMemory"]
