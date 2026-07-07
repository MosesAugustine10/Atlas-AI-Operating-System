"""Text chunker for the Atlas Knowledge Engine.

The :class:`TextChunker` splits a document into :class:`KnowledgeChunk`
objects of roughly equal size with a configurable overlap. Overlap ensures
that semantically related sentences are not severed at a chunk boundary,
which improves retrieval quality.
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.knowledge.models import KnowledgeChunk, KnowledgeDocument


class TextChunker:
    """Splits documents into overlapping chunks.

    Parameters:
        chunk_size: Target number of characters per chunk.
        overlap: Number of characters of overlap between consecutive chunks.
            Must be strictly less than ``chunk_size``.
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
            )
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = get_logger("knowledge.chunker")

    def chunk(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        """Split ``document`` into ordered chunks.

        Returns an empty list when the document has no content.
        """
        text = document.content.strip()
        if not text:
            return []

        step = self.chunk_size - self.overlap
        chunks: list[KnowledgeChunk] = []
        index = 0
        start = 0
        length = len(text)
        while start < length:
            end = min(start + self.chunk_size, length)
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    KnowledgeChunk(
                        document_id=document.id,
                        content=piece,
                        index=index,
                        tags=list(document.tags),
                        metadata={"source": document.source},
                    )
                )
                index += 1
            if end >= length:
                break
            start += step

        self.logger.debug(
            "Chunked document %s into %d chunks", document.id, len(chunks)
        )
        return chunks
