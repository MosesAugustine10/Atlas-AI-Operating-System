"""Knowledge data models for the Atlas Knowledge Engine.

Pure immutable dataclasses representing the shape of every record in the
knowledge system: documents, chunks, queries, and results. These are leaf
nodes — they hold data and construction helpers only, with no dependencies
on the rest of the knowledge package.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _uuid() -> str:
    """Return a new unique identifier."""
    return uuid.uuid4().hex


@dataclass(frozen=True)
class KnowledgeDocument:
    """A single ingested document.

    Attributes:
        id: Unique identifier for this document.
        source: Origin of the document (file path, URL, etc.).
        content: The full extracted text content.
        content_type: MIME-style type hint (``text/plain``, ``text/markdown``...).
        tags: Free-form labels for retrieval filtering.
        metadata: Free-form bag for additional information.
        created_at: When this document record was created.
    """

    content: str
    source: str
    content_type: str = "text/plain"
    id: str = field(default_factory=_uuid)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class KnowledgeChunk:
    """A chunk of a :class:`KnowledgeDocument` produced by the chunker.

    Attributes:
        id: Unique identifier for this chunk.
        document_id: Id of the parent document.
        content: The text content of this chunk.
        index: Position of this chunk within the parent document (0-based).
        tags: Inherited + chunk-specific tags.
        metadata: Free-form bag for additional information.
        created_at: When this chunk record was created.
    """

    document_id: str
    content: str
    index: int
    id: str = field(default_factory=_uuid)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class KnowledgeQuery:
    """Structured query for searching the knowledge store.

    Attributes:
        text: The natural-language query string.
        top_k: Maximum number of results to return.
        tags: Tags that must all be present on a matching chunk.
        min_score: Minimum relevance score (0.0–1.0) for returned results.
    """

    text: str
    top_k: int = 5
    tags: list[str] = field(default_factory=list)
    min_score: float = 0.0


@dataclass(frozen=True)
class KnowledgeResult:
    """A single retrieval result.

    Attributes:
        chunk: The matched :class:`KnowledgeChunk`.
        document: The parent :class:`KnowledgeDocument`.
        score: Relevance score in the range 0.0–1.0.
    """

    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
