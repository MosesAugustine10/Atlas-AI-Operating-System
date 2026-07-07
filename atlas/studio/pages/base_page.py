"""Studio base page stub — gracefully degrades when PySide6 is absent.

All concrete Studio pages subclass :class:`BasePage`. When PySide6 is
available it is a minimal :class:`QWidget` subclass; otherwise it is a
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
    from atlas.studio.models.studio_models import PageInfo


_QT_MISSING_MSG = (
    "PySide6 is not available. Install it with `pip install PySide6` to use "
    "atlas.studio.pages.base_page.BasePage."
)


if _HAS_QT:

    class BasePage(QtWidgets.QWidget):  # type: ignore[misc, valid-type]
        """Common base for every Studio page widget.

        Parameters:
            page_info: The :class:`PageInfo` describing this page.
        """

        def __init__(
            self, page_info: PageInfo | None = None, parent: Any = None
        ) -> None:
            super().__init__(parent)
            self.page_info = page_info
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            if page_info is not None:
                title = QtWidgets.QLabel(page_info.title, self)
                title.setObjectName("PageTitle")
                layout.addWidget(title)

else:

    class BasePage:  # type: ignore[no-redef]
        """Placeholder used when PySide6 is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["BasePage"]
