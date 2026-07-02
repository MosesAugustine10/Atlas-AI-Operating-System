"""Storage interface for the Atlas Memory Engine.

The :class:`MemoryStorage` abstract class defines the contract that any
persistence backend must implement. Concrete backends (SQLite, filesystem,
PostgreSQL, etc.) will subclass it. The memory engine interacts *only*
through this interface, so the storage layer is swappable without touching
any memory-type logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger
from atlas.memory.models import MemoryEntry, MemoryQuery


class MemoryStorage(ABC):
    """Abstract persistence backend for Atlas memory.

    Parameters:
        name: Human-readable identifier for this storage backend.
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.logger = get_logger(f"memory.storage.{name}")

    @abstractmethod
    def store(self, entry: MemoryEntry) -> MemoryEntry:
        """Persist ``entry`` and return it (potentially with a generated id)."""

    @abstractmethod
    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        """Fetch an entry by its unique id."""

    @abstractmethod
    def query(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Search and return matching entries."""

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Remove an entry by id. Return ``True`` if it existed."""

    @abstractmethod
    def update(self, entry_id: str, **fields: Any) -> MemoryEntry | None:
        """Apply partial updates to an entry and return the updated version."""

    @abstractmethod
    def count(self, category: str | None = None) -> int:
        """Return the total number of entries, optionally filtered by category."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
