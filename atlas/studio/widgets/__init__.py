"""Studio widgets package — Qt widget stubs with graceful degradation.

Each widget module tries to import :mod:`PySide6` and defines either a
real (minimal) widget or a placeholder that raises :class:`ImportError`
on instantiation. Importing this package never fails.
"""

from __future__ import annotations

try:  # pragma: no cover — exercised on Qt-bearing hosts
    import PySide6  # noqa: F401  # type: ignore[import-not-found]

    HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    HAS_QT = False


__all__ = ["HAS_QT"]
