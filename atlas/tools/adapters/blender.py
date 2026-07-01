"""Blender adapter — placeholder connector to a running Blender instance.

The Blender adapter will eventually translate Atlas tool calls into Blender
Python API calls (or MCP server calls) and return the results.
"""

from __future__ import annotations

from typing import Any

from atlas.tools.adapters import BaseAdapter
from atlas.tools.services.blender import BlenderService


class BlenderAdapter(BaseAdapter):
    """Connects :class:`BlenderService` to a running Blender instance.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real Blender transport is wired in.
    """

    def __init__(self, service: BlenderService | None = None) -> None:
        super().__init__(service or BlenderService())

    def open(self, **config: Any) -> None:
        """Open the Blender connection. Not yet implemented."""
        raise NotImplementedError("BlenderAdapter.open is not implemented")

    def close(self) -> None:
        """Close the Blender connection. Not yet implemented."""
        raise NotImplementedError("BlenderAdapter.close is not implemented")

    def is_open(self) -> bool:
        """Return whether the adapter is open. Always ``False`` for now."""
        return False
