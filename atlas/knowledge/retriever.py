"""Retriever for the Atlas Knowledge Engine.

The :class:`Retriever` is a thin pipeline that turns a
:class:`KnowledgeQuery` into ranked :class:`KnowledgeResult` objects. The
pipeline is: embed the query → search the vector store → join the matched
chunks back to their parent documents → apply tag and score filters.
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.knowledge.base import KnowledgeStore
from atlas.knowledge.embeddings import EmbeddingModel
from atlas.knowledge.models import KnowledgeQuery, KnowledgeResult


class Retriever:
    """Embeds queries and retrieves ranked results from a store.

    Parameters:
        store: The knowledge store to search.
        embedder: The embedding model used to vectorise queries.
    """

    def __init__(self, store: KnowledgeStore, embedder: EmbeddingModel) -> None:
        self.store = store
        self.embedder = embedder
        self.logger = get_logger("knowledge.retriever")

    def retrieve(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        """Run the retrieval pipeline and return ranked results.

        Steps:
            1. Embed the query text.
            2. Ask the store to search (the store consults its vector index).
            3. Filter by required tags and minimum score.
            4. Return up to ``query.top_k`` results.
        """
        self.logger.info("Retrieving for: %s", query.text)
        query_embedding = self.embedder.embed_query(query.text)
        results = self.store.search(query, embeddings=query_embedding)

        filtered: list[KnowledgeResult] = []
        for result in results:
            if query.tags and not all(tag in result.chunk.tags for tag in query.tags):
                continue
            if result.score < query.min_score:
                continue
            filtered.append(result)
            if len(filtered) >= query.top_k:
                break
        self.logger.debug("Returning %d results", len(filtered))
        return filtered
