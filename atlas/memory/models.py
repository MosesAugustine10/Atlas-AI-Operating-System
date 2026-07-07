"""Memory data models for the Atlas Memory Engine.

Pure dataclasses representing the shape of every memory record in the
system. These are leaf nodes — they hold data, they hold no behaviour
beyond construction helpers, and they have no dependencies on the rest of
the memory package.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class MemoryCategory(enum.StrEnum):
    """High-level categories a memory record can belong to."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    REFLECTION = "reflection"


class MemoryPriority(enum.IntEnum):
    """Priority levels that control retention and retrieval ordering."""

    LOW = 1
    NORMAL = 3
    HIGH = 5
    CRITICAL = 10


@dataclass
class MemoryEntry:
    """A single record in the Atlas memory system.

    Attributes:
        id: Unique identifier for this entry.
        category: Which memory store this entry belongs to.
        content: The primary payload — the text, data, or structured content.
        source: Origin of the memory (e.g. user request, system inference).
        tags: Free-form labels for retrieval filtering.
        priority: Retention and retrieval priority.
        timestamp: When this entry was created.
        metadata: Free-form bag for additional runtime information.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    category: MemoryCategory = MemoryCategory.WORKING
    content: Any = None
    source: str | None = None
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.NORMAL
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches_tag(self, tag: str) -> bool:
        """Return ``True`` if ``tag`` is in this entry's tag list."""
        return tag in self.tags


@dataclass
class MemoryQuery:
    """Structured query for searching across memory stores.

    Attributes:
        text: Free-text search string (matched against content).
        tags: Tags that must all be present on a matching entry.
        category: Restrict results to a single memory category.
        since: Include only entries created at or after this timestamp.
        until: Include only entries created at or before this timestamp.
        limit: Maximum number of results to return.
    """

    text: str = ""
    tags: list[str] = field(default_factory=list)
    category: MemoryCategory | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 20
