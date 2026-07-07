"""Studio main window — Qt entry point with graceful degradation.

This module tries to import :mod:`PySide6`. When PySide6 is available a
minimal :class:`MainWindow` subclassing
:class:`PySide6.QtWidgets.QMainWindow` is defined. When PySide6 is
absent a placeholder :class:`MainWindow` is defined instead, which
raises :class:`ImportError` with a helpful message on instantiation.

Either way, importing this module never fails — so tests and headless
tools can import it on any host.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:  # pragma: no cover — exercised on Qt-bearing hosts
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

    _HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    _HAS_QT = False
    QtCore = None  # type: ignore[assignment]
    QtGui = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]


if TYPE_CHECKING:
    from atlas.studio.navigation import NavigationModel
    from atlas.studio.settings import StudioSettings
    from atlas.studio.workspace import WorkspaceModel


_QT_MISSING_MSG = (
    "PySide6 is not available. Install it with `pip install PySide6` to use "
    "atlas.studio.mainwindow.MainWindow. The pure-Python Model and ViewModel "
    "layers of atlas.studio work without PySide6."
)


if _HAS_QT:

    class MainWindow(QtWidgets.QMainWindow):  # type: ignore[misc, valid-type]
        """Primary Studio window.

        This is a minimal stub that wires up the central widget, sidebars
        and status bar. Concrete page widgets are added by the
        application bootstrap.
        """

        def __init__(
            self,
            settings: StudioSettings | None = None,
            navigation: NavigationModel | None = None,
            workspace: WorkspaceModel | None = None,
            controllers: dict[str, Any] | None = None,
        ) -> None:
            super().__init__()
            self.settings = settings
            self.navigation = navigation
            self.workspace = workspace
            self.controllers = controllers or {}
            self.setWindowTitle("Atlas Studio")
            self.resize(1600, 900)
            central = QtWidgets.QWidget(self)
            self.setCentralWidget(central)

else:

    class MainWindow:  # type: ignore[no-redef]
        """Placeholder used when PySide6 is not installed.

        Instantiating this class raises :class:`ImportError` so callers
        get a clear, actionable message. The class itself is still
        importable for introspection and testing.
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["MainWindow"]
