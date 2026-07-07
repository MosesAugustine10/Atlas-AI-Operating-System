"""Navigation model — owns the ordered catalogue of Studio pages.

The :class:`NavigationModel` is the single source of truth for which
pages exist, how they are grouped, which one is currently active, and
which are enabled. It is a pure-Python Model-layer component: it has no
Qt dependency and emits no signals — ViewModels observe it by polling or
by wrapping it.

The :class:`NavigationCategory` enum is re-exported here for convenience
even though it is defined in :mod:`atlas.studio.models.studio_models`
(this avoids a circular import between this module and the models).
"""

from __future__ import annotations

from atlas.studio.models.studio_models import (
    NavigationCategory,
    PageId,
    PageInfo,
)


class NavigationModel:
    """Ordered, queryable catalogue of Studio pages.

    The model is seeded with the built-in 17 pages on construction.
    Plugins may add or remove pages via :meth:`add_page` /
    :meth:`remove_page`.
    """

    def __init__(self) -> None:
        self._pages: list[PageInfo] = list(_default_pages())
        self._current: PageId = PageId.CHAT

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def pages(self) -> list[PageInfo]:
        """Return every page in registration order (a copy of the list)."""
        return list(self._pages)

    def page_by_id(self, page_id: PageId | str) -> PageInfo | None:
        """Return the :class:`PageInfo` for ``page_id`` or ``None``."""
        target = PageId(page_id) if not isinstance(page_id, PageId) else page_id
        for page in self._pages:
            if page.id is target or page.id == target:
                return page
        return None

    def pages_by_category(self, category: NavigationCategory | str) -> list[PageInfo]:
        """Return enabled pages in ``category`` sorted by position."""
        target = (
            NavigationCategory(category)
            if not isinstance(category, NavigationCategory)
            else category
        )
        matches = [p for p in self._pages if p.category == target and p.enabled]
        return sorted(matches, key=lambda p: p.position)

    def categories(self) -> list[NavigationCategory]:
        """Return every category that has at least one page, in enum order."""
        seen: list[NavigationCategory] = []
        for page in self._pages:
            if page.category not in seen:
                seen.append(page.category)
        return seen

    # ------------------------------------------------------------------
    # Current page
    # ------------------------------------------------------------------

    def current_page(self) -> PageInfo:
        """Return the :class:`PageInfo` for the active page.

        Falls back to the first enabled page if the current page was
        removed or disabled.
        """
        info = self.page_by_id(self._current)
        if info is not None and info.enabled:
            return info
        for page in self._pages:
            if page.enabled:
                self._current = page.id
                return page
        # No enabled pages — return a synthetic fallback so callers never
        # get ``None`` from a non-Optional method.
        return PageInfo(
            id=self._current,
            title="Studio",
            icon="layout-dashboard",
            description="No pages available",
            category=NavigationCategory.SYSTEM,
            position=0,
            enabled=False,
        )

    def set_current(self, page_id: PageId | str) -> PageInfo | None:
        """Activate ``page_id``.

        Returns the new page or ``None`` if unknown/disabled.
        """
        info = self.page_by_id(page_id)
        if info is None or not info.enabled:
            return None
        self._current = info.id
        return info

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_page(self, page: PageInfo) -> NavigationModel:
        """Register a new page. Replaces an existing page with the same id."""
        self._pages = [p for p in self._pages if p.id != page.id]
        self._pages.append(page)
        return self

    def remove_page(self, page_id: PageId | str) -> bool:
        """Remove a page by id. Returns ``True`` if a page was removed."""
        target = PageId(page_id) if not isinstance(page_id, PageId) else page_id
        before = len(self._pages)
        self._pages = [p for p in self._pages if p.id != target]
        removed = len(self._pages) < before
        if removed and self._current == target:
            # Pick a new current page if we removed the active one.
            self._current = self._pages[0].id if self._pages else PageId.CHAT
        return removed

    def set_enabled(self, page_id: PageId | str, enabled: bool) -> NavigationModel:
        """Enable or disable a page by id. Returns ``self`` for chaining."""
        target = PageId(page_id) if not isinstance(page_id, PageId) else page_id
        updated: list[PageInfo] = []
        for page in self._pages:
            if page.id == target:
                updated.append(
                    PageInfo(
                        id=page.id,
                        title=page.title,
                        icon=page.icon,
                        description=page.description,
                        category=page.category,
                        position=page.position,
                        enabled=enabled,
                    )
                )
            else:
                updated.append(page)
        self._pages = updated
        return self

    def __len__(self) -> int:
        return len(self._pages)

    def __repr__(self) -> str:
        return (
            f"<NavigationModel pages={len(self._pages)} "
            f"current={self._current.value!r}>"
        )


