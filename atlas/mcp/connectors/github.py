"""GitHub MCP connector — deterministic placeholder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.mcp.base import BaseConnector
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


class GitHubConnector(BaseConnector):
    """Deterministic placeholder GitHub MCP connector."""

    def __init__(self) -> None:
        super().__init__(
            name="github",
            description="GitHub access (repos, issues, PRs, commits)",
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="repo.list",
                    description="List repositories",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="repo.get",
                    description="Get repository info",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="issue.list", description="List issues", permissions=("read",)
                ),
                MCPCapability(
                    name="issue.create",
                    description="Create issue",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="pr.create",
                    description="Create pull request",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.commit",
                    description="Create a commit",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.push", description="Push commits", permissions=("write",)
                ),
            ),
        )

    def _do_connect(self, transport: MCPTransport) -> None:
        return None

    def _do_disconnect(self) -> None:
        return None

    def _do_health(self) -> MCPHealth:
        return MCPHealth(
            connector=self.name,
            status=MCPStatus.CONNECTED,
            level=HealthLevel.HEALTHY,
            latency_ms=120.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
        )

    def _do_execute(self, request: MCPRequest) -> Any:
        if request.capability == "repo.list":
            return {"repos": ["atlas-ai", "atlas-tools", "atlas-docs"]}
        if request.capability == "repo.get":
            return {"repo": request.params.get("repo", ""), "stars": 42, "forks": 7}
        if request.capability == "issue.list":
            return {"issues": [{"id": 1, "title": "Placeholder issue"}]}
        if request.capability == "issue.create":
            return {"issue_number": 100, "title": request.params.get("title", "")}
        if request.capability == "pr.create":
            return {"pr_number": 50, "title": request.params.get("title", "")}
        if request.capability == "git.commit":
            return {
                "commit_hash": "abc123def456",
                "message": request.params.get("message", ""),
            }
        if request.capability == "git.push":
            return {"pushed": True, "commits": request.params.get("commits", 1)}
        return {"capability": request.capability, "params": request.params}


__all__ = ["GitHubConnector"]
