"""GitHub service — placeholder for GitHub domain logic.

The GitHub service will eventually wrap repository, issue, and pull-request
operations against the GitHub API or an MCP server that exposes them.
"""

from __future__ import annotations

from typing import Any

from atlas.tools.services import BaseService


class GitHubService(BaseService):
    """Domain service for GitHub operations.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real GitHub integration is wired in.
    """

    def __init__(self) -> None:
        super().__init__(name="github")

    def connect(self, **config: Any) -> None:
        """Connect to GitHub. Not yet implemented."""
        raise NotImplementedError("GitHubService.connect is not implemented")

    def disconnect(self) -> None:
        """Disconnect from GitHub. Not yet implemented."""
        raise NotImplementedError("GitHubService.disconnect is not implemented")

    def is_connected(self) -> bool:
        """Return whether the service is connected. Always ``False`` for now."""
        return False
