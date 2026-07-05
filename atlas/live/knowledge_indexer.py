"""Knowledge indexer — auto-index generated files in the Knowledge Engine.

The :class:`KnowledgeIndexer` watches for generated files and
automatically ingests them into the :class:`KnowledgeEngine` so that
knowledge search immediately finds new content.

Supported file types: markdown, python, json, csv, text, html, pdf.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas.core.logger import get_logger
from atlas.live.event_bus import LiveEventBus

#: File extensions that are auto-indexed.
INDEXABLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".python",
        ".py",
        ".json",
        ".csv",
        ".txt",
        ".html",
        ".htm",
        ".yaml",
        ".yml",
        ".xml",
        ".rst",
        ".log",
    }
)


class KnowledgeIndexer:
    """Auto-indexes generated files in the Knowledge Engine.

    Parameters:
        knowledge: The :class:`KnowledgeEngine` (or compatible). Must
            have an ``ingest_text(content, source, tags, **metadata)``
            method.
        event_bus: Optional :class:`LiveEventBus` for emitting events.
    """

    def __init__(
        self,
        knowledge: Any = None,
        event_bus: LiveEventBus | None = None,
    ) -> None:
        self.knowledge = knowledge
        self.event_bus = event_bus if event_bus is not None else LiveEventBus()
        self.logger = get_logger("live.knowledge_indexer")
        self._indexed: set[str] = set()

    def index_file(self, path: str | Path) -> str | None:
        """Index a single file.

        Returns the document id if successful, ``None`` otherwise.
        """
        if self.knowledge is None:
            return None
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            return None
        ext = file_path.suffix.lower()
        if ext not in INDEXABLE_EXTENSIONS:
            return None
        try:
            content = file_path.read_text(encoding="utf-8")
            return self.index_text(
                content=content,
                source=str(file_path),
                tags=[ext.lstrip("."), "indexed"],
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to index %s: %s", file_path, exc)
            return None

    def index_text(
        self,
        content: str,
        source: str = "",
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> str | None:
        """Index inline text content.

        Returns the document id if successful, ``None`` otherwise.
        """
        if self.knowledge is None:
            return None
        try:
            ingest_fn = getattr(self.knowledge, "ingest_text", None)
            if not callable(ingest_fn):
                return None
            doc = ingest_fn(
                content=content,
                source=source,
                tags=tags or [],
                **metadata,
            )
            doc_id = getattr(doc, "id", "")
            self._indexed.add(doc_id)
            self.event_bus.emit_knowledge_indexed(doc_id, source)
            self.logger.info("Indexed %s (%d chars)", source or doc_id, len(content))
            return doc_id
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to index text: %s", exc)
            return None

    def index_directory(self, dir_path: str | Path) -> int:
        """Index every indexable file in ``dir_path``.

        Returns the number of files indexed.
        """
        directory = Path(dir_path)
        if not directory.exists() or not directory.is_dir():
            return 0
        count = 0
        for ext in INDEXABLE_EXTENSIONS:
            for file_path in directory.rglob(f"*{ext}"):
                if self.index_file(file_path) is not None:
                    count += 1
        return count

    def is_indexable(self, filename: str) -> bool:
        """Return ``True`` if ``filename`` has an indexable extension."""
        return Path(filename).suffix.lower() in INDEXABLE_EXTENSIONS

    def indexed_count(self) -> int:
        """Return the number of documents indexed by this indexer."""
        return len(self._indexed)

    def indexed_ids(self) -> list[str]:
        """Return the IDs of every indexed document."""
        return sorted(self._indexed)

    def search(self, query: str, top_k: int = 5) -> list[Any]:
        """Search the knowledge engine."""
        if self.knowledge is None:
            return []
        try:
            search_fn = getattr(self.knowledge, "search", None)
            if callable(search_fn):
                return list(search_fn(query, top_k=top_k))
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Knowledge search failed: %s", exc)
        return []

    def __repr__(self) -> str:
        return f"<KnowledgeIndexer indexed={len(self._indexed)}>"


__all__ = ["INDEXABLE_EXTENSIONS", "KnowledgeIndexer"]
