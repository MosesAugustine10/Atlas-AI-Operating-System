"""Atlas Studio — Qt-based control surface for the Atlas AI Operating System.

This package implements the Model and ViewModel layers of the Studio's
MVVM architecture. The Model layer (:mod:`atlas.studio.models`,
:mod:`atlas.studio.settings`, :mod:`atlas.studio.events`,
:mod:`atlas.studio.navigation`, :mod:`atlas.studio.workspace`) is pure
Python with **no Qt dependency**, so it can be used from tests and
headless scripts. The ViewModel layer
(:mod:`atlas.studio.controllers`) wraps Atlas subsystems via dependency
injection and duck typing.

The View layer (:mod:`atlas.studio.mainwindow`, :mod:`atlas.studio.app`,
:mod:`atlas.studio.widgets`, :mod:`atlas.studio.pages`) depends on
PySide6 but degrades gracefully — :func:`has_qt` reports whether
PySide6 is importable, and the Qt modules define placeholders that
raise :class:`ImportError` on instantiation when PySide6 is absent.
"""

from __future__ import annotations

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
from atlas.studio.events import EventRelay
from atlas.studio.models import (
    AgentStatus,
    ArtifactInfo,
    ConnectorStatus,
    EventEntry,
    ExecutionStep,
    ExecutionTimeline,
    KnowledgeDoc,
    LogEntry,
    LogLevel,
    MemoryEntry,
    NavigationCategory,
    NotificationEntry,
    PageId,
    PageInfo,
    PluginInfo,
    ProviderStatus,
    SystemMetric,
    TabInfo,
    WorkflowRun,
)
from atlas.studio.navigation import NavigationModel
from atlas.studio.settings import StudioSettings
from atlas.studio.theme import DARK_THEME, get_stylesheet
from atlas.studio.workspace import SplitOrientation, WorkspaceModel

__version__ = "1.0.0"


def has_qt() -> bool:
    """Return ``True`` if PySide6 is importable, ``False`` otherwise.

    The check imports the :mod:`PySide6.QtWidgets` submodule (rather
    than just the top-level :mod:`PySide6` package) so that the result
    is consistent with the Qt-dependent modules in this package: those
    modules only define real widget classes when ``QtWidgets`` can be
    imported. On hosts where PySide6 is installed but its platform
    plugins cannot load (e.g. missing ``libEGL``), this returns
    ``False`` and the View layer degrades to placeholders.

    The pure-Python Model and ViewModel layers always work regardless of
    this result.
    """
    try:
        from PySide6 import QtWidgets  # noqa: F401  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 — optional dependency / plugin load
        return False
    return True


__all__ = [
    "AgentController",
    "AgentStatus",
    "ArtifactController",
    "ArtifactInfo",
    "ChatController",
    "ConnectorStatus",
    "DARK_THEME",
    "EventEntry",
    "EventRelay",
    "ExecutionController",
    "ExecutionStep",
    "ExecutionTimeline",
    "KnowledgeController",
    "KnowledgeDoc",
    "LogEntry",
    "LogLevel",
    "MCPController",
    "MemoryController",
    "MemoryEntry",
    "NavigationCategory",
    "NavigationModel",
    "NotificationEntry",
    "PageId",
    "PageInfo",
    "PluginController",
    "PluginInfo",
    "ProviderController",
    "ProviderStatus",
    "SplitOrientation",
    "StudioSettings",
    "SystemController",
    "SystemMetric",
    "TabInfo",
    "WorkflowRun",
    "WorkspaceModel",
    "__version__",
    "get_stylesheet",
    "has_qt",
]
