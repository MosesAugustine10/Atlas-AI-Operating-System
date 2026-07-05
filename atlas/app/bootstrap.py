"""Atlas application bootstrap — wires every controller into the Qt app.

The :class:`AtlasApp` is the single composition root for the
production application. It:

* Creates a :class:`PySide6.QtWidgets.QApplication` (when PySide6 is
  available).
* Instantiates every :class:`~atlas.studio.controllers` controller with
  the appropriate injected subsystem (Brain, ProviderManager, MCPManager,
  MemoryEngine, KnowledgeEngine, etc.).
* Builds the :class:`~atlas.app.main_window.MainWindow` and connects it
  to the controllers.
* Exposes a :meth:`run` method that enters the Qt event loop.

On headless hosts (no PySide6), :class:`AtlasApp` can still be
constructed — it just cannot call :meth:`run`. The :attr:`controllers`
dict is always available so tests can verify wiring.
"""

from __future__ import annotations

import sys
from typing import Any

from atlas.app._qt import has_qt

try:  # pragma: no cover — exercised on Qt-bearing hosts
    from PySide6 import QtWidgets  # type: ignore[import-not-found]

    _HAS_QT: bool = True
except Exception:  # noqa: BLE001 — PySide6 optional
    _HAS_QT: bool = False
    QtWidgets = None  # type: ignore[assignment]

from atlas.studio.controllers import (
    AgentController,
    ArtifactController,
    ChatController,
    ExecutionController,
    KnowledgeController,
    MCPController,
    MemoryController,
    PluginController,
    ProviderController,
    SystemController,
)


class AtlasApp:
    """The production Atlas application bootstrap.

    Parameters:
        brain: Optional Atlas Brain (or any object exposing ``run``).
        providers: Optional :class:`~atlas.providers.manager.ProviderManager`.
        mcp: Optional MCP manager.
        memory: Optional Memory engine.
        knowledge: Optional Knowledge engine.
        agents: Optional agent registry.
        artifacts: Optional artifact manager.
        system: Optional system-info source.
    """

    def __init__(
        self,
        brain: Any = None,
        providers: Any = None,
        mcp: Any = None,
        memory: Any = None,
        knowledge: Any = None,
        agents: Any = None,
        artifacts: Any = None,
        system: Any = None,
    ) -> None:
        # Build the controller dict — every page pulls from this.
        self.controllers: dict[str, Any] = {
            "chat": ChatController(
                brain=brain, providers=providers, agent_registry=agents
            ),
            "agents": AgentController(registry=agents),
            "providers": ProviderController(manager=providers),
            "memory": MemoryController(engine=memory),
            "knowledge": KnowledgeController(engine=knowledge),
            "execution": ExecutionController(brain=brain),
            "artifacts": ArtifactController(manager=artifacts),
            "mcp": MCPController(manager=mcp),
            "system": SystemController(),
            "plugins": PluginController(),
        }
        # Subsystem references (kept for later phases that need direct access)
        self.brain = brain
        self.providers = providers
        self.mcp = mcp
        self.memory = memory
        self.knowledge = knowledge
        self.agents = agents
        self.artifacts = artifacts
        self.system = system
        # Qt objects (built lazily)
        self._qt_app: Any = None
        self._main_window: Any = None

    # ------------------------------------------------------------------
    # Controller access
    # ------------------------------------------------------------------

    def controller(self, name: str) -> Any:
        """Return the controller registered under ``name``."""
        return self.controllers[name]

    def controller_names(self) -> list[str]:
        """Return the sorted list of registered controller names."""
        return sorted(self.controllers)

    # ------------------------------------------------------------------
    # Qt application lifecycle
    # ------------------------------------------------------------------

    @property
    def qt_app(self) -> Any:
        """Return the :class:`QApplication` (creating it if needed)."""
        if not _HAS_QT:
            return None
        if self._qt_app is None:
            self._qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
                sys.argv
            )
        return self._qt_app

    @property
    def main_window(self) -> Any:
        """Return the :class:`MainWindow` (creating it if needed)."""
        if not _HAS_QT:
            return None
        if self._main_window is None:
            from atlas.app.main_window import MainWindow

            self._main_window = MainWindow(app=self)
        return self._main_window

    def show(self) -> Any:
        """Show the main window. Returns the window."""
        if not _HAS_QT:
            raise RuntimeError("PySide6 is not available — cannot show window")
        win = self.main_window
        win.show()
        return win

    def run(self) -> int:
        """Enter the Qt event loop. Returns the exit code."""
        if not _HAS_QT:
            raise RuntimeError("PySide6 is not available — cannot run Qt event loop")
        app = self.qt_app
        win = self.show()
        _ = win  # keep reference
        return int(app.exec())

    # ------------------------------------------------------------------
    # Headless introspection
    # ------------------------------------------------------------------

    def is_qt_available(self) -> bool:
        """Return ``True`` if PySide6 is available."""
        return has_qt()

    def status(self) -> dict[str, Any]:
        """Return a dict describing the app's wiring state."""
        return {
            "qt_available": self.is_qt_available(),
            "controllers": self.controller_names(),
            "brain_wired": self.brain is not None,
            "providers_wired": self.providers is not None,
            "mcp_wired": self.mcp is not None,
            "memory_wired": self.memory is not None,
            "knowledge_wired": self.knowledge is not None,
            "agents_wired": self.agents is not None,
            "artifacts_wired": self.artifacts is not None,
        }


__all__ = ["AtlasApp"]
