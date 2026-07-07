"""GitHub adapter — placeholder connector to the GitHub API / MCP server.

The GitHub adapter will eventually translate Atlas tool calls into GitHub
API requests (or MCP server calls) and translate the responses back.
"""

from __future__ import annotations

from typing import Any

from atlas.tools.adapters import BaseAdapter
from atlas.tools.services.github import GitHubService


class GitHubAdapter(BaseAdapter):
    """Connects :class:`GitHubService` to the GitHub API.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real GitHub transport is wired in.
    """

    def __init__(self, service: GitHubService | None = None) -> None:
        super().__init__(service or GitHubService())

    def open(self, **config: Any) -> None:
        """Open the GitHub connection. Not yet implemented."""
        raise NotImplementedError("GitHubAdapter.open is not implemented")

    def close(self) -> None:
        """Close the GitHub connection. Not yet implemented."""
        raise NotImplementedError("GitHubAdapter.close is not implemented")

    def is_open(self) -> bool:
        """Return whether the adapter is open. Always ``False`` for now."""
        return False
