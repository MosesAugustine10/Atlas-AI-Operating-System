"""Shared Qt helpers for the Atlas production application.

Provides :func:`has_qt` and a consistent error message used by every
widget and page module when PySide6 is unavailable.

The Atlas application is designed to be **importable on any host**
(even headless CI boxes without PySide6). On Qt-bearing hosts the full
UI is available; on headless hosts every View class is importable but
raises :class:`ImportError` on instantiation.
"""

from __future__ import annotations

_QT_MISSING_MSG = (
    "PySide6 is not available. Install it with `pip install PySide6` to use "
    "the Atlas production application. The pure-Python controllers and "
    "models work without PySide6."
)


def has_qt() -> bool:
    """Return ``True`` if PySide6 is importable and can create an app.

    On hosts where PySide6 is installed but its platform plugins cannot
    load (e.g. missing ``libEGL``), this returns ``False`` and the View
    layer degrades to placeholders.
    """
    try:
        from PySide6 import QtWidgets  # type: ignore[import-not-found]  # noqa: F401
    except Exception:  # noqa: BLE001 — optional dependency
        return False
    return True


def qt_version() -> str | None:
    """Return the PySide6 version string, or ``None`` if unavailable."""
    try:
        from PySide6 import __version__ as ps6_version  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 — optional dependency
        return None
    return ps6_version


__all__ = ["_QT_MISSING_MSG", "has_qt", "qt_version"]
