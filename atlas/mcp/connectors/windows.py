"""Windows MCP connector — real implementation.

Provides Windows OS automation via PowerShell and CMD subprocesses. On
non-Windows platforms, shell commands still work (via the default
shell); PowerShell-specific commands degrade gracefully.

Capabilities:

* ``windows.shell`` — run a CMD / shell command.
* ``windows.powershell`` — run a PowerShell command.
* ``windows.env.get`` — get an environment variable.
* ``windows.env.set`` — set an environment variable (in-process).
* ``windows.process.list`` — list running processes.
* ``windows.process.kill`` — kill a process by PID or name.
* ``windows.app.launch`` — launch an application.
* ``windows.clipboard`` — get / set the clipboard.
"""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import UTC, datetime
from typing import Any

from atlas.mcp.base import BaseConnector
from atlas.mcp.connector_config import get_connector_config
from atlas.mcp.models import (
    HealthLevel,
    MCPCapability,
    MCPHealth,
    MCPRequest,
    MCPStatus,
    MCPTransport,
    TransportKind,
)
from atlas.mcp.permissions import PermissionLevel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WindowsConnector(BaseConnector):
    """Real Windows OS MCP connector.

    Parameters:
        powershell: PowerShell executable name (``powershell`` or ``pwsh``).
        shell_timeout: Subprocess timeout in seconds.
    """

    def __init__(
        self,
        powershell: str | None = None,
        shell_timeout: int | None = None,
    ) -> None:
        cfg = get_connector_config("windows")
        self.powershell = powershell or cfg.get("powershell", "powershell")
        self.shell_timeout = (
            shell_timeout
            if shell_timeout is not None
            else cfg.get("shell_timeout_seconds", 30)
        )
        self._is_windows = platform.system() == "Windows"
        self._has_powershell = self._check_powershell()
        super().__init__(
            name="windows",
            description=(
                "Windows OS automation (shell, PowerShell, env vars, "
                "processes, app launch, clipboard)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="windows.shell",
                    description="Run a CMD / shell command",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.powershell",
                    description="Run a PowerShell command",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.env.get",
                    description="Get environment variable",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="windows.env.set",
                    description="Set environment variable",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="windows.process.list",
                    description="List running processes",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="windows.process.kill",
                    description="Kill a process",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.app.launch",
                    description="Launch an application",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="windows.clipboard",
                    description="Get / set clipboard",
                    permissions=("read", "write"),
                ),
            ),
            metadata={
                "is_windows": self._is_windows,
                "has_powershell": self._has_powershell,
                "shell_timeout": self.shell_timeout,
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _check_powershell(self) -> bool:
        """Return ``True`` if PowerShell is available."""
        try:
            subprocess.run(
                [self.powershell, "-Command", "echo ok"],
                capture_output=True,
                timeout=5,
                check=True,
            )
            return True
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            return False

    def _do_connect(self, transport: MCPTransport) -> None:
        return None  # no persistent connection needed

    def _do_disconnect(self) -> None:
        return None

    def _do_health(self) -> MCPHealth:
        status = MCPStatus.CONNECTED
        level = HealthLevel.HEALTHY
        if not self._has_powershell:
            status = MCPStatus.DEGRADED
            level = HealthLevel.WARNING
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=5.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={
                "is_windows": self._is_windows,
                "has_powershell": self._has_powershell,
            },
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        cap = request.capability
        params = request.params
        if cap == "windows.shell":
            return self._shell(params)
        if cap == "windows.powershell":
            return self._powershell(params)
        if cap == "windows.env.get":
            return self._env_get(params)
        if cap == "windows.env.set":
            return self._env_set(params)
        if cap == "windows.process.list":
            return self._process_list(params)
        if cap == "windows.process.kill":
            return self._process_kill(params)
        if cap == "windows.app.launch":
            return self._app_launch(params)
        if cap == "windows.clipboard":
            return self._clipboard(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _shell(self, params: dict[str, Any]) -> dict[str, Any]:
        command = params.get("command", "")
        if not command:
            raise ValueError("missing 'command' parameter")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=self.shell_timeout,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _powershell(self, params: dict[str, Any]) -> dict[str, Any]:
        command = params.get("command", "")
        if not command:
            raise ValueError("missing 'command' parameter")
        if not self._has_powershell:
            raise RuntimeError(
                f"PowerShell ({self.powershell}) is not available on this system"
            )
        result = subprocess.run(
            [self.powershell, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=self.shell_timeout,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _env_get(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "")
        if not name:
            raise ValueError("missing 'name' parameter")
        return {"name": name, "value": os.environ.get(name)}

    def _env_set(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "")
        value = params.get("value", "")
        if not name:
            raise ValueError("missing 'name' parameter")
        os.environ[name] = str(value)
        return {"name": name, "value": value, "set": True}

    def _process_list(self, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        if self._is_windows:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=self.shell_timeout,
            )
            return {"processes": result.stdout, "format": "csv"}
        # POSIX fallback
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=self.shell_timeout,
        )
        return {"processes": result.stdout, "format": "ps_aux"}

    def _process_kill(self, params: dict[str, Any]) -> dict[str, Any]:
        pid = params.get("pid")
        name = params.get("name")
        if pid:
            os.kill(int(pid), 9)
            return {"killed": True, "pid": int(pid)}
        if name:
            if self._is_windows:
                subprocess.run(
                    ["taskkill", "/IM", name, "/F"],
                    capture_output=True,
                    timeout=self.shell_timeout,
                )
            else:
                subprocess.run(
                    ["pkill", "-f", name],
                    capture_output=True,
                    timeout=self.shell_timeout,
                )
            return {"killed": True, "name": name}
        raise ValueError("missing 'pid' or 'name' parameter")

    def _app_launch(self, params: dict[str, Any]) -> dict[str, Any]:
        app = params.get("app", "")
        args = params.get("args", [])
        if not app:
            raise ValueError("missing 'app' parameter")
        if self._is_windows:
            subprocess.Popen([app, *args], shell=True)
        else:
            subprocess.Popen([app, *args])
        return {"app": app, "args": list(args), "launched": True}

    def _clipboard(self, params: dict[str, Any]) -> dict[str, Any]:
        op = params.get("op", "get")
        if op == "get":
            # Try tkinter first (cross-platform)
            try:
                import tkinter

                root = tkinter.Tk()
                root.withdraw()
                content = root.clipboard_get()
                root.destroy()
                return {"op": "get", "data": content}
            except Exception:  # noqa: BLE001
                return {"op": "get", "data": None, "error": "clipboard not available"}
        if op == "set":
            data = params.get("data", "")
            try:
                import tkinter

                root = tkinter.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(data)
                root.update()
                root.destroy()
                return {"op": "set", "data": data, "set": True}
            except Exception as exc:  # noqa: BLE001
                return {"op": "set", "error": str(exc)}
        raise ValueError(f"unknown clipboard op: {op!r}")


__all__ = ["WindowsConnector"]
