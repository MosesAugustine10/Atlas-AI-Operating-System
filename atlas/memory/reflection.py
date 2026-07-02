"""Reflection memory — Atlas's self-assessment and meta-cognition layer.

Reflection memory holds *evaluations of past performance*, lessons learned,
and summaries generated from other memory stores. It is where Atlas
records what went well, what went wrong, and how to improve.
"""

from __future__ import annotations

from typing import Any

from atlas.memory.base import BaseMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryQuery


class ReflectionMemory(BaseMemory):
    """Store for self-assessments, lessons learned, and meta-cognition.

    Parameters:
        storage: Optional persistence backend.
    """

    def __init__(self, storage: Any = None) -> None:
        super().__init__(
            name="reflection", category=MemoryCategory.REFLECTION, storage=storage
        )
        self._entries: dict[str, MemoryEntry] = {}

    def store(
        self,
        content: Any,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Add a reflection entry."""
        entry = MemoryEntry(
            category=MemoryCategory.REFLECTION,
            content=content,
            source=source,
            tags=tags or [],
            metadata=metadata,
        )
        if self.storage:
            entry = self.storage.store(entry)
        self._entries[entry.id] = entry
        self.logger.debug("Stored reflection: %s", entry.id)
        return entry

    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)

    def query(
        self, query: MemoryQuery | None = None, **kwargs: Any
    ) -> list[MemoryEntry]:
        q = query or MemoryQuery(**kwargs)
        results = sorted(
            self._entries.values(), key=lambda e: e.timestamp, reverse=True
        )
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

    def lessons(
        self, tags: list[str] | None = None, count: int = 10
    ) -> list[MemoryEntry]:
        """Return the most recent reflections, optionally filtered by tags."""
        q = MemoryQuery(tags=tags or [], limit=count)
        return self.query(q)
