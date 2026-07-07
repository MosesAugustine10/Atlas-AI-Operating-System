"""Procedural memory — how Atlas does things.

Procedural memory stores *procedures, workflows, and methods* — the
knowledge of *how* to accomplish tasks. This is where reusable processes,
step sequences, and operational patterns live.
"""

from __future__ import annotations

from typing import Any

from atlas.memory.base import BaseMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryQuery


class ProceduralMemory(BaseMemory):
    """Long-term store for procedures and workflow knowledge.

    Parameters:
        storage: Optional persistence backend.
    """

    def __init__(self, storage: Any = None) -> None:
        super().__init__(
            name="procedural", category=MemoryCategory.PROCEDURAL, storage=storage
        )
        self._entries: dict[str, MemoryEntry] = {}

    def store(
        self,
        content: Any,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Add a procedure to procedural memory."""
        entry = MemoryEntry(
            category=MemoryCategory.PROCEDURAL,
            content=content,
            source=source,
            tags=tags or [],
            metadata=metadata,
        )
        if self.storage:
            entry = self.storage.store(entry)
        self._entries[entry.id] = entry
        self.logger.debug("Stored procedure: %s", entry.id)
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
