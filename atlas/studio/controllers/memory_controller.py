"""Memory controller — wraps the MemoryEngine for the Studio UI.

The :class:`MemoryController` adapts the
:class:`~atlas.memory.engine.MemoryEngine` (or any duck-typed
equivalent) into a list of
:class:`~atlas.studio.models.MemoryEntry` snapshots for the Memory
page. All access is defensive: a ``None`` engine yields empty results.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from atlas.studio.models.studio_models import MemoryEntry

#: The five Atlas memory store attribute names, in canonical order.
_STORE_NAMES: tuple[str, ...] = (
    "working",
    "episodic",
    "semantic",
    "procedural",
    "reflection",
)


class MemoryController:
    """ViewModel for the Memory page.

    Parameters:
        engine: Optional :class:`~atlas.memory.engine.MemoryEngine`-like
            object. Expected duck-typed surface (any subset):
            ``recall(query)`` -> list of memory entries, ``forget(id)``,
            and the five stores (``working``, ``episodic``, ``semantic``,
            ``procedural``, ``reflection``) each exposing ``all()`` /
            ``query()`` / ``count()``.
        category_key: Attribute name used to derive a store's category
            label (defaults to ``"category"``).
    """

    def __init__(self, engine: Any = None) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def entries(
        self, category: str | None = None, limit: int = 100
    ) -> list[MemoryEntry]:
        """Return memory entries, optionally filtered by ``category``.

        Results are returned newest-first and capped at ``limit``.
        """
        raw = self._recall(category=category, limit=limit)
        items = [self._to_entry(item) for item in raw]
        items.sort(key=lambda e: e.timestamp, reverse=True)
        return items[:limit]

    def search(self, query: str, limit: int = 100) -> list[MemoryEntry]:
        """Search memory entries by free-text ``query``."""
        if not query:
            return self.entries(limit=limit)
        raw = self._recall(text=query, limit=limit)
        items = [self._to_entry(item) for item in raw]
        query_lower = query.lower()
        # Extra client-side filter in case the engine does a broad recall.
        filtered = [
            item
            for item in items
            if query_lower in item.content_preview.lower()
            or query_lower in item.source.lower()
            or any(query_lower in tag.lower() for tag in item.tags)
        ]
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        return filtered[:limit]

    def categories(self) -> list[str]:
        """Return the distinct memory category keys that have entries."""
        if self._engine is None:
            return []
        categories: list[str] = []
        for store_name in _STORE_NAMES:
            store = getattr(self._engine, store_name, None)
            if store is None:
                continue
            count = self._store_count(store)
            if count > 0:
                categories.append(store_name)
        return categories

    def count(self, category: str | None = None) -> int:
        """Return the total number of memory entries, optionally per category."""
        if self._engine is None:
            return 0
        if category is not None:
            store = getattr(self._engine, category, None)
            if store is None:
                return 0
            return self._store_count(store)
        total = 0
        for store_name in _STORE_NAMES:
            store = getattr(self._engine, store_name, None)
            if store is not None:
                total += self._store_count(store)
        return total

    def __len__(self) -> int:
        return self.count()

    def __repr__(self) -> str:
        return f"<MemoryController count={self.count()}>"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _recall(self, **kwargs: Any) -> list[Any]:
        """Invoke ``engine.recall`` with the given keyword filters."""
        if self._engine is None:
            return []
        recall = getattr(self._engine, "recall", None)
        if not callable(recall):
            # Fall back to merging each store's contents.
            return self._gather_from_stores(kwargs.get("category"))
        try:
            result = recall(**kwargs) if kwargs else recall()
        except TypeError:
            try:
                result = recall()
            except Exception:  # noqa: BLE001
                return []
        except Exception:  # noqa: BLE001
            return []
        if isinstance(result, list):
            return result
        return []

    def _gather_from_stores(self, category: str | None) -> list[Any]:
        """Gather entries directly from the stores when recall is unavailable."""
        items: list[Any] = []
        store_names = [category] if category else list(_STORE_NAMES)
        for name in store_names:
            store = getattr(self._engine, name, None) if name else None
            if store is None:
                continue
            all_method = getattr(store, "all", None)
            if callable(all_method):
                try:
                    items.extend(all_method())
                except Exception:  # noqa: BLE001
                    pass
        return items

    @staticmethod
    def _store_count(store: Any) -> int:
        """Return the number of entries in a memory store."""
        count = getattr(store, "count", None)
        if callable(count):
            try:
                return int(count())
            except Exception:  # noqa: BLE001
                pass
        all_method = getattr(store, "all", None)
        if callable(all_method):
            try:
                return len(all_method())
            except Exception:  # noqa: BLE001
                pass
        try:
            return len(store)
        except TypeError:
            return 0

    @staticmethod
    def _to_entry(item: Any) -> MemoryEntry:
        """Convert a raw memory entry into a :class:`MemoryEntry` view."""
        entry_id = str(getattr(item, "id", "") or "")
        category = getattr(item, "category", None)
        category_str = (
            getattr(category, "value", None)
            if category is not None and not isinstance(category, str)
            else category
        )
        if category_str is None:
            category_str = "working"
        content = getattr(item, "content", None)
        preview = _content_preview(content)
        tags = list(getattr(item, "tags", []) or [])
        source = str(getattr(item, "source", "") or "")
        timestamp = getattr(item, "timestamp", None)
        if not isinstance(timestamp, datetime):
            from datetime import UTC
            from datetime import datetime as _dt

            timestamp = _dt.now(UTC)
        return MemoryEntry(
            id=entry_id,
            category=str(category_str),
            content_preview=preview,
            tags=tags,
            source=source,
            timestamp=timestamp,
        )


def _content_preview(content: Any) -> str:
    """Render a short string preview of arbitrary memory content."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content[:200]
    try:
        text = repr(content)
    except Exception:  # noqa: BLE001
        text = "<unrenderable>"
    return text[:200]


__all__ = ["MemoryController"]
