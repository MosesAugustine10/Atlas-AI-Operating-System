"""Blender MCP connector — real implementation (subprocess-based).

Drives Blender via its command-line interface (``blender --background
--python script.py``). If Blender is not installed, the connector
degrades gracefully and returns an error message.

Capabilities:

* ``blender.launch`` — launch Blender (background mode).
* ``blender.script`` — run a Python script in Blender.
* ``blender.open`` — open a Blender project.
* ``blender.save`` — save the current project.
* ``blender.render`` — render an image.
* ``blender.render_animation`` — render an animation.
* ``blender.execute`` — execute a Python expression.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
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


class BlenderConnector(BaseConnector):
    """Real Blender MCP connector (subprocess-based).

    Parameters:
        blender_path: Path to the Blender executable.
        timeout: Subprocess timeout in seconds.
        output_dir: Directory for render output.
    """

    def __init__(
        self,
        blender_path: str | None = None,
        timeout: int | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        cfg = get_connector_config("blender")
        self.blender_path = blender_path or cfg.get("blender_path", "blender")
        self.timeout = (
            timeout if timeout is not None else cfg.get("timeout_seconds", 120)
        )
        self.output_dir = Path(output_dir or cfg.get("output_dir", "./renders"))
        self._blender_available = self._check_blender()
        super().__init__(
            name="blender",
            description=(
                "Blender 3D automation (launch, script, open, save, "
                "render, render_animation, execute)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.NAMED_PIPE),
            default_transport=TransportKind.NAMED_PIPE,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="blender.launch",
                    description="Launch Blender (background)",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="blender.script",
                    description="Run a Python script",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="blender.open",
                    description="Open a project",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="blender.save",
                    description="Save the project",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.render",
                    description="Render an image",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="blender.render_animation",
                    description="Render an animation",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="blender.execute",
                    description="Execute a Python expression",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="blender.scene.new",
                    description="Create a new scene",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.object.add",
                    description="Add an object",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="blender.export",
                    description="Export to a file",
                    permissions=("write",),
                ),
            ),
            metadata={
                "blender_path": self.blender_path,
                "blender_available": self._blender_available,
                "output_dir": str(self.output_dir),
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _check_blender(self) -> bool:
        """Return ``True`` if Blender is available."""
        try:
            result = shutil.which(self.blender_path)
            if result:
                return True
            # Try running it directly
            subprocess.run(
                [self.blender_path, "--version"],
                capture_output=True,
                timeout=10,
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
        if self._blender_available:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def _do_disconnect(self) -> None:
        return None

    def _do_health(self) -> MCPHealth:
        status = MCPStatus.CONNECTED if self._blender_available else MCPStatus.DEGRADED
        level = HealthLevel.HEALTHY if self._blender_available else HealthLevel.WARNING
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=None,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={"blender_available": self._blender_available},
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        if not self._blender_available:
            raise RuntimeError(
                f"Blender ({self.blender_path}) is not installed — "
                f"install Blender to use this connector"
            )
        cap = request.capability
        params = request.params
        if cap == "blender.launch":
            return self._launch(params)
        if cap == "blender.script":
            return self._run_script(params)
        if cap == "blender.open":
            return self._open_project(params)
        if cap == "blender.save":
            return self._save_project(params)
        if cap == "blender.render":
            return self._render(params)
        if cap == "blender.render_animation":
            return self._render_animation(params)
        if cap == "blender.execute":
            return self._execute_expr(params)
        if cap == "blender.scene.new":
            return self._scene_new(params)
        if cap == "blender.object.add":
            return self._object_add(params)
        if cap == "blender.export":
            return self._export(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    # ------------------------------------------------------------------
    # Blender CLI runner
    # ------------------------------------------------------------------

    def _run_blender(
        self,
        args: list[str],
        script: str | None = None,
        blend_file: str | None = None,
    ) -> dict[str, Any]:
        """Run Blender in background mode with optional script / blend file."""
        cmd = [self.blender_path, "--background"]
        if blend_file:
            cmd.append(blend_file)
        if script:
            cmd.extend(["--python", script])
        cmd.extend(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _run_python_script(
        self, code: str, blend_file: str | None = None
    ) -> dict[str, Any]:
        """Run Python ``code`` inside Blender."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            script_path = f.name
        try:
            return self._run_blender([], script=script_path, blend_file=blend_file)
        finally:
            Path(script_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _launch(self, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        result = self._run_blender([])
        return {"launched": result["exit_code"] == 0, "exit_code": result["exit_code"]}

    def _run_script(self, params: dict[str, Any]) -> dict[str, Any]:
        script_path = params.get("path") or params.get("script", "")
        blend_file = params.get("blend_file")
        if not script_path:
            raise ValueError("missing 'path' or 'script' parameter")
        return self._run_blender([], script=script_path, blend_file=blend_file)

    def _open_project(self, params: dict[str, Any]) -> dict[str, Any]:
        path = params.get("path", "")
        if not path:
            raise ValueError("missing 'path' parameter")
        result = self._run_blender([], blend_file=path)
        return {
            "path": path,
            "opened": result["exit_code"] == 0,
            "exit_code": result["exit_code"],
        }

    def _save_project(self, params: dict[str, Any]) -> dict[str, Any]:
        blend_file = params.get("blend_file", "")
        dest = params.get("dest", "")
        if not dest:
            raise ValueError("missing 'dest' parameter")
        code = "import bpy\n" f"bpy.ops.wm.save_as_mainfile(filepath={dest!r})\n"
        result = self._run_python_script(code, blend_file=blend_file or None)
        return {
            "dest": dest,
            "saved": result["exit_code"] == 0,
            "exit_code": result["exit_code"],
        }

    def _render(self, params: dict[str, Any]) -> dict[str, Any]:
        blend_file = params.get("blend_file", "")
        frame = params.get("frame", 1)
        output = params.get("output") or str(
            self.output_dir / f"render_{frame:04d}.png"
        )
        code = (
            "import bpy\n"
            f"bpy.context.scene.frame_set({frame})\n"
            f"bpy.context.scene.render.filepath = {output!r}\n"
            "bpy.context.scene.render.image_settings.file_format = 'PNG'\n"
            "bpy.ops.render.render(write_still=True)\n"
        )
        result = self._run_python_script(code, blend_file=blend_file or None)
        return {
            "frame": frame,
            "output": output,
            "rendered": result["exit_code"] == 0,
            "exit_code": result["exit_code"],
        }

    def _render_animation(self, params: dict[str, Any]) -> dict[str, Any]:
        blend_file = params.get("blend_file", "")
        start = params.get("start", 1)
        end = params.get("end", 250)
        output = params.get("output") or str(self.output_dir / "anim_")
        code = (
            "import bpy\n"
            f"bpy.context.scene.frame_start = {start}\n"
            f"bpy.context.scene.frame_end = {end}\n"
            f"bpy.context.scene.render.filepath = {output!r}\n"
            "bpy.ops.render.render(animation=True)\n"
        )
        result = self._run_python_script(code, blend_file=blend_file or None)
        return {
            "start": start,
            "end": end,
            "output": output,
            "rendered": result["exit_code"] == 0,
            "exit_code": result["exit_code"],
        }

    def _execute_expr(self, params: dict[str, Any]) -> dict[str, Any]:
        expr = params.get("expr") or params.get("expression", "")
        blend_file = params.get("blend_file")
        if not expr:
            raise ValueError("missing 'expr' or 'expression' parameter")
        code = f"import bpy\n{expr}\n"
        result = self._run_python_script(code, blend_file=blend_file or None)
        return {
            "expr": expr,
            "exit_code": result["exit_code"],
            "stdout": result["stdout"],
        }

    def _scene_new(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "Scene")
        code = (
            "import bpy\n"
            f"bpy.ops.scene.new(type='NEW')\n"
            f"bpy.context.scene.name = {name!r}\n"
        )
        result = self._run_python_script(code)
        return {"scene": name, "created": result["exit_code"] == 0}

    def _object_add(self, params: dict[str, Any]) -> dict[str, Any]:
        obj_type = params.get("type", "cube")
        name = params.get("name", obj_type.capitalize())
        code = (
            "import bpy\n"
            f"bpy.ops.mesh.primitive_{obj_type}_add()\n"
            f"bpy.context.active_object.name = {name!r}\n"
        )
        result = self._run_python_script(code)
        return {"object": name, "type": obj_type, "added": result["exit_code"] == 0}

    def _export(self, params: dict[str, Any]) -> dict[str, Any]:
        path = params.get("path", "")
        fmt = params.get("format", "obj")
        blend_file = params.get("blend_file", "")
        if not path:
            raise ValueError("missing 'path' parameter")
        ops_map = {
            "obj": "bpy.ops.wm.obj_export(filepath={path!r})",
            "fbx": "bpy.ops.export_scene.fbx(filepath={path!r})",
            "gltf": "bpy.ops.export_scene.gltf(filepath={path!r})",
        }
        op = ops_map.get(fmt, ops_map["obj"])
        code = f"import bpy\n{op.format(path=path)}\n"
        result = self._run_python_script(code, blend_file=blend_file or None)
        return {"path": path, "format": fmt, "exported": result["exit_code"] == 0}


__all__ = ["BlenderConnector"]
