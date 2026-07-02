"""Knowledge engine — orchestrates the full ingestion & retrieval pipeline.

The :class:`KnowledgeEngine` is the single entry point through which the
Kernel interacts with knowledge. It owns the loader, parser, chunker,
embedding model, store, and retriever, and it wires them together for the
two core flows:

* **Ingestion**:  Load → Parse → Chunk → Embed → Index
* **Retrieval**:  Query → Embed → Vector Search → Top-K Results

All collaborators are dependency-injected, so any single stage can be
swapped (e.g. HashingEmbedder → OpenAI embedder) without touching the rest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas.core.logger import get_logger
from atlas.knowledge.chunker import TextChunker
from atlas.knowledge.embeddings import EmbeddingModel, HashingEmbedder
from atlas.knowledge.loader import DocumentLoader
from atlas.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeResult,
)
from atlas.knowledge.parser import DocumentParser
from atlas.knowledge.retriever import Retriever
from atlas.knowledge.store import InMemoryKnowledgeStore


class KnowledgeEngine:
    """Orchestrates ingestion and retrieval for Atlas knowledge.

    Parameters:
        loader: Document loader. Defaults to a new :class:`DocumentLoader`.
        parser: Document parser. Defaults to a new :class:`DocumentParser`.
        chunker: Text chunker. Defaults to ``chunk_size=500, overlap=50``.
        embedder: Embedding model. Defaults to :class:`HashingEmbedder`.
        store: Knowledge store. Defaults to :class:`InMemoryKnowledgeStore`.
    """

    def __init__(
        self,
        loader: DocumentLoader | None = None,
        parser: DocumentParser | None = None,
        chunker: TextChunker | None = None,
        embedder: EmbeddingModel | None = None,
        store: InMemoryKnowledgeStore | None = None,
    ) -> None:
        self.loader = loader or DocumentLoader()
        self.parser = parser or DocumentParser()
        self.chunker = chunker or TextChunker()
        self.embedder = embedder or HashingEmbedder()
        self.store = store or InMemoryKnowledgeStore()
        self.retriever = Retriever(store=self.store, embedder=self.embedder)
        self.logger = get_logger("knowledge.engine")

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_text(
        self,
        content: str,
        source: str,
        content_type: str = "text/plain",
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> KnowledgeDocument:
        """Ingest raw text through the full pipeline.

        Pipeline: build document → parse → chunk → embed → index.
        """
        document = self.loader.load_text(
            content=content,
            source=source,
            content_type=content_type,
            tags=tags,
            **metadata,
        )
        return self._ingest_document(document)

    def ingest_file(
        self,
        path: str | Path,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> KnowledgeDocument:
        """Ingest a file from disk through the full pipeline."""
        document = self.loader.load_file(path, tags=tags, **metadata)
        return self._ingest_document(document)

    def _ingest_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        """Run parse → chunk → embed → index for an already-loaded document."""
        self.logger.info("Ingesting document: %s", document.source)

        cleaned = self.parser.parse(document)
        # Rebuild the document with cleaned content (immutable dataclass).
        document = KnowledgeDocument(
            content=cleaned,
            source=document.source,
            content_type=document.content_type,
            id=document.id,
            tags=list(document.tags),
            metadata=dict(document.metadata),
            created_at=document.created_at,
        )

        chunks = self.chunker.chunk(document)
        embeddings = {
            chunk.id: self.embedder.embed_document(chunk.content) for chunk in chunks
        }
        self.store.add_document(document, chunks, embeddings=embeddings)
        self.logger.info("Indexed document %s with %d chunks", document.id, len(chunks))
        return document

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(
        self, text: str, top_k: int = 5, tags: list[str] | None = None
    ) -> list[KnowledgeResult]:
        """Semantic search over the indexed knowledge.

        Pipeline: build query → embed → vector search → top-k results.
        """
        query = KnowledgeQuery(text=text, top_k=top_k, tags=tags or [])
        return self.retriever.retrieve(query)

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def remove(self, document_id: str) -> bool:
        """Remove a document and all its chunks from the store."""
        return self.store.remove_document(document_id)

    def count(self) -> int:
        """Return the number of indexed documents."""
        return self.store.count()

    def list_documents(self) -> list[KnowledgeDocument]:
        """Return all indexed documents."""
        return self.store.list_documents()

    def chunks_of(self, document_id: str) -> list[KnowledgeChunk]:
        """Return the chunks of a document, by id."""
        return self.store.chunks_of(document_id)
