"""Abstract storage interface for the Atlas Knowledge Engine.

The :class:`KnowledgeStorage` defines the persistence contract any backend
must implement. The engine and store interact *only* through this interface,
so the persistence layer (SQLite, Chroma, Qdrant, etc.) is swappable without
touching retrieval logic. No implementation coupling here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger
from atlas.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeQuery


class KnowledgeStorage(ABC):
    """Abstract persistence backend for Atlas knowledge records.

    Parameters:
        name: Human-readable identifier for this storage backend.
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.logger = get_logger(f"knowledge.storage.{name}")

    @abstractmethod
    def store_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        """Persist a document record."""

    @abstractmethod
    def store_chunks(self, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        """Persist a batch of chunk records belonging to one document."""

    @abstractmethod
    def retrieve_document(self, document_id: str) -> KnowledgeDocument | None:
        """Fetch a document by id."""

    @abstractmethod
    def retrieve_chunks(self, document_id: str) -> list[KnowledgeChunk]:
        """Fetch all chunks belonging to a document."""

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Remove a document and all its chunks. Return ``True`` if it existed."""

    @abstractmethod
    def update(self, document_id: str, **fields: Any) -> KnowledgeDocument | None:
        """Apply partial updates to a document."""

    @abstractmethod
    def query(self, query: KnowledgeQuery) -> list[KnowledgeChunk]:
        """Return chunks matching the structured query."""

    @abstractmethod
    def count(self) -> int:
        """Return the total number of stored documents."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
