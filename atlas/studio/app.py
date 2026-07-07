"""Studio application bootstrap — Qt entry point with graceful degradation.

This module tries to import :mod:`PySide6`. When PySide6 is available a
minimal :class:`StudioApp` (wrapping a :class:`QApplication`) is
defined. When PySide6 is absent a placeholder :class:`StudioApp` is
defined instead, which raises :class:`ImportError` with a helpful
message on instantiation.

Importing this module never fails — tests and headless tools can import
it on any host.
"""

from __future__ import annotations

import sys
from typing import Any

try:  # pragma: no cover — exercised on Qt-bearing hosts
    from PySide6 import QtWidgets  # type: ignore[import-not-found]

    _HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    _HAS_QT = False
    QtWidgets = None  # type: ignore[assignment]


_QT_MISSING_MSG = (
    "PySide6 is not available. Install it with `pip install PySide6` to use "
    "atlas.studio.app.StudioApp. The pure-Python Model and ViewModel layers "
    "of atlas.studio work without PySide6."
)


if _HAS_QT:

    class StudioApp:
        """Thin wrapper around :class:`PySide6.QtWidgets.QApplication`.

        Parameters:
            argv: Optional command-line argument list. Defaults to
                :data:`sys.argv`.
            settings: Optional :class:`StudioSettings` used to pick the
                theme stylesheet.
        """

        def __init__(
            self,
            argv: list[str] | None = None,
            settings: Any = None,
        ) -> None:
            self.settings = settings
            existing = QtWidgets.QApplication.instance()
            self._qt_app = existing or QtWidgets.QApplication(argv or sys.argv)
            if settings is not None:
                from atlas.studio.theme import get_stylesheet

                theme = getattr(settings, "get", lambda *_: "dark")("theme", "dark")
                self._qt_app.setStyleSheet(get_stylesheet(theme))

        def run(self) -> int:
            """Show the main window and enter the Qt event loop."""
            from atlas.studio.mainwindow import MainWindow

            window = MainWindow(settings=self.settings)
            window.show()
            return self._qt_app.exec()

        @property
        def qt_application(self) -> QtWidgets.QApplication:
            """Return the underlying :class:`QApplication` instance."""
            return self._qt_app

else:

    class StudioApp:  # type: ignore[no-redef]
        """Placeholder used when PySide6 is not installed.

        Instantiating this class raises :class:`ImportError` so callers
        get a clear, actionable message. The class itself is still
        importable for introspection and testing.
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


def run(argv: list[str] | None = None) -> int:
    """Convenience entry point — create a :class:`StudioApp` and run it.

    Returns the Qt exit code, or ``1`` if PySide6 is unavailable.
    """
    try:
        app = StudioApp(argv=argv)
    except ImportError:
        print(_QT_MISSING_MSG)  # noqa: T201 — CLI feedback
        return 1
    return app.run()


__all__ = ["StudioApp", "run"]
