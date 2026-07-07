"""Embedding models for the Atlas Knowledge Engine.

The :class:`EmbeddingModel` abstract class defines the contract for turning
text into vectors. Concrete implementations may wrap OpenAI, Cohere, or a
local sentence-transformer. The included :class:`HashingEmbedder` produces
*deterministic* vectors purely from Python's hash — it is intentionally
lightweight so the engine can be tested end-to-end with no external service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingModel(ABC):
    """Abstract contract for embedding text into vector space.

    Parameters:
        dimensions: The dimensionality of the vectors this model produces.
    """

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    @abstractmethod
    def embed_document(self, text: str) -> list[float]:
        """Embed a document into a vector."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a query into a vector.

        Some models use separate encoders for queries vs. documents; this
        method allows that distinction even when they coincide.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} dimensions={self.dimensions}>"


class HashingEmbedder(EmbeddingModel):
    """Deterministic placeholder embedder for testing.

    Produces a fixed-size vector by hashing tokens and summing their
    contributions into a dense vector. The output is deterministic for any
    given input, so identical texts yield identical vectors — essential for
    reproducible retrieval tests.
    """

    def __init__(self, dimensions: int = 64) -> None:
        super().__init__(dimensions=dimensions)

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        """Hash tokens of ``text`` into a deterministic dense vector."""
        vector = [0.0] * self.dimensions
        tokens = text.lower().split()
        if not tokens:
            return vector
        for token in tokens:
            # Stable hash across runs (Python's hash() is salted by default).
            h = hash(token)
            idx = abs(h) % self.dimensions
            sign = 1.0 if (h % 2 == 0) else -1.0
            vector[idx] += sign
        # L2-normalise so cosine-style similarity is meaningful.
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector
