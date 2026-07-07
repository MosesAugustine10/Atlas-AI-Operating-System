"""The Atlas Knowledge Engine.

A modular pipeline for ingesting, parsing, chunking, embedding, indexing,
and retrieving documents. Every stage is dependency-injected and the
persistence layer is swappable — the engine works end-to-end with an
in-memory store and a deterministic hashing embedder, and can be upgraded
to Chroma / FAISS / Qdrant and a real embedding model without changing
engine code.

The dependency graph is acyclic:

* ``models`` — pure dataclasses (leaf).
* ``embeddings`` — abstract embedder + deterministic placeholder (leaf).
* ``storage`` — abstract persistence contract.
* ``base`` — abstract knowledge store.
* ``loader``, ``parser``, ``chunker`` — ingestion utilities.
* ``vectorstore`` — in-memory vector index.
* ``store`` — concrete in-memory knowledge store.
* ``retriever`` — query pipeline.
* ``engine`` — orchestrator.
"""

from __future__ import annotations

from atlas.knowledge.base import KnowledgeStore
from atlas.knowledge.chunker import TextChunker
from atlas.knowledge.embeddings import EmbeddingModel, HashingEmbedder
from atlas.knowledge.engine import KnowledgeEngine
from atlas.knowledge.loader import DocumentLoader
from atlas.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeResult,
)
from atlas.knowledge.parser import DocumentParser
from atlas.knowledge.retriever import Retriever
from atlas.knowledge.storage import KnowledgeStorage
from atlas.knowledge.store import InMemoryKnowledgeStore
from atlas.knowledge.vectorstore import InMemoryVectorStore

__all__ = [
    "DocumentLoader",
    "DocumentParser",
    "EmbeddingModel",
    "HashingEmbedder",
    "InMemoryKnowledgeStore",
    "InMemoryVectorStore",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeEngine",
    "KnowledgeQuery",
    "KnowledgeResult",
    "KnowledgeStorage",
    "KnowledgeStore",
    "Retriever",
    "TextChunker",
]
