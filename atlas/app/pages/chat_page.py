"""Atlas Chat page — real Qt chat interface using :class:`ChatController`.

Renders the conversation history, an input box, and provider/agent
selectors. The page is fully wired to :class:`ChatController` — no
placeholders.
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
    from atlas.studio.controllers.chat_controller import ChatController

from atlas.app._qt import _QT_MISSING_MSG

if _HAS_QT:

    class ChatPage(QtWidgets.QWidget):  # type: ignore[misc, valid-type]
        """Real chat page.

        Parameters:
            controller: :class:`ChatController` instance.
            parent: Optional Qt parent.
        """

        def __init__(self, controller: ChatController, parent: Any = None) -> None:
            super().__init__(parent)
            self.setObjectName("AtlasChatPage")
            self.controller = controller
            self._build_ui()
            self.refresh()

        def _build_ui(self) -> None:
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)

            # Header
            header = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel("Chat")
            title.setStyleSheet("font-size: 18pt; font-weight: bold;")
            header.addWidget(title)
            header.addStretch()

            # Provider selector
            self.provider_combo = QtWidgets.QComboBox()
            self.provider_combo.addItem("(default)", None)
            self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
            header.addWidget(QtWidgets.QLabel("Provider:"))
            header.addWidget(self.provider_combo)

            # Agent selector
            self.agent_combo = QtWidgets.QComboBox()
            self.agent_combo.addItem("(none)", None)
            self.agent_combo.currentIndexChanged.connect(self._on_agent_changed)
            header.addWidget(QtWidgets.QLabel("Agent:"))
            header.addWidget(self.agent_combo)

            self.clear_button = QtWidgets.QPushButton("Clear")
            self.clear_button.clicked.connect(self._on_clear)
            header.addWidget(self.clear_button)

            layout.addLayout(header)

            # Conversation view
            self.conversation = QtWidgets.QListWidget()
            self.conversation.setAlternatingRowColors(True)
            layout.addWidget(self.conversation, 1)

            # Input area
            input_row = QtWidgets.QHBoxLayout()
            self.input_edit = QtWidgets.QLineEdit()
            self.input_edit.setPlaceholderText("Type a message…")
            self.input_edit.returnPressed.connect(self._on_send)
            input_row.addWidget(self.input_edit, 1)

            self.send_button = QtWidgets.QPushButton("Send")
            self.send_button.clicked.connect(self._on_send)
            input_row.addWidget(self.send_button)

            layout.addLayout(input_row)

        def _on_send(self) -> None:
            text = self.input_edit.text().strip()
            if not text:
                return
            self.input_edit.clear()
            self.send_button.setEnabled(False)
            try:
                self.controller.send(text)
            finally:
                self.send_button.setEnabled(True)
            self.refresh()

        def _on_clear(self) -> None:
            self.controller.clear()
            self.refresh()

        def _on_provider_changed(self, index: int) -> None:
            name = self.provider_combo.itemData(index)
            self.controller.set_provider(name)

        def _on_agent_changed(self, index: int) -> None:
            name = self.agent_combo.itemData(index)
            self.controller.set_agent(name)

        def focus_input(self) -> None:
            """Focus the input edit (used by the main window's search shortcut)."""
            self.input_edit.setFocus()

        def refresh(self) -> None:
            """Refresh the conversation view from the controller."""
            self.conversation.clear()
            for msg in self.controller.messages:
                role = msg.get("role", "?").title()
                content = msg.get("content", "")
                self.conversation.addItem(f"[{role}] {content}")
            # Scroll to bottom
            self.conversation.scrollToBottom()
            # Refresh provider/agent combos
            self._refresh_combos()

        def _refresh_combos(self) -> None:
            # Provider / agent lists come from the underlying subsystems
            # via the controller's _providers / _agents attributes.
            providers = self._list_provider_names()
            agents = self._list_agent_names()
            current_provider = self.controller.provider
            current_agent = self.controller.agent

            self.provider_combo.clear()
            self.provider_combo.addItem("(default)", None)
            for p in providers:
                self.provider_combo.addItem(p, p)
            if current_provider:
                idx = self.provider_combo.findData(current_provider)
                if idx >= 0:
                    self.provider_combo.setCurrentIndex(idx)

            self.agent_combo.clear()
            self.agent_combo.addItem("(none)", None)
            for a in agents:
                self.agent_combo.addItem(a, a)
            if current_agent:
                idx = self.agent_combo.findData(current_agent)
                if idx >= 0:
                    self.agent_combo.setCurrentIndex(idx)

        def _list_provider_names(self) -> list[str]:
            mgr = getattr(self.controller, "_providers", None)
            if mgr is None:
                return []
            # Try common provider-manager APIs
            for attr in ("available_models", "models", "list_models"):
                method = getattr(mgr, attr, None)
                if callable(method):
                    try:
                        result = method()
                        return [str(r) if not isinstance(r, str) else r for r in result]
                    except Exception:  # noqa: BLE001
                        continue
            # Fall back to a names attribute
            names = getattr(mgr, "names", None)
            if callable(names):
                try:
                    return [str(n) for n in names()]
                except Exception:  # noqa: BLE001
                    pass
            return []

        def _list_agent_names(self) -> list[str]:
            registry = getattr(self.controller, "_agents", None)
            if registry is None:
                return []
            # Dict-like registry
            if hasattr(registry, "keys"):
                try:
                    return [str(k) for k in registry.keys()]
                except Exception:  # noqa: BLE001
                    pass
            # List-like registry
            if hasattr(registry, "__iter__"):
                try:
                    return [str(getattr(a, "name", a)) for a in registry]
                except Exception:  # noqa: BLE001
                    pass
            return []

else:

    class ChatPage:  # type: ignore[no-redef]
        """Placeholder raised when PySide6 is unavailable."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(_QT_MISSING_MSG)


__all__ = ["ChatPage"]
