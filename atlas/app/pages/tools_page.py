"""Atlas Tools page — real Qt info page.

View installed tools.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover — exercised on Qt-bearing hosts
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

    _HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    _HAS_QT: bool = False
    QtCore = None  # type: ignore[assignment]
    QtGui = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]

from atlas.app._qt import _QT_MISSING_MSG

if _HAS_QT:

    class ToolsPage(QtWidgets.QWidget):  # type: ignore[misc, valid-type]
        """Real Tools page."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self.setObjectName("AtlasToolsPage")
            self._build_ui()

        def _build_ui(self) -> None:
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)

            title = QtWidgets.QLabel("Tools")
            title.setStyleSheet("font-size: 18pt; font-weight: bold;")
            layout.addWidget(title)

            self.content = QtWidgets.QListWidget()
            layout.addWidget(self.content, 1)

            self.status_label = QtWidgets.QLabel("View installed tools")
            self.status_label.setStyleSheet("color: #94A3B8;")
            layout.addWidget(self.status_label)

        def refresh(self) -> None:
            """Refresh the page contents."""
            self.content.clear()

else:

    class ToolsPage:  # type: ignore[no-redef]
        """Placeholder raised when PySide6 is unavailable."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["ToolsPage"]
