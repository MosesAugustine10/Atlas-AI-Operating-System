"""Working memory — short-lived, task-scoped scratch space.

Working memory holds the immediate context for the *current* task. It is
fast to read and write, intentionally ephemeral (entries are not expected
to survive across sessions unless explicitly promoted), and bounded in
capacity to keep the active context window manageable.
"""

from __future__ import annotations

from typing import Any

from atlas.memory.base import BaseMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryPriority, MemoryQuery


class WorkingMemory(BaseMemory):
    """Short-lived, task-scoped memory store.

    Parameters:
        capacity: Maximum number of entries before eviction applies.
            When ``0`` the store is unbounded.
        storage: Optional persistence backend.
    """

    def __init__(
        self,
        capacity: int = 0,
        storage: Any = None,
    ) -> None:
        super().__init__(
            name="working", category=MemoryCategory.WORKING, storage=storage
        )
        self.capacity = capacity
        self._entries: dict[str, MemoryEntry] = {}

    def store(
        self,
        content: Any,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Add an entry. Evicts the oldest entry when at capacity."""
        entry = MemoryEntry(
            category=MemoryCategory.WORKING,
            content=content,
            source=source,
            tags=tags or [],
            priority=MemoryPriority.NORMAL,
            metadata=metadata,
        )
        if self.storage:
            entry = self.storage.store(entry)
        self._entries[entry.id] = entry
        self._evict_if_needed()
        self.logger.debug("Stored working entry: %s", entry.id)
        return entry

    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)

    def query(
        self, query: MemoryQuery | None = None, **kwargs: Any
    ) -> list[MemoryEntry]:
        q = query or MemoryQuery(**kwargs)
        results = list(self._entries.values())
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

    def clear(self) -> None:
        """Remove all entries from working memory."""
        self._entries.clear()

    def _evict_if_needed(self) -> None:
        """Evict the oldest entry when the capacity is exceeded."""
        if self.capacity <= 0 or len(self._entries) <= self.capacity:
            return
        oldest = min(self._entries.values(), key=lambda e: e.timestamp)
        self.delete(oldest.id)
        self.logger.debug("Evicted oldest working entry: %s", oldest.id)
