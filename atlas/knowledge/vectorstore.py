"""In-memory vector store for the Atlas Knowledge Engine.

The :class:`InMemoryVectorStore` holds chunk embeddings and performs
brute-force cosine similarity search. It is intentionally simple and
dependency-free so the engine works end-to-end for testing and small
datasets. The interface mirrors what a Chroma / FAISS / Qdrant backend
will eventually provide.
"""

from __future__ import annotations

from atlas.core.logger import get_logger


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equal-length vectors.

    Returns ``0.0`` when either vector has zero magnitude.
    """
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """Holds chunk embeddings and performs cosine-similarity search.

    The store is keyed by ``chunk_id`` and tracks each chunk's embedding
    alongside its parent ``document_id`` so results can be joined back to
    documents efficiently.
    """

    def __init__(self) -> None:
        self.logger = get_logger("knowledge.vectorstore")
        # chunk_id -> (document_id, embedding)
        self._vectors: dict[str, tuple[str, list[float]]] = {}

    def index(self, chunk_id: str, document_id: str, embedding: list[float]) -> None:
        """Add (or overwrite) the embedding for ``chunk_id``."""
        self._vectors[chunk_id] = (document_id, list(embedding))
        self.logger.debug("Indexed chunk: %s", chunk_id)

    def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[str, str, float]]:
        """Return the top-k ``(chunk_id, document_id, score)`` matches.

        Results are sorted by descending similarity score.
        """
        scored: list[tuple[str, str, float]] = []
        for chunk_id, (document_id, embedding) in self._vectors.items():
            score = _cosine_similarity(query_embedding, embedding)
            scored.append((chunk_id, document_id, score))
        scored.sort(key=lambda triple: triple[2], reverse=True)
        return scored[:top_k]

    def delete(self, chunk_id: str) -> bool:
        """Remove a chunk's embedding. Return ``True`` if it existed."""
        return self._vectors.pop(chunk_id, None) is not None

    def delete_document(self, document_id: str) -> int:
        """Remove all embeddings belonging to ``document_id``.

        Returns the number of removed vectors.
        """
        victims = [
            cid for cid, (doc_id, _) in self._vectors.items() if doc_id == document_id
        ]
        for cid in victims:
            del self._vectors[cid]
        if victims:
            self.logger.debug(
                "Removed %d vectors for document %s", len(victims), document_id
            )
        return len(victims)

    def count(self) -> int:
        """Return the number of indexed vectors."""
        return len(self._vectors)

    def has(self, chunk_id: str) -> bool:
        """Return ``True`` if ``chunk_id`` is indexed."""
        return chunk_id in self._vectors
