"""Studio theme — Qt stylesheet strings (no Qt import required to define).

This module holds the dark-theme Qt stylesheet as a plain string and a
:func:`get_stylesheet` accessor. Defining the stylesheet as a string
does not require PySide6, so the module is safe to import from headless
code and tests.
"""

from __future__ import annotations

#: A comprehensive dark stylesheet for the Studio shell.
#:
#: The stylesheet targets Qt widget class names and object names used
#: throughout the Studio UI. It is intentionally self-contained (no
#: external resource references) so it can be applied with a single
#: ``app.setStyleSheet(...)`` call.
DARK_THEME: str = """
/* ============================================================
 * Atlas Studio — Dark theme
 * ============================================================ */

QWidget {
    background-color: #0f1115;
    color: #e4e6eb;
    font-family: "Inter", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 14px;
}

QMainWindow, QDialog {
    background-color: #0f1115;
}

/* ---------- Sidebar ---------- */
QFrame#Sidebar {
    background-color: #15181f;
    border-right: 1px solid #232732;
}

QLabel#SidebarHeader {
    color: #8b94a7;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 8px 16px 4px 16px;
}

QPushButton#NavButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 9px 14px;
    color: #c2c8d4;
    font-weight: 500;
}

QPushButton#NavButton:hover {
    background-color: #1e232e;
    color: #e4e6eb;
}

QPushButton#NavButton:checked {
    background-color: #2b6cb0;
    color: #ffffff;
}

/* ---------- Content area ---------- */
QFrame#ContentArea {
    background-color: #0f1115;
}

QLabel#PageTitle {
    font-size: 20px;
    font-weight: 700;
    color: #f3f4f6;
}

QLabel#PageSubtitle {
    font-size: 13px;
    color: #8b94a7;
}

/* ---------- Cards ---------- */
QFrame#Card {
    background-color: #15181f;
    border: 1px solid #232732;
    border-radius: 10px;
}

QLabel#CardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #e4e6eb;
}

QLabel#CardValue {
    font-size: 22px;
    font-weight: 700;
    color: #f3f4f6;
}

/* ---------- Tabs ---------- */
QTabWidget::pane {
    border: 1px solid #232732;
    border-radius: 8px;
    top: -1px;
    background-color: #0f1115;
}

QTabBar::tab {
    background-color: #15181f;
    color: #8b94a7;
    border: 1px solid #232732;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 7px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0f1115;
    color: #e4e6eb;
    border-bottom: 2px solid #2b6cb0;
}

QTabBar::tab:hover:!selected {
    background-color: #1e232e;
    color: #c2c8d4;
}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #15181f;
    border: 1px solid #232732;
    border-radius: 6px;
    padding: 7px 9px;
    color: #e4e6eb;
    selection-background-color: #2b6cb0;
    selection-color: #ffffff;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2b6cb0;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #15181f;
    border: 1px solid #232732;
    selection-background-color: #2b6cb0;
    selection-color: #ffffff;
    outline: none;
}

/* ---------- Buttons ---------- */
QPushButton {
    background-color: #1e232e;
    color: #e4e6eb;
    border: 1px solid #2a3040;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #262c39;
    border-color: #3a4256;
}

QPushButton:pressed {
    background-color: #15181f;
}

QPushButton:disabled {
    color: #5b6477;
    background-color: #15181f;
    border-color: #1e232e;
}

QPushButton#Primary {
    background-color: #2b6cb0;
    border-color: #2b6cb0;
    color: #ffffff;
}

QPushButton#Primary:hover {
    background-color: #3182ce;
    border-color: #3182ce;
}

QPushButton#Danger {
    background-color: #c53030;
    border-color: #c53030;
    color: #ffffff;
}

QPushButton#Danger:hover {
    background-color: #e53e3e;
    border-color: #e53e3e;
}

/* ---------- Lists / tables ---------- */
QListWidget, QTreeWidget, QTableWidget, QTableView, QTreeView {
    background-color: #15181f;
    border: 1px solid #232732;
    border-radius: 6px;
    alternate-background-color: #181c25;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #2b6cb0;
    color: #ffffff;
}

QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {
    background-color: #1e232e;
}

QHeaderView::section {
    background-color: #181c25;
    color: #8b94a7;
    border: none;
    border-right: 1px solid #232732;
    padding: 7px 9px;
    font-weight: 600;
}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #2a3040;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3a4256;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #2a3040;
    border-radius: 5px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3a4256;
}

QScrollBar::add-line, QScrollBar::sub-line {
    background: none;
    border: none;
    height: 0;
    width: 0;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}

/* ---------- Status bar ---------- */
QStatusBar {
    background-color: #15181f;
    border-top: 1px solid #232732;
    color: #8b94a7;
}

QStatusBar QLabel {
    color: #8b94a7;
}

/* ---------- Tooltips ---------- */
QToolTip {
    background-color: #1e232e;
    color: #e4e6eb;
    border: 1px solid #2a3040;
    border-radius: 4px;
    padding: 5px 8px;
}

/* ---------- Progress ---------- */
QProgressBar {
    background-color: #15181f;
    border: 1px solid #232732;
    border-radius: 6px;
    text-align: center;
    color: #e4e6eb;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #2b6cb0;
    border-radius: 5px;
}

/* ---------- Splitter ---------- */
QSplitter::handle {
    background-color: #232732;
}

QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* ---------- Group boxes ---------- */
QGroupBox {
    border: 1px solid #232732;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
    color: #c2c8d4;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 5px;
    color: #8b94a7;
}

/* ---------- Checkboxes / radios ---------- */
QCheckBox, QRadioButton {
    color: #c2c8d4;
    spacing: 7px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #2a3040;
    background-color: #15181f;
    border-radius: 3px;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #2b6cb0;
    border-color: #2b6cb0;
}
"""

#: A lighter companion theme (kept compact; Studio defaults to dark).
LIGHT_THEME: str = """
QWidget {
    background-color: #ffffff;
    color: #1a202c;
    font-family: "Inter", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 14px;
}

QPushButton {
    background-color: #edf2f7;
    color: #1a202c;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    padding: 7px 14px;
}

QPushButton#Primary {
    background-color: #2b6cb0;
    border-color: #2b6cb0;
    color: #ffffff;
}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    padding: 7px 9px;
    color: #1a202c;
}

QListWidget, QTreeWidget, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #2b6cb0;
    color: #ffffff;
}
"""


def get_stylesheet(theme: str = "dark") -> str:
    """Return the stylesheet for ``theme`` (``"dark"`` or ``"light"``).

    Unknown themes fall back to the dark stylesheet.
    """
    if theme.lower() == "light":
        return LIGHT_THEME
    return DARK_THEME


__all__ = ["DARK_THEME", "LIGHT_THEME", "get_stylesheet"]
