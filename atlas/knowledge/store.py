"""Concrete in-memory knowledge store.

A working implementation of :class:`KnowledgeStore` that keeps documents
and chunks in process memory and consults an :class:`InMemoryVectorStore`
for similarity search. This is the default store used by the engine; it can
be swapped for a persistent backend without changing engine code.
"""

from __future__ import annotations

from atlas.knowledge.base import KnowledgeStore
from atlas.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeResult,
)
from atlas.knowledge.vectorstore import InMemoryVectorStore


class InMemoryKnowledgeStore(KnowledgeStore):
    """In-memory implementation of the knowledge store contract.

    Holds documents, their chunks, and a vector index over those chunks.
    The vector index is built lazily as chunks are added with embeddings.
    """

    def __init__(
        self,
        vector_store: InMemoryVectorStore | None = None,
    ) -> None:
        super().__init__(name="in-memory")
        self._documents: dict[str, KnowledgeDocument] = {}
        self._chunks_by_doc: dict[str, list[KnowledgeChunk]] = {}
        self._chunks_by_id: dict[str, KnowledgeChunk] = {}
        self._embeddings: dict[str, list[float]] = {}
        self.vectors = vector_store or InMemoryVectorStore()

    def add_document(
        self,
        document: KnowledgeDocument,
        chunks: list[KnowledgeChunk],
        embeddings: dict[str, list[float]] | None = None,
    ) -> None:
        """Add a document, its chunks, and optional pre-computed embeddings."""
        self._documents[document.id] = document
        self._chunks_by_doc[document.id] = list(chunks)
        emap = embeddings or {}
        for chunk in chunks:
            self._chunks_by_id[chunk.id] = chunk
            vec = emap.get(chunk.id)
            if vec is not None:
                self._embeddings[chunk.id] = vec
                self.vectors.index(chunk.id, document.id, vec)

    def remove_document(self, document_id: str) -> bool:
        if document_id not in self._documents:
            return False
        for chunk in self._chunks_by_doc.pop(document_id, []):
            self._chunks_by_id.pop(chunk.id, None)
            self._embeddings.pop(chunk.id, None)
        self.vectors.delete_document(document_id)
        del self._documents[document_id]
        return True

    def search(
        self,
        query: KnowledgeQuery,
        embeddings: list[float] | None = None,
    ) -> list[KnowledgeResult]:
        """Search by embedding similarity (requires a query embedding)."""
        if embeddings is None:
            return []
        hits = self.vectors.search(embeddings, top_k=max(query.top_k, 1))
        results: list[KnowledgeResult] = []
        for chunk_id, doc_id, score in hits:
            chunk = self._chunks_by_id.get(chunk_id)
            document = self._documents.get(doc_id)
            if chunk is None or document is None:
                continue
            results.append(KnowledgeResult(chunk=chunk, document=document, score=score))
        return results

    def list_documents(self) -> list[KnowledgeDocument]:
        return list(self._documents.values())

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self._documents.get(document_id)

    def chunks_of(self, document_id: str) -> list[KnowledgeChunk]:
        return list(self._chunks_by_doc.get(document_id, []))

    def count(self) -> int:
        return len(self._documents)
