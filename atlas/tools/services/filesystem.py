"""Filesystem service — placeholder for local-file domain logic.

The filesystem service will eventually wrap read, write, search, and move
operations against the local filesystem (or a sandboxed view of it).
"""

from __future__ import annotations

from typing import Any

from atlas.tools.services import BaseService


class FilesystemService(BaseService):
    """Domain service for local filesystem operations.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real filesystem integration is wired in.
    """

    def __init__(self) -> None:
        super().__init__(name="filesystem")

    def connect(self, **config: Any) -> None:
        """Connect to the filesystem. Not yet implemented."""
        raise NotImplementedError("FilesystemService.connect is not implemented")

    def disconnect(self) -> None:
        """Disconnect from the filesystem. Not yet implemented."""
        raise NotImplementedError("FilesystemService.disconnect is not implemented")

    def is_connected(self) -> bool:
        """Return whether the service is connected. Always ``False`` for now."""
        return False
