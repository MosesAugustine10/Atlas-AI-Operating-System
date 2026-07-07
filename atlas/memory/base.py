"""Abstract base class for all Atlas memory stores.

A :class:`BaseMemory` is the in-process abstraction that the Memory Engine
and Kernel interact with. Each concrete memory type (working, episodic,
semantic, procedural, reflection) implements this contract. A BaseMemory
*optionally* holds a reference to a :class:`MemoryStorage` for persistence,
but can also operate purely in-memory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryQuery
from atlas.memory.storage import MemoryStorage


class BaseMemory(ABC):
    """Abstract foundation for every Atlas memory store.

    Parameters:
        name: Unique identifier for this memory store.
        category: The :class:`MemoryCategory` this store belongs to.
        storage: Optional persistence backend. When ``None`` the store
            operates purely in-memory.
    """

    def __init__(
        self,
        name: str,
        category: MemoryCategory,
        storage: MemoryStorage | None = None,
    ) -> None:
        self.name = name
        self.category = category
        self.storage = storage
        self.logger = get_logger(f"memory.{name}")

    @abstractmethod
    def store(
        self,
        content: Any,
        source: str | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> MemoryEntry:
        """Add a new entry to this memory store."""

    @abstractmethod
    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        """Fetch a single entry by id."""

    @abstractmethod
    def query(
        self, query: MemoryQuery | None = None, **kwargs: Any
    ) -> list[MemoryEntry]:
        """Search for entries matching the given criteria."""

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Remove an entry by id."""

    def __repr__(self) -> str:
        backend = "persistent" if self.storage else "in-memory"
        return f"<{self.__class__.__name__} name={self.name!r} ({backend})>"
