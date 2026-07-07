"""Workspace model — manages open tabs, pinned tabs and the active tab.

The :class:`WorkspaceModel` is the Model-layer representation of the
Studio tab strip. Tabs are ordered with pinned tabs first, followed by
unpinned tabs in opening order. The model is pure Python (no Qt) so it
can be unit-tested headlessly.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Iterable

from atlas.studio.models.studio_models import PageId, TabInfo


class SplitOrientation(enum.StrEnum):
    """Orientation for splitting the workspace view."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class WorkspaceModel:
    """Owns the ordered set of open tabs and the active tab id.

    Tabs are stored as :class:`TabInfo` instances. Pinned tabs are kept
    at the front of the strip; within each group order is preserved.
    """

    def __init__(self) -> None:
        self._tabs: list[TabInfo] = []
        self._active_id: str | None = None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def tabs(self) -> list[TabInfo]:
        """Return every tab in display order (pinned first)."""
        return list(self._sorted_tabs())

    def tab_by_id(self, tab_id: str) -> TabInfo | None:
        """Return the tab with ``tab_id`` or ``None``."""
        for tab in self._tabs:
            if tab.id == tab_id:
                return tab
        return None

    def active_tab(self) -> TabInfo | None:
        """Return the active tab, or ``None`` if no tab is open."""
        if self._active_id is None:
            return None
        return self.tab_by_id(self._active_id)

    def has_unsaved(self) -> bool:
        """Return ``True`` if any tab is marked as modified."""
        return any(tab.modified for tab in self._tabs)

    def modified_tabs(self) -> list[TabInfo]:
        """Return every tab currently marked as modified."""
        return [tab for tab in self._tabs if tab.modified]

    def __len__(self) -> int:
        return len(self._tabs)

    def __contains__(self, tab_id: object) -> bool:
        return isinstance(tab_id, str) and any(t.id == tab_id for t in self._tabs)

    def __repr__(self) -> str:
        return f"<WorkspaceModel tabs={len(self._tabs)} " f"active={self._active_id!r}>"

    # ------------------------------------------------------------------
    # Tab lifecycle
    # ------------------------------------------------------------------

    def open_tab(
        self,
        page_id: PageId | str,
        title: str,
        *,
        icon: str = "",
        pinned: bool = False,
        closable: bool = True,
        tooltip: str = "",
    ) -> TabInfo:
        """Open a new tab for ``page_id`` and activate it.

        If a tab for the same page already exists, it is activated
        instead of duplicated (a tab models a single live page view).

        Returns the (possibly existing) :class:`TabInfo`.
        """
        page = PageId(page_id) if not isinstance(page_id, PageId) else page_id
        for tab in self._tabs:
            if tab.page_id == page:
                self._active_id = tab.id
                return tab
        tab = TabInfo(
            id=f"tab_{uuid.uuid4().hex[:12]}",
            title=title,
            page_id=page,
            icon=icon,
            closable=closable,
            pinned=pinned,
            tooltip=tooltip or title,
        )
        self._tabs.append(tab)
        self._active_id = tab.id
        return tab

    def close_tab(self, tab_id: str) -> bool:
        """Close ``tab_id``. Returns ``True`` if a tab was closed.

        If the closed tab was active, the nearest remaining tab becomes
        active (preferring the tab that followed it).
        """
        index = self._index_of(tab_id)
        if index is None:
            return False
        self._tabs.pop(index)
        if self._active_id == tab_id:
            if self._tabs and index < len(self._tabs):
                self._active_id = self._tabs[index].id
            elif self._tabs:
                self._active_id = self._tabs[-1].id
            else:
                self._active_id = None
        return True

    def set_active(self, tab_id: str) -> TabInfo | None:
        """Activate ``tab_id``. Returns the tab or ``None`` if unknown."""
        tab = self.tab_by_id(tab_id)
        if tab is None:
            return None
        self._active_id = tab.id
        return tab

    # ------------------------------------------------------------------
    # Pinning & modification
    # ------------------------------------------------------------------

    def pin_tab(self, tab_id: str) -> TabInfo | None:
        """Pin ``tab_id`` (moves it to the front of the strip)."""
        return self._set_pinned(tab_id, True)

    def unpin_tab(self, tab_id: str) -> TabInfo | None:
        """Unpin ``tab_id`` (moves it after the last pinned tab)."""
        return self._set_pinned(tab_id, False)

    def mark_modified(self, tab_id: str, modified: bool = True) -> TabInfo | None:
        """Set the ``modified`` flag on ``tab_id``. Returns the updated tab."""
        tab = self.tab_by_id(tab_id)
        if tab is None:
            return None
        self._tabs = [
            t if t.id != tab_id else _replace(t, modified=modified) for t in self._tabs
        ]
        return self.tab_by_id(tab_id)

    # ------------------------------------------------------------------
    # Reordering
    # ------------------------------------------------------------------

    def reorder(self, ids: Iterable[str]) -> bool:
        """Reorder tabs to match ``ids``.

        Pinned tabs are always forced to the front regardless of the
        requested order. Any tabs not present in ``ids`` keep their
        relative order at the end. Unknown ids in ``ids`` are ignored.
        Returns ``True`` if the order changed.
        """
        id_list = [tid for tid in ids if self.tab_by_id(tid) is not None]
        # Preserve any tabs not mentioned in the requested order.
        for tab in self._tabs:
            if tab.id not in id_list:
                id_list.append(tab.id)
        new_order = [self.tab_by_id(tid) for tid in id_list]  # type: ignore[assignment]
        new_order = [t for t in new_order if t is not None]
        before = [t.id for t in self._sorted_tabs()]
        after = [t.id for t in new_order]
        self._tabs = new_order
        return before != after

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _index_of(self, tab_id: str) -> int | None:
        for index, tab in enumerate(self._tabs):
            if tab.id == tab_id:
                return index
        return None

    def _set_pinned(self, tab_id: str, pinned: bool) -> TabInfo | None:
        tab = self.tab_by_id(tab_id)
        if tab is None:
            return None
        updated = _replace(tab, pinned=pinned)
        self._tabs = [t if t.id != tab_id else updated for t in self._tabs]
        return updated

    def _sorted_tabs(self) -> list[TabInfo]:
        """Return tabs with pinned first, preserving relative order."""
        return sorted(self._tabs, key=lambda t: (not t.pinned,))


def _replace(tab: TabInfo, **changes: object) -> TabInfo:
    """Return a copy of ``tab`` with ``changes`` applied (frozen dataclass)."""
    from dataclasses import replace as _dc_replace

    return _dc_replace(tab, **changes)


__all__ = ["SplitOrientation", "WorkspaceModel"]