def _default_pages() -> list[PageInfo]:
    """Return the built-in 17 Studio pages in display order."""
    return [
        # --- Main -------------------------------------------------------
        PageInfo(
            id=PageId.CHAT,
            title="Chat",
            icon="message-square",
            description="Conversational interface to the Atlas brain",
            category=NavigationCategory.MAIN,
            position=10,
        ),
        PageInfo(
            id=PageId.PROJECTS,
            title="Projects",
            icon="folder-kanban",
            description="Manage projects and workspaces",
            category=NavigationCategory.MAIN,
            position=20,
        ),
        PageInfo(
            id=PageId.AGENTS,
            title="Agents",
            icon="bot",
            description="Inspect and control Atlas agents",
            category=NavigationCategory.MAIN,
            position=30,
        ),
        PageInfo(
            id=PageId.PROVIDERS,
            title="Providers",
            icon="cpu",
            description="LLM providers and routing",
            category=NavigationCategory.MAIN,
            position=40,
        ),
        # --- Monitoring -------------------------------------------------
        PageInfo(
            id=PageId.MEMORY,
            title="Memory",
            icon="brain-circuit",
            description="Persistent memory stores",
            category=NavigationCategory.MONITORING,
            position=10,
        ),
        PageInfo(
            id=PageId.KNOWLEDGE,
            title="Knowledge",
            icon="library",
            description="Indexed knowledge base",
            category=NavigationCategory.MONITORING,
            position=20,
        ),
        PageInfo(
            id=PageId.WORKFLOWS,
            title="Workflows",
            icon="git-branch",
            description="Reusable workflow runs",
            category=NavigationCategory.MONITORING,
            position=30,
        ),
        PageInfo(
            id=PageId.EXECUTIONS,
            title="Executions",
            icon="activity",
            description="Live execution timelines",
            category=NavigationCategory.MONITORING,
            position=40,
        ),
        PageInfo(
            id=PageId.ARTIFACTS,
            title="Artifacts",
            icon="file-stack",
            description="Outputs produced by Atlas",
            category=NavigationCategory.MONITORING,
            position=50,
        ),
        # --- Tools ------------------------------------------------------
        PageInfo(
            id=PageId.SKILLS,
            title="Skills",
            icon="sparkles",
            description="Reusable skill library",
            category=NavigationCategory.TOOLS,
            position=10,
        ),
        PageInfo(
            id=PageId.TOOLS,
            title="Tools",
            icon="wrench",
            description="Governed tool registry",
            category=NavigationCategory.TOOLS,
            position=20,
        ),
        PageInfo(
            id=PageId.MCP,
            title="MCP",
            icon="plug",
            description="Model Context Protocol connectors",
            category=NavigationCategory.TOOLS,
            position=30,
        ),
        PageInfo(
            id=PageId.BROWSER,
            title="Browser",
            icon="globe",
            description="Browser automation",
            category=NavigationCategory.TOOLS,
            position=40,
        ),
        PageInfo(
            id=PageId.BLENDER,
            title="Blender",
            icon="box",
            description="Blender 3D integration",
            category=NavigationCategory.TOOLS,
            position=50,
        ),
        PageInfo(
            id=PageId.MINING,
            title="Mining",
            icon="pickaxe",
            description="Data mining pipelines",
            category=NavigationCategory.TOOLS,
            position=60,
        ),
        # --- System -----------------------------------------------------
        PageInfo(
            id=PageId.LOGS,
            title="Logs",
            icon="scroll-text",
            description="Live system logs and events",
            category=NavigationCategory.SYSTEM,
            position=10,
        ),
        PageInfo(
            id=PageId.SETTINGS,
            title="Settings",
            icon="settings",
            description="Studio and Atlas configuration",
            category=NavigationCategory.SYSTEM,
            position=20,
        ),
    ]


__all__ = ["NavigationCategory", "NavigationModel"]
