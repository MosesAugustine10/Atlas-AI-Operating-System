"""Knowledge controller — wraps the KnowledgeEngine for the Studio UI.

The :class:`KnowledgeController` adapts the
:class:`~atlas.knowledge.engine.KnowledgeEngine` (or any duck-typed
equivalent) into a list of
:class:`~atlas.studio.models.KnowledgeDoc` snapshots for the Knowledge
page. All access is defensive: a ``None`` engine yields empty results.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from atlas.studio.models.studio_models import KnowledgeDoc


class KnowledgeController:
    """ViewModel for the Knowledge page.

    Parameters:
        engine: Optional :class:`~atlas.knowledge.engine.KnowledgeEngine`
            -like object. Expected duck-typed surface (any subset):
            ``store`` exposing ``documents()`` / ``chunks(document_id)``
            / ``count_documents()`` / ``count_chunks()``, and
            ``retriever.search(query)``.
    """

    def __init__(self, engine: Any = None) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def documents(self, limit: int = 100) -> list[KnowledgeDoc]:
        """Return indexed documents as :class:`KnowledgeDoc` (newest first)."""
        raw = self._list_documents(limit)
        docs = [self._to_doc(item) for item in raw]
        docs.sort(key=lambda d: d.created_at, reverse=True)
        return docs[:limit]

    def search(self, query: str, limit: int = 20) -> list[KnowledgeDoc]:
        """Search documents by ``query`` via the engine's retriever.

        Returns the documents backing the top matching chunks, deduplicated
        and capped at ``limit``.
        """
        if self._engine is None or not query:
            return self.documents(limit=limit)
        retriever = getattr(self._engine, "retriever", None)
        search = getattr(retriever, "search", None) or getattr(
            retriever, "retrieve", None
        )
        if not callable(search):
            # Fall back to client-side filtering on document source.
            query_lower = query.lower()
            return [
                d
                for d in self.documents(limit=limit)
                if query_lower in d.source.lower()
                or any(query_lower in t.lower() for t in d.tags)
            ]
        try:
            results = search(query)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(results, list):
            return []
        seen: set[str] = set()
        docs: list[KnowledgeDoc] = []
        for result in results:
            document = getattr(result, "document", None) or result
            doc = self._to_doc(document)
            if doc.id in seen:
                continue
            seen.add(doc.id)
            docs.append(doc)
            if len(docs) >= limit:
                break
        return docs

    def chunks(self, doc_id: str) -> list[Any]:
        """Return the raw chunks for ``doc_id`` (empty list if unknown).

        Chunks are returned as-is from the store; the UI renders them
        directly since their shape is stable.
        """
        if self._engine is None:
            return []
        store = getattr(self._engine, "store", None)
        if store is None:
            return []
        for method_name in ("chunks", "chunks_for", "get_chunks"):
            method = getattr(store, method_name, None)
            if callable(method):
                try:
                    result = method(doc_id)
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(result, list):
                    return result
        return []

    def count(self) -> int:
        """Return the total number of indexed documents."""
        if self._engine is None:
            return 0
        store = getattr(self._engine, "store", None)
        if store is None:
            return 0
        for method_name in ("count_documents", "document_count", "count"):
            method = getattr(store, method_name, None)
            if callable(method):
                try:
                    return int(method())
                except Exception:  # noqa: BLE001
                    continue
        # Fall back to len(documents()).
        try:
            docs_method = getattr(store, "documents", None)
            if callable(docs_method):
                return len(docs_method())
        except Exception:  # noqa: BLE001
            pass
        return 0

    def __len__(self) -> int:
        return self.count()

    def __repr__(self) -> str:
        return f"<KnowledgeController documents={self.count()}>"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _list_documents(self, limit: int) -> list[Any]:
        """Return the raw document objects from the engine's store."""
        if self._engine is None:
            return []
        store = getattr(self._engine, "store", None)
        if store is None:
            return []
        for method_name in ("documents", "all_documents", "list_documents"):
            method = getattr(store, method_name, None)
            if callable(method):
                try:
                    result = method()
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(result, list):
                    return result
        try:
            return list(store)
        except TypeError:
            return []

    @staticmethod
    def _to_doc(document: Any) -> KnowledgeDoc:
        """Convert a raw knowledge document into a :class:`KnowledgeDoc`."""
        doc_id = str(getattr(document, "id", "") or "")
        source = str(getattr(document, "source", "") or "")
        content_type = str(
            getattr(document, "content_type", "text/plain") or "text/plain"
        )
        created_at = getattr(document, "created_at", None)
        if not isinstance(created_at, datetime):
            from datetime import UTC
            from datetime import datetime as _dt

            created_at = _dt.now(UTC)
        tags = list(getattr(document, "tags", []) or [])
        # Chunk count is best-effort: some document objects carry it.
        chunk_count = 0
        for attr in ("chunk_count", "num_chunks", "chunks"):
            value = getattr(document, attr, None)
            if isinstance(value, int):
                chunk_count = value
                break
            if isinstance(value, list):
                chunk_count = len(value)
                break
        return KnowledgeDoc(
            id=doc_id,
            source=source,
            content_type=content_type,
            chunk_count=chunk_count,
            created_at=created_at,
            tags=tags,
        )


__all__ = ["KnowledgeController"]
