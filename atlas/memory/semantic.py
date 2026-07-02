"""Semantic memory — long-term knowledge and factual recall.

Semantic memory holds *what Atlas knows* — facts, concepts, domain
knowledge, and reference material that persists across sessions. In the
full implementation entries are backed by vector embeddings for semantic
search; for now the store supports tag-based and text-based queries.
"""

from __future__ import annotations

from typing import Any

from atlas.memory.base import BaseMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryQuery


class SemanticMemory(BaseMemory):
    """Long-term knowledge store for facts and domain concepts.

    Parameters:
        storage: Optional persistence backend.
    """

    def __init__(self, storage: Any = None) -> None:
        super().__init__(
            name="semantic", category=MemoryCategory.SEMANTIC, storage=storage
        )
        self._entries: dict[str, MemoryEntry] = {}

    def store(
        self,
        content: Any,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Add a knowledge entry to semantic memory."""
        entry = MemoryEntry(
            category=MemoryCategory.SEMANTIC,
            content=content,
            source=source,
            tags=tags or [],
            metadata=metadata,
        )
        if self.storage:
            entry = self.storage.store(entry)
        self._entries[entry.id] = entry
        self.logger.debug("Stored semantic entry: %s", entry.id)
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
