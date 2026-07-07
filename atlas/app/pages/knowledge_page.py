"""Atlas Knowledge page — real Qt page using the KnowledgeController controller.

Browse the knowledge base.
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
    from atlas.studio.controllers.knowledge_controller import KnowledgeController

from atlas.app._qt import _QT_MISSING_MSG

if _HAS_QT:

    class KnowledgePage(QtWidgets.QWidget):  # type: ignore[misc, valid-type]
        """Real Knowledge page.

        Parameters:
            controller: :class:`KnowledgeController` instance.
            parent: Optional Qt parent.
        """

        def __init__(self, controller: KnowledgeController, parent: Any = None) -> None:
            super().__init__(parent)
            self.setObjectName("AtlasKnowledgePage")
            self.controller = controller
            self._build_ui()
            self.refresh()

        def _build_ui(self) -> None:
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)

            header = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel("Knowledge")
            title.setStyleSheet("font-size: 18pt; font-weight: bold;")
            header.addWidget(title)
            header.addStretch()

            self.search_edit = QtWidgets.QLineEdit()
            self.search_edit.setPlaceholderText("Search…")
            self.search_edit.textChanged.connect(self._on_search)
            header.addWidget(self.search_edit)

            self.refresh_button = QtWidgets.QPushButton("Refresh")
            self.refresh_button.clicked.connect(self._on_refresh)
            header.addWidget(self.refresh_button)

            layout.addLayout(header)

            self.list_widget = QtWidgets.QListWidget()
            self.list_widget.setAlternatingRowColors(True)
            layout.addWidget(self.list_widget, 1)

            self.status_label = QtWidgets.QLabel("")
            self.status_label.setStyleSheet("color: #94A3B8;")
            layout.addWidget(self.status_label)

        def _on_search(self, text: str) -> None:
            self.refresh()

        def _on_refresh(self) -> None:
            if hasattr(self.controller, "refresh"):
                try:
                    self.controller.refresh()
                except Exception:
                    pass
            self.refresh()

        def refresh(self) -> None:
            """Refresh the list from the controller."""
            self.list_widget.clear()
            query = self.search_edit.text().strip()
            items = self._fetch_items(query)
            for item in items:
                label = self._item_label(item)
                self.list_widget.addItem(label)
            self.status_label.setText(f"{len(items)} item(s)")

        def _fetch_items(self, query: str) -> list[Any]:
            list_method = getattr(self.controller, "documents", None)
            if list_method is None:
                return []
            try:
                if query and hasattr(self.controller, "search"):
                    return list(self.controller.search(query))
                return list(list_method())
            except Exception:  # noqa: BLE001
                return []

        @staticmethod
        def _item_label(item: Any) -> str:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                return str(item.get("title", item))
            return str(getattr(item, "title", item))

else:

    class KnowledgePage:  # type: ignore[no-redef]
        """Placeholder raised when PySide6 is unavailable."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["KnowledgePage"]
