"""Atlas Sidebar widget — real Qt navigation sidebar.

Renders the :class:`~atlas.studio.navigation.NavigationModel` as a
vertical list of pages grouped by category. Clicking a page emits
:attr:`page_requested`.
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
    from atlas.studio.navigation import NavigationModel

from atlas.app._qt import _QT_MISSING_MSG

if _HAS_QT:

    class SidebarWidget(QtWidgets.QWidget):  # type: ignore[misc, valid-type]
        """Real navigation sidebar.

        Parameters:
            navigation: The :class:`NavigationModel` to render.
            parent: Optional Qt parent.
        """

        page_requested = QtCore.Signal(str)

        def __init__(
            self,
            navigation: NavigationModel,
            parent: Any = None,
        ) -> None:
            super().__init__(parent)
            self.setObjectName("AtlasSidebar")
            self.setFixedWidth(220)
            self._navigation = navigation
            self._buttons: dict[str, QtWidgets.QPushButton] = {}
            self._build_ui()

        def _build_ui(self) -> None:
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(8, 12, 8, 12)
            layout.setSpacing(4)

            # Brand
            brand = QtWidgets.QLabel("ATLAS")
            brand.setStyleSheet(
                "font-size: 16pt; font-weight: bold; color: #6366F1; "
                "padding: 4px 8px 12px 8px;"
            )
            layout.addWidget(brand)

            # Scroll area for the page list
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            inner = QtWidgets.QWidget()
            inner_layout = QtWidgets.QVBoxLayout(inner)
            inner_layout.setContentsMargins(0, 0, 0, 0)
            inner_layout.setSpacing(2)

            current_category: str | None = None
            for page in self._navigation.pages():
                if not page.enabled:
                    continue
                if page.category.value != current_category:
                    current_category = page.category.value
                    label = QtWidgets.QLabel(current_category.upper())
                    label.setStyleSheet(
                        "color: #94A3B8; font-size: 9pt; "
                        "font-weight: bold; padding: 12px 8px 4px 8px;"
                    )
                    inner_layout.addWidget(label)

                btn = QtWidgets.QPushButton(f"  {page.title}")
                btn.setCheckable(True)
                btn.setObjectName(f"sidebar_{page.id.value}")
                btn.clicked.connect(
                    lambda checked=False, pid=page.id.value: self._on_click(pid)
                )
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 6px 12px; "
                    "border: none; border-radius: 6px; }"
                    "QPushButton:hover { background: #1E293B; }"
                    "QPushButton:checked { background: #6366F1; color: white; }"
                )
                self._buttons[page.id.value] = btn
                inner_layout.addWidget(btn)

            inner_layout.addStretch()
            scroll.setWidget(inner)
            layout.addWidget(scroll, 1)

        def _on_click(self, page_id: str) -> None:
            self.page_requested.emit(page_id)

        def set_active(self, page_id: str) -> None:
            """Highlight the button for ``page_id``."""
            for pid, btn in self._buttons.items():
                btn.setChecked(pid == page_id)

        def refresh(self) -> None:
            """Rebuild the sidebar (used when pages are added/removed)."""
            # Clear existing layout
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
            self._buttons.clear()
            self._build_ui()

else:

    class SidebarWidget:  # type: ignore[no-redef]
        """Placeholder raised when PySide6 is unavailable."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["SidebarWidget"]
