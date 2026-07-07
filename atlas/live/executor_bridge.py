"""Executor bridge — dispatch execution tasks through the MCP Manager.

The :class:`MCPExecutorBridge` sits between the :class:`ExecutionExecutor`
and the :class:`MCPManager`. Instead of using placeholder actions, the
bridge routes each task's capability to the appropriate MCP connector.

Capability → connector mapping:

* ``research``          → Browser MCP (``browser.navigate``)
* ``generate_code``     → Ollama / OpenRouter MCP (``ollama.generate``)
* ``generate_assets``   → Blender MCP (``blender.render``)
* ``run_tests``         → Filesystem MCP (``file.read``) + Windows MCP
* ``git_commit``        → GitHub MCP (``git.commit``)
* ``deploy``            → Windows MCP (``windows.shell``)
* ``file.read``         → Filesystem MCP
* ``file.write``        → Filesystem MCP
* ``browser.navigate``  → Browser MCP
* ``playwright.*``      → Playwright MCP

The bridge is **dependency-injected**: it accepts an MCPManager and
delegates all execution to it. If the manager is not available, the
bridge falls back to a deterministic placeholder.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MCPExecutorBridge:
    """Bridges execution tasks to MCP connectors.

    Parameters:
        mcp_manager: The :class:`MCPManager` to dispatch through. If
            ``None``, the bridge returns deterministic placeholders.
    """

    #: Mapping of task capability → (connector_name, mcp_capability).
    CAPABILITY_MAP: dict[str, tuple[str, str]] = {
        "research": ("browser", "browser.navigate"),
        "generate_code": ("ollama", "ollama.generate"),
        "generate": ("ollama", "ollama.generate"),
        "generate_assets": ("blender", "blender.render"),
        "run_tests": ("filesystem", "file.read"),
        "git_commit": ("github", "git.commit"),
        "git.push": ("github", "git.push"),
        "git.status": ("github", "git.status"),
        "deploy": ("windows", "windows.shell"),
        "file.read": ("filesystem", "file.read"),
        "file.write": ("filesystem", "file.write"),
        "file.list": ("filesystem", "file.list"),
        "file.delete": ("filesystem", "file.delete"),
        "browser.navigate": ("browser", "browser.navigate"),
        "browser.html": ("browser", "browser.html"),
        "browser.download": ("browser", "browser.download"),
        "blender.render": ("blender", "blender.render"),
        "blender.script": ("blender", "blender.script"),
        "blender.scene.new": ("blender", "blender.scene.new"),
        "windows.shell": ("windows", "windows.shell"),
        "windows.powershell": ("windows", "windows.powershell"),
        "playwright.launch": ("playwright", "playwright.launch"),
        "playwright.goto": ("playwright", "playwright.goto"),
        "playwright.screenshot": ("playwright", "playwright.screenshot"),
    }

    def __init__(self, mcp_manager: Any = None) -> None:
        self.mcp_manager = mcp_manager
        self.logger = get_logger("live.executor_bridge")
        self._session_id: str | None = None

    def connect(self) -> None:
        """Open a session with the MCP manager (if available)."""
        if self.mcp_manager is None:
            return
        # Open sessions for each connector we'll use.
        for connector_name in {c for c, _ in self.CAPABILITY_MAP.values()}:
            if self.mcp_manager.registry.contains(connector_name):
                try:
                    self.mcp_manager.open_session(
                        connector_name,
                        permissions=["read", "write", "execute"],
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning(
                        "Failed to open session for %s: %s", connector_name, exc
                    )

    def disconnect(self) -> None:
        """Close all sessions."""
        if self.mcp_manager is None:
            return
        for session in self.mcp_manager.list_sessions():
            self.mcp_manager.close_session(session.id)

    def execute(self, capability: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute ``capability`` with ``params`` via the MCP manager.

        Returns a dict with at least ``success`` and either ``output``
        or ``error``.
        """
        if self.mcp_manager is None:
            return self._placeholder(capability, params)

        mapping = self.CAPABILITY_MAP.get(capability)
        if mapping is None:
            # Try direct capability match.
            return self._execute_direct(capability, params)

        connector_name, mcp_capability = mapping
        if not self.mcp_manager.registry.contains(connector_name):
            return self._placeholder(capability, params)

        # Build MCP params from the task params.
        mcp_params = self._build_params(capability, mcp_capability, params)

        try:
            session = self.mcp_manager.open_session(
                connector_name,
                permissions=["read", "write", "execute"],
            )
            try:
                resp = self.mcp_manager.execute_capability(
                    mcp_capability,
                    mcp_params,
                    connector=connector_name,
                    session_id=session.id,
                )
                if resp.success:
                    return {
                        "success": True,
                        "output": resp.output,
                        "connector": connector_name,
                    }
                return {
                    "success": False,
                    "error": resp.error or "unknown error",
                    "connector": connector_name,
                }
            finally:
                self.mcp_manager.close_session(session.id)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "MCP execute failed for %s/%s: %s",
                connector_name,
                mcp_capability,
                exc,
            )
            return {"success": False, "error": str(exc), "connector": connector_name}

    def available_connectors(self) -> list[str]:
        """Return the names of available MCP connectors."""
        if self.mcp_manager is None:
            return []
        return self.mcp_manager.connector_names()

    def can_execute(self, capability: str) -> bool:
        """Return ``True`` if ``capability`` can be dispatched via MCP."""
        if self.mcp_manager is None:
            return False
        mapping = self.CAPABILITY_MAP.get(capability)
        if mapping is None:
            return False
        connector_name, _ = mapping
        return self.mcp_manager.registry.contains(connector_name)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_direct(
        self, capability: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Try to execute ``capability`` directly against any connector."""
        if self.mcp_manager is None:
            return self._placeholder(capability, params)
        connectors = self.mcp_manager.find_by_capability(capability)
        if not connectors:
            return self._placeholder(capability, params)
        connector = connectors[0]
        try:
            session = self.mcp_manager.open_session(
                connector.name,
                permissions=["read", "write", "execute"],
            )
            try:
                resp = self.mcp_manager.execute_capability(
                    capability,
                    params,
                    connector=connector.name,
                    session_id=session.id,
                )
                if resp.success:
                    return {
                        "success": True,
                        "output": resp.output,
                        "connector": connector.name,
                    }
                return {
                    "success": False,
                    "error": resp.error or "error",
                    "connector": connector.name,
                }
            finally:
                self.mcp_manager.close_session(session.id)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc), "connector": connector.name}

    def _build_params(
        self,
        task_capability: str,
        mcp_capability: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Build MCP params from task params based on the capability."""
        if mcp_capability == "browser.navigate":
            return {
                "url": params.get("url", params.get("topic", "https://example.com"))
            }
        if mcp_capability == "ollama.generate":
            return {
                "prompt": params.get("prompt", params.get("goal", "generate code")),
                "model": params.get("model", "llama3"),
            }
        if mcp_capability == "blender.render":
            return {"frame": params.get("frame", 1)}
        if mcp_capability == "file.read":
            return {"path": params.get("path", "/tmp/test.txt")}
        if mcp_capability == "file.write":
            return {
                "path": params.get("path", "/tmp/output.txt"),
                "content": params.get("content", ""),
            }
        if mcp_capability == "git.commit":
            return {
                "path": params.get("path", params.get("repo", ".")),
                "message": params.get("message", "auto-commit"),
            }
        if mcp_capability == "windows.shell":
            return {"command": params.get("command", "echo done")}
        if mcp_capability == "playwright.goto":
            return {"url": params.get("url", "https://example.com")}
        if mcp_capability == "playwright.screenshot":
            return {}
        return dict(params)

    @staticmethod
    def _placeholder(capability: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return a deterministic placeholder when MCP is not available."""
        return {
            "success": True,
            "output": {
                "capability": capability,
                "params": dict(params),
                "note": "MCP manager not available — placeholder result",
            },
            "connector": "placeholder",
        }


__all__ = ["MCPExecutorBridge"]
