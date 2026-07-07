"""Memory engine — the orchestrator of all Atlas memory stores.

The :class:`MemoryEngine` is the single entry point through which the Kernel
and the rest of the system interact with memory. It owns the five memory
stores (working, episodic, semantic, procedural, reflection) and an
optional persistence backend, and it delegates operations to the appropriate
store based on the request.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.memory.base import BaseMemory
from atlas.memory.episodic import EpisodicMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryQuery
from atlas.memory.procedural import ProceduralMemory
from atlas.memory.reflection import ReflectionMemory
from atlas.memory.semantic import SemanticMemory
from atlas.memory.storage import MemoryStorage
from atlas.memory.working import WorkingMemory


class MemoryEngine:
    """Orchestrates all Atlas memory stores under a single interface.

    The engine provides a high-level API (``remember``, ``recall``,
    ``forget``) and also exposes each individual store for direct access
    when the caller knows which store it needs.

    Parameters:
        storage: Optional persistence backend shared by all stores.
            When ``None`` all stores operate purely in-memory.
    """

    def __init__(self, storage: MemoryStorage | None = None) -> None:
        self.storage = storage
        self.logger = get_logger("memory.engine")

        self.working = WorkingMemory(storage=storage)
        self.episodic = EpisodicMemory(storage=storage)
        self.semantic = SemanticMemory(storage=storage)
        self.procedural = ProceduralMemory(storage=storage)
        self.reflection = ReflectionMemory(storage=storage)

        self._stores: dict[MemoryCategory, BaseMemory] = {
            MemoryCategory.WORKING: self.working,
            MemoryCategory.EPISODIC: self.episodic,
            MemoryCategory.SEMANTIC: self.semantic,
            MemoryCategory.PROCEDURAL: self.procedural,
            MemoryCategory.REFLECTION: self.reflection,
        }

    def remember(
        self,
        content: Any,
        category: MemoryCategory = MemoryCategory.WORKING,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Store content in the specified memory category.

        This is the primary write API for the memory engine. It delegates
        to the appropriate store based on ``category``.
        """
        store = self._stores[category]
        self.logger.info("Remembering in %s: %s...", category.value, str(content)[:50])
        return store.store(content=content, source=source, tags=tags, **metadata)

    def recall(
        self,
        query: MemoryQuery | None = None,
        **kwargs: Any,
    ) -> list[MemoryEntry]:
        """Search across memory stores and return matching entries.

        If ``query`` specifies a ``category``, only that store is searched.
        Otherwise the engine queries all stores and merges the results,
        ordered by timestamp (newest first).
        """
        q = query or MemoryQuery(**kwargs)
        if q.category is not None:
            return self._stores[q.category].query(q)

        self.logger.debug("Recalling across all stores: %s", q.text or "*")
        all_results: list[MemoryEntry] = []
        for store in self._stores.values():
            all_results.extend(store.query(q))
        all_results.sort(key=lambda e: e.timestamp, reverse=True)
        return all_results[: q.limit]

    def forget(self, entry_id: str, category: MemoryCategory | None = None) -> bool:
        """Remove an entry from memory.

        If ``category`` is provided only that store is searched. Otherwise
        all stores are checked.
        """
        if category is not None:
            return self._stores[category].delete(entry_id)

        for store in self._stores.values():
            if store.delete(entry_id):
                self.logger.info("Forgot entry: %s", entry_id)
                return True
        return False

    def store_for(self, category: MemoryCategory) -> BaseMemory:
        """Return the memory store for a given category."""
        return self._stores[category]
