"""The Atlas Tool System.

A layered tool framework giving the Kernel a controlled, permissioned gateway
to external capabilities. The layers are:

* **result** / **permissions** — leaf data models.
* **base** — the :class:`BaseTool` contract every tool implements.
* **registry** — the catalog of registered tools.
* **manager** — the gateway that dispatches calls after permission checks.
* **services** — domain logic wrappers (GitHub, filesystem, browser, Blender).
* **adapters** — connectors from services to external systems / MCP servers.

The dependency graph is acyclic: ``result`` and ``permissions`` are leaves;
``base`` depends on both; ``registry`` depends on ``base``; ``manager``
depends on ``registry``, ``base``, ``result``, and ``permissions``; adapters
depend on services, never the reverse.
"""

from __future__ import annotations

from atlas.tools.base import BaseTool
from atlas.tools.manager import ToolManager
from atlas.tools.permissions import Permission, Permissions
from atlas.tools.registry import ToolRegistry
from atlas.tools.result import ToolResult

__all__ = [
    "BaseTool",
    "Permission",
    "Permissions",
    "ToolManager",
    "ToolRegistry",
    "ToolResult",
]
