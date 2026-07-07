"""Atlas production application — the real Qt desktop shell.

This package is the **single composition root** for the Atlas AI
Operating System desktop application. It wires together every existing
subsystem (Brain, Runtime, Execution Engine, Provider Manager, MCP
Manager, Memory Engine, Knowledge Engine, Workflow Engine, Studio,
IDE, Creator Studio, Command Center) into one executable Qt
application.

Phase 1 deliverables (this package):

* :class:`AtlasApp` (:mod:`atlas.app.bootstrap`) — the bootstrap that
  owns every controller and the Qt application.
* :class:`MainWindow` (:mod:`atlas.app.main_window`) — the real Qt
  main window with sidebar, stacked pages, top bar, and status bar.
* :class:`SidebarWidget` (:mod:`atlas.app.widgets.sidebar`) — the real
  navigation sidebar.
* 12 real page widgets in :mod:`atlas.app.pages`, each using an
  existing controller from :mod:`atlas.studio.controllers`.

Every page uses a real controller — no placeholders. The application
is importable on headless hosts (every View class raises
:class:`ImportError` on instantiation when PySide6 is unavailable, but
the :class:`AtlasApp` controllers dict is always available for
headless testing).

Start the application from the CLI:

    atlas launch

Or programmatically:

    from atlas.app import AtlasApp
    AtlasApp().run()
"""

from __future__ import annotations

__version__ = "1.0.0"


def has_qt() -> bool:
    """Return ``True`` if PySide6 is importable and usable."""
    try:
        from PySide6 import QtWidgets  # noqa: F401  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 — optional dependency / plugin load
        return False
    return True


from atlas.app.bootstrap import AtlasApp  # noqa: E402

# Re-export MainWindow and SidebarWidget (graceful degradation)
from atlas.app.main_window import MainWindow  # noqa: E402

# Re-export pages (graceful degradation)
from atlas.app.pages.agents_page import AgentsPage  # noqa: E402
from atlas.app.pages.artifacts_page import ArtifactsPage  # noqa: E402
from atlas.app.pages.chat_page import ChatPage  # noqa: E402
from atlas.app.pages.execution_page import ExecutionPage  # noqa: E402
from atlas.app.pages.knowledge_page import KnowledgePage  # noqa: E402
from atlas.app.pages.logs_page import LogsPage  # noqa: E402
from atlas.app.pages.mcp_page import MCPPage  # noqa: E402
from atlas.app.pages.memory_page import MemoryPage  # noqa: E402
from atlas.app.pages.providers_page import ProvidersPage  # noqa: E402
from atlas.app.pages.settings_page import SettingsPage  # noqa: E402
from atlas.app.pages.system_page import SystemPage  # noqa: E402
from atlas.app.pages.tools_page import ToolsPage  # noqa: E402
from atlas.app.widgets.sidebar import SidebarWidget  # noqa: E402

__all__ = [
    "__version__",
    "has_qt",
    "AtlasApp",
    "MainWindow",
    "SidebarWidget",
    # Pages
    "AgentsPage",
    "ArtifactsPage",
    "ChatPage",
    "ExecutionPage",
    "KnowledgePage",
    "LogsPage",
    "MCPPage",
    "MemoryPage",
    "ProvidersPage",
    "SettingsPage",
    "SystemPage",
    "ToolsPage",
]
