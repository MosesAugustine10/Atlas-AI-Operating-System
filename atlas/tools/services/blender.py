"""Blender service — placeholder for 3D-scene domain logic.

The Blender service will eventually wrap scene creation, mesh manipulation,
and rendering operations against a running Blender instance (via its Python
API or an MCP server).
"""

from __future__ import annotations

from typing import Any

from atlas.tools.services import BaseService


class BlenderService(BaseService):
    """Domain service for Blender 3D operations.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real Blender integration is wired in.
    """

    def __init__(self) -> None:
        super().__init__(name="blender")

    def connect(self, **config: Any) -> None:
        """Connect to Blender. Not yet implemented."""
        raise NotImplementedError("BlenderService.connect is not implemented")

    def disconnect(self) -> None:
        """Disconnect from Blender. Not yet implemented."""
        raise NotImplementedError("BlenderService.disconnect is not implemented")

    def is_connected(self) -> bool:
        """Return whether the service is connected. Always ``False`` for now."""
        return False
