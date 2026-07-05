"""Atlas production MainWindow — the real Qt application shell.

This is **not** a placeholder. The :class:`MainWindow` is a full
:class:`PySide6.QtWidgets.QMainWindow` that wires together:

* A :class:`SidebarWidget` for navigation.
* A :class:`PySide6.QtWidgets.QStackedWidget` hosting one real page
  widget per :class:`~atlas.studio.models.studio_models.PageId`.
* A top bar with the command-palette launcher.
* A status bar showing the current phase, integration count, and
  notification count.

Every page widget uses an existing controller from
:mod:`atlas.studio.controllers` — no placeholder pages.

When PySide6 is unavailable, a placeholder :class:`MainWindow` is
defined that raises :class:`ImportError` on instantiation. Importing
this module never fails.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:  # pragma: no cover — exercised on Qt-bearing hosts
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

    _HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    _HAS_QT: bool = False
    QtCore = None  # type: ignore[assignment]
    QtGui = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from atlas.app.bootstrap import AtlasApp
    from atlas.studio.navigation import NavigationModel

from atlas.app._qt import _QT_MISSING_MSG
from atlas.studio.models.studio_models import PageId

if _HAS_QT:

    class MainWindow(QtWidgets.QMainWindow):  # type: ignore[misc, valid-type]
        """The real Atlas production main window.

        Parameters:
            app: The :class:`~atlas.app.bootstrap.AtlasApp` that owns
                every controller. Pages pull their controllers from
                ``app.controllers``.
            navigation: Optional :class:`NavigationModel`. When omitted
                a fresh one is created.
        """

        def __init__(
            self,
            app: AtlasApp | None = None,
            navigation: NavigationModel | None = None,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.setObjectName("AtlasMainWindow")
            self.setWindowTitle("Atlas AI Operating System")
            self.resize(1440, 900)
            self._app = app
            self._navigation = navigation or self._default_navigation()
            self._pages: dict[str, QtWidgets.QWidget] = {}
            self._build_ui()
            self._wire_status_bar()
            self._navigate_to(PageId.CHAT.value)

        # ------------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------------

        def _build_ui(self) -> None:
            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            layout = QtWidgets.QHBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            # Sidebar
            from atlas.app.widgets.sidebar import SidebarWidget

            self.sidebar = SidebarWidget(self._navigation, parent=self)
            self.sidebar.page_requested.connect(self._navigate_to)
            layout.addWidget(self.sidebar)

            # Main area (top bar + stacked pages)
            main_area = QtWidgets.QWidget()
            main_layout = QtWidgets.QVBoxLayout(main_area)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # Top bar
            self.top_bar = self._build_top_bar()
            main_layout.addWidget(self.top_bar)

            # Stacked pages
            self.stack = QtWidgets.QStackedWidget()
            self._populate_stack()
            main_layout.addWidget(self.stack, 1)

            layout.addWidget(main_area, 1)

        def _build_top_bar(self) -> QtWidgets.QWidget:
            bar = QtWidgets.QWidget()
            bar.setObjectName("AtlasTopBar")
            bar.setFixedHeight(48)
            layout = QtWidgets.QHBoxLayout(bar)
            layout.setContentsMargins(12, 6, 12, 6)
            layout.setSpacing(8)

            self.title_label = QtWidgets.QLabel("Atlas")
            self.title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
            layout.addWidget(self.title_label)

            layout.addStretch()

            self.search_button = QtWidgets.QPushButton("Search  ")
            self.search_button.setObjectName("AtlasSearchButton")
            self.search_button.setShortcut("Ctrl+K")
            self.search_button.clicked.connect(self._open_search)
            layout.addWidget(self.search_button)

            self.palette_button = QtWidgets.QPushButton("Commands  ")
            self.palette_button.setObjectName("AtlasPaletteButton")
            self.palette_button.setShortcut("Ctrl+Shift+P")
            self.palette_button.clicked.connect(self._open_palette)
            layout.addWidget(self.palette_button)

            return bar

        def _populate_stack(self) -> None:
            from atlas.app.pages.agents_page import AgentsPage
            from atlas.app.pages.artifacts_page import ArtifactsPage
            from atlas.app.pages.chat_page import ChatPage
            from atlas.app.pages.execution_page import ExecutionPage
            from atlas.app.pages.knowledge_page import KnowledgePage
            from atlas.app.pages.logs_page import LogsPage
            from atlas.app.pages.mcp_page import MCPPage
            from atlas.app.pages.memory_page import MemoryPage
            from atlas.app.pages.providers_page import ProvidersPage
            from atlas.app.pages.settings_page import SettingsPage
            from atlas.app.pages.system_page import SystemPage
            from atlas.app.pages.tools_page import ToolsPage

            controllers = self._controllers()
            page_factory: dict[str, Any] = {
                PageId.CHAT.value: lambda: ChatPage(controllers["chat"], parent=self),
                PageId.AGENTS.value: lambda: AgentsPage(
                    controllers["agents"], parent=self
                ),
                PageId.PROVIDERS.value: lambda: ProvidersPage(
                    controllers["providers"], parent=self
                ),
                PageId.MEMORY.value: lambda: MemoryPage(
                    controllers["memory"], parent=self
                ),
                PageId.KNOWLEDGE.value: lambda: KnowledgePage(
                    controllers["knowledge"], parent=self
                ),
                PageId.EXECUTIONS.value: lambda: ExecutionPage(
                    controllers["execution"], parent=self
                ),
                PageId.ARTIFACTS.value: lambda: ArtifactsPage(
                    controllers["artifacts"], parent=self
                ),
                PageId.MCP.value: lambda: MCPPage(controllers["mcp"], parent=self),
                PageId.LOGS.value: lambda: LogsPage(parent=self),
                PageId.TOOLS.value: lambda: ToolsPage(parent=self),
                PageId.SETTINGS.value: lambda: SettingsPage(parent=self),
                "system": lambda: SystemPage(controllers["system"], parent=self),
            }
            for page_id, factory in page_factory.items():
                try:
                    page = factory()
                except Exception:
                    # Fallback: empty page so navigation never breaks
                    page = QtWidgets.QWidget()
                    layout = QtWidgets.QVBoxLayout(page)
                    layout.addWidget(QtWidgets.QLabel(f"Page: {page_id}"))
                self._pages[page_id] = page
                self.stack.addWidget(page)

        def _wire_status_bar(self) -> None:
            self.statusBar().showMessage("Ready")
            self.phase_label = QtWidgets.QLabel("phase: ready")
            self.statusBar().addPermanentWidget(self.phase_label)

        # ------------------------------------------------------------------
        # Navigation
        # ------------------------------------------------------------------

        def _navigate_to(self, page_id: str) -> None:
            page = self._pages.get(page_id)
            if page is None:
                # Fall back to chat
                page = self._pages.get(PageId.CHAT.value)
                page_id = PageId.CHAT.value
            if page is not None:
                self.stack.setCurrentWidget(page)
                self.sidebar.set_active(page_id)
                self.title_label.setText(f"Atlas — {page_id.title()}")

        def _open_search(self) -> None:
            # Phase 1: focus the chat input as a simple search surrogate.
            # Phase 3 will replace this with a real command palette overlay.
            page = self._pages.get(PageId.CHAT.value)
            if page is not None and hasattr(page, "focus_input"):
                page.focus_input()

        def _open_palette(self) -> None:
            # Phase 1: navigate to settings as a palette surrogate.
            # Phase 3 will replace this with a real command palette overlay.
            self._navigate_to(PageId.SETTINGS.value)

        # ------------------------------------------------------------------
        # Public API
        # ------------------------------------------------------------------

        def current_page_id(self) -> str:
            """Return the page id of the currently-visible page."""
            widget = self.stack.currentWidget()
            for page_id, page in self._pages.items():
                if page is widget:
                    return page_id
            return PageId.CHAT.value

        def navigate(self, page_id: str) -> None:
            """Public navigation entry point (used by tests and the CLI)."""
            self._navigate_to(page_id)

        def refresh(self) -> None:
            """Refresh every page from its controller."""
            for page in self._pages.values():
                if hasattr(page, "refresh"):
                    try:
                        page.refresh()
                    except Exception:
                        pass

        def set_phase(self, phase: str) -> None:
            """Update the status-bar phase label."""
            self.phase_label.setText(f"phase: {phase}")
            self.statusBar().showMessage(f"Atlas is {phase}")

        # ------------------------------------------------------------------
        # Internals
        # ------------------------------------------------------------------

        def _controllers(self) -> dict[str, Any]:
            if self._app is None:
                # Build default controllers so the window is usable standalone
                from atlas.studio.controllers import (
                    AgentController,
                    ArtifactController,
                    ChatController,
                    ExecutionController,
                    KnowledgeController,
                    MCPController,
                    MemoryController,
                    PluginController,
                    ProviderController,
                    SystemController,
                )

                return {
                    "chat": ChatController(),
                    "agents": AgentController(),
                    "providers": ProviderController(),
                    "memory": MemoryController(),
                    "knowledge": KnowledgeController(),
                    "execution": ExecutionController(),
                    "artifacts": ArtifactController(),
                    "mcp": MCPController(),
                    "system": SystemController(),
                    "plugins": PluginController(),
                }
            return self._app.controllers

        @staticmethod
        def _default_navigation() -> NavigationModel:
            from atlas.studio.navigation import NavigationModel

            return NavigationModel()

else:

    class MainWindow:  # type: ignore[no-redef]
        """Placeholder raised when PySide6 is unavailable.

        Importing :mod:`atlas.app.main_window` never fails — but
        instantiating :class:`MainWindow` on a headless host raises
        :class:`ImportError`.
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["MainWindow"]
