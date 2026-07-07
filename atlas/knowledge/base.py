"""Abstract knowledge store for the Atlas Knowledge Engine.

A :class:`KnowledgeStore` is the in-process abstraction that the engine and
retriever interact with. It coordinates documents, their chunks, and an
optional :class:`KnowledgeStorage` backend. Concrete stores (e.g. an
in-memory implementation) subclass this contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from atlas.core.logger import get_logger
from atlas.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeResult,
)
from atlas.knowledge.storage import KnowledgeStorage


class KnowledgeStore(ABC):
    """Abstract foundation for every Atlas knowledge store.

    Parameters:
        name: Unique identifier for this store.
        storage: Optional persistence backend.
    """

    def __init__(
        self,
        name: str,
        storage: KnowledgeStorage | None = None,
    ) -> None:
        self.name = name
        self.storage = storage
        self.logger = get_logger(f"knowledge.store.{name}")

    @abstractmethod
    def add_document(
        self, document: KnowledgeDocument, chunks: list[KnowledgeChunk]
    ) -> None:
        """Add a document and its pre-computed chunks to the store."""

    @abstractmethod
    def remove_document(self, document_id: str) -> bool:
        """Remove a document and all its chunks by id."""

    @abstractmethod
    def search(
        self, query: KnowledgeQuery, embeddings: list[float] | None = None
    ) -> list[KnowledgeResult]:
        """Search the store and return ranked results."""

    @abstractmethod
    def list_documents(self) -> list[KnowledgeDocument]:
        """Return all documents in the store."""

    def __repr__(self) -> str:
        backend = "persistent" if self.storage else "in-memory"
        return f"<{self.__class__.__name__} name={self.name!r} ({backend})>"
