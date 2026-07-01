"""Filesystem adapter — placeholder connector to the local filesystem.

The filesystem adapter will eventually translate Atlas tool calls into local
file operations (subject to sandboxing and permission rules).
"""

from __future__ import annotations

from typing import Any

from atlas.tools.adapters import BaseAdapter
from atlas.tools.services.filesystem import FilesystemService


class FilesystemAdapter(BaseAdapter):
    """Connects :class:`FilesystemService` to the local filesystem.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real filesystem transport is wired in.
    """

    def __init__(self, service: FilesystemService | None = None) -> None:
        super().__init__(service or FilesystemService())

    def open(self, **config: Any) -> None:
        """Open the filesystem connection. Not yet implemented."""
        raise NotImplementedError("FilesystemAdapter.open is not implemented")

    def close(self) -> None:
        """Close the filesystem connection. Not yet implemented."""
        raise NotImplementedError("FilesystemAdapter.close is not implemented")

    def is_open(self) -> bool:
        """Return whether the adapter is open. Always ``False`` for now."""
        return False
