"""Studio sidebar widget stub — gracefully degrades when PySide6 is absent.

The :class:`Sidebar` widget renders the navigation tree. When PySide6 is
available it is a minimal :class:`QFrame` subclass; otherwise it is a
placeholder that raises :class:`ImportError` on instantiation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:  # pragma: no cover — exercised on Qt-bearing hosts
    from PySide6 import QtWidgets  # type: ignore[import-not-found]

    _HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    _HAS_QT = False
    QtWidgets = None  # type: ignore[assignment]


if TYPE_CHECKING:
    from atlas.studio.navigation import NavigationModel


_QT_MISSING_MSG = (
    "PySide6 is not available. Install it with `pip install PySide6` to use "
    "atlas.studio.widgets.sidebar.Sidebar."
)


if _HAS_QT:

    class Sidebar(QtWidgets.QFrame):  # type: ignore[misc, valid-type]
        """Navigation sidebar showing every Studio page."""

        def __init__(
            self, navigation: NavigationModel | None = None, parent: Any = None
        ) -> None:
            super().__init__(parent)
            self.navigation = navigation
            self.setObjectName("Sidebar")
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(8, 12, 8, 12)
            layout.setSpacing(4)
            header = QtWidgets.QLabel("NAVIGATION", self)
            header.setObjectName("SidebarHeader")
            layout.addWidget(header)
            layout.addStretch(1)

else:

    class Sidebar:  # type: ignore[no-redef]
        """Placeholder used when PySide6 is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["Sidebar"]
