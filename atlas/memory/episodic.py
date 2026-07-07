"""Episodic memory — a chronological log of past experiences.

Episodic memory records *what happened* and *when*. It is the primary store
for conversation logs, daily entries, and event records. Entries are
append-first and ordered by timestamp, supporting chronological queries.
"""

from __future__ import annotations

from typing import Any

from atlas.memory.base import BaseMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryQuery


class EpisodicMemory(BaseMemory):
    """Chronological log of past experiences and events.

    Parameters:
        storage: Optional persistence backend.
    """

    def __init__(self, storage: Any = None) -> None:
        super().__init__(
            name="episodic", category=MemoryCategory.EPISODIC, storage=storage
        )
        self._entries: dict[str, MemoryEntry] = {}

    def store(
        self,
        content: Any,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Append a new episode to the log."""
        entry = MemoryEntry(
            category=MemoryCategory.EPISODIC,
            content=content,
            source=source,
            tags=tags or [],
            metadata=metadata,
        )
        if self.storage:
            entry = self.storage.store(entry)
        self._entries[entry.id] = entry
        self.logger.debug("Logged episode: %s", entry.id)
        return entry

    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)

    def query(
        self, query: MemoryQuery | None = None, **kwargs: Any
    ) -> list[MemoryEntry]:
        q = query or MemoryQuery(**kwargs)
        results = sorted(self._entries.values(), key=lambda e: e.timestamp)
        if q.since:
            results = [e for e in results if e.timestamp >= q.since]
        if q.until:
            results = [e for e in results if e.timestamp <= q.until]
        if q.tags:
            results = [e for e in results if all(t in e.tags for t in q.tags)]
        if q.text:
            results = [e for e in results if q.text.lower() in str(e.content).lower()]
        return results[: q.limit]

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            if self.storage:
                self.storage.delete(entry_id)
            return True
        return False

    def recent(self, count: int = 10) -> list[MemoryEntry]:
        """Return the most recent ``count`` episodes, newest first."""
        ordered = sorted(
            self._entries.values(), key=lambda e: e.timestamp, reverse=True
        )
        return ordered[:count]
