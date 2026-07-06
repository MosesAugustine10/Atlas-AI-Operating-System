"""GitHub MCP connector — real implementation.

Uses :mod:`git` (GitPython) for local git operations (clone, status,
branch, checkout, commit, push, pull, fetch, log, diff, tag, remote)
and :mod:`requests` for optional REST API calls (issues, PRs). No
GitHub token is required for local git operations.

Capabilities:

* ``git.clone`` — clone a repository.
* ``git.status`` — show working-tree status.
* ``git.branch`` — list / create / delete branches.
* ``git.checkout`` — checkout a branch or commit.
* ``git.commit`` — stage and commit changes.
* ``git.push`` — push commits to a remote.
* ``git.pull`` — pull from a remote.
* ``git.fetch`` — fetch from a remote.
* ``git.log`` — show commit history.
* ``git.diff`` — show diffs.
* ``git.tag`` — list / create tags.
* ``git.remote`` — list / add / remove remotes.
* ``repo.list`` — (REST) list repositories for the authenticated user.
* ``repo.get`` — (REST) get repository metadata.
* ``issue.list`` — (REST) list issues.
* ``issue.create`` — (REST) create an issue.
* ``pr.create`` — (REST) create a pull request.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.mcp.base import BaseConnector
from atlas.mcp.connector_config import get_connector_config
from atlas.mcp.exceptions import MCPConnectionError
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
    """Real GitHub / git MCP connector.

    Parameters:
        workspace: Directory where repositories are cloned / opened.
            Defaults to ``./github_workspace``.
        token: Optional GitHub API token for REST calls. If ``None``,
            the connector reads ``GITHUB_TOKEN`` from the environment.
    """

    def __init__(
        self,
        workspace: str | Path | None = None,
        token: str | None = None,
    ) -> None:
        cfg = get_connector_config("github")
        self.workspace = Path(workspace or "./github_workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.token = token or os.environ.get(cfg.get("token_env", "GITHUB_TOKEN"))
        self.api_base = cfg.get("api_base", "https://api.github.com")
        self.default_branch = cfg.get("default_branch", "main")
        self.timeout = cfg.get("timeout_seconds", 30)
        self._git_available = self._check_git()
        super().__init__(
            name="github",
            description=(
                "GitHub / git access (clone, status, branch, checkout, "
                "commit, push, pull, fetch, log, diff, tag, remote, "
                "issues, PRs)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.HTTP),
            default_transport=TransportKind.HTTP,
            required_permission=PermissionLevel.READ,
            capabilities=(
                MCPCapability(
                    name="git.clone",
                    description="Clone a repository",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="git.status",
                    description="Show working-tree status",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="git.branch",
                    description="List / create / delete branches",
                    permissions=("read", "write"),
                ),
                MCPCapability(
                    name="git.checkout",
                    description="Checkout a branch or commit",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.commit",
                    description="Stage and commit changes",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.push",
                    description="Push commits to a remote",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.pull",
                    description="Pull from a remote",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.fetch",
                    description="Fetch from a remote",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="git.log",
                    description="Show commit history",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="git.diff", description="Show diffs", permissions=("read",)
                ),
                MCPCapability(
                    name="git.tag",
                    description="List / create tags",
                    permissions=("read", "write"),
                ),
                MCPCapability(
                    name="git.remote",
                    description="List / add / remove remotes",
                    permissions=("read", "write"),
                ),
                MCPCapability(
                    name="git.stash",
                    description="Stash / pop / list stashes",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.merge",
                    description="Merge a branch",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="git.blame",
                    description="Show blame for a file",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="git.rollback",
                    description="Rollback to a previous commit",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="repo.list",
                    description="List repositories (REST)",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="repo.get",
                    description="Get repository metadata (REST)",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="issue.list",
                    description="List issues (REST)",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="issue.create",
                    description="Create issue (REST)",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="pr.create",
                    description="Create pull request (REST)",
                    permissions=("write",),
                ),
            ),
            metadata={
                "workspace": str(self.workspace),
                "git_available": self._git_available,
                "has_token": self.token is not None,
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _check_git(self) -> bool:
        """Return ``True`` if ``git`` CLI is available."""
        try:
            subprocess.run(
                ["git", "--version"],
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
        if not self._git_available:
            raise MCPConnectionError(
                "git CLI not available — install git to use the GitHub connector",
                connector="github",
            )

    def _do_disconnect(self) -> None:
        return None

    def _do_health(self) -> MCPHealth:
        status = MCPStatus.CONNECTED if self._git_available else MCPStatus.DEGRADED
        level = HealthLevel.HEALTHY if self._git_available else HealthLevel.WARNING
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=10.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={
                "git_available": self._git_available,
                "has_token": self.token is not None,
            },
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        cap = request.capability
        params = request.params
        # Git operations (local, no token required)
        if cap == "git.clone":
            return self._clone(params)
        if cap == "git.status":
            return self._git_status(params)
        if cap == "git.branch":
            return self._branch(params)
        if cap == "git.checkout":
            return self._checkout(params)
        if cap == "git.commit":
            return self._commit(params)
        if cap == "git.push":
            return self._push(params)
        if cap == "git.pull":
            return self._pull(params)
        if cap == "git.fetch":
            return self._fetch(params)
        if cap == "git.log":
            return self._log(params)
        if cap == "git.diff":
            return self._diff(params)
        if cap == "git.tag":
            return self._tag(params)
        if cap == "git.remote":
            return self._remote(params)
        if cap == "git.stash":
            return self._stash(params)
        if cap == "git.merge":
            return self._merge(params)
        if cap == "git.blame":
            return self._blame(params)
        if cap == "git.rollback":
            return self._rollback(params)
        # REST API operations (token required)
        if cap == "repo.list":
            return self._rest_list_repos(params)
        if cap == "repo.get":
            return self._rest_get_repo(params)
        if cap == "issue.list":
            return self._rest_list_issues(params)
        if cap == "issue.create":
            return self._rest_create_issue(params)
        if cap == "pr.create":
            return self._rest_create_pr(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    # ------------------------------------------------------------------
    # Git operations (via GitPython)
    # ------------------------------------------------------------------

    def _get_repo(self, params: dict[str, Any]):
        """Open a repo from ``params['path']`` or ``params['name']``."""
        import git

        path = params.get("path") or params.get("name")
        if not path:
            raise ValueError("missing 'path' or 'name' parameter")
        repo_path = (
            self.workspace / path if not Path(path).is_absolute() else Path(path)
        )
        return git.Repo(str(repo_path))

    def _clone(self, params: dict[str, Any]) -> dict[str, Any]:
        import git

        url = params.get("url", "")
        name = params.get("name", "")
        if not url or not name:
            raise ValueError("missing 'url' or 'name' parameter")
        target = self.workspace / name
        if target.exists():
            return {
                "url": url,
                "path": str(target),
                "cloned": False,
                "reason": "already exists",
            }
        git.Repo.clone_from(url, str(target))
        return {"url": url, "path": str(target), "cloned": True}

    def _git_status(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        return {
            "path": str(repo.working_tree_dir),
            "is_dirty": repo.is_dirty(),
            "untracked": list(repo.untracked_files),
            "active_branch": (
                repo.active_branch.name if not repo.head.is_detached else None
            ),
        }

    def _branch(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        op = params.get("op", "list")
        if op == "list":
            branches = [b.name for b in repo.branches]
            return {
                "branches": branches,
                "active": (
                    repo.active_branch.name if not repo.head.is_detached else None
                ),
            }
        if op == "create":
            name = params.get("name", "")
            if not name:
                raise ValueError("missing 'name' for branch create")
            repo.create_head(name)
            return {"created": name}
        if op == "delete":
            name = params.get("name", "")
            if not name:
                raise ValueError("missing 'name' for branch delete")
            repo.delete_head(name, force=True)
            return {"deleted": name}
        raise ValueError(f"unknown branch op: {op!r}")

    def _checkout(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        target = params.get("target", "")
        if not target:
            raise ValueError("missing 'target' parameter")
        repo.git.checkout(target)
        return {"checked_out": target}

    def _commit(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        message = params.get("message", "auto-commit")
        add_all = params.get("add_all", True)
        if add_all:
            repo.git.add(A=True)
        if not repo.is_dirty() and not repo.untracked_files:
            return {"committed": False, "reason": "nothing to commit"}
        commit = repo.index.commit(message)
        return {"committed": True, "commit_hash": commit.hexsha, "message": message}

    def _push(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        remote = params.get("remote", "origin")
        refspec = params.get("refspec", None)
        origin = repo.remote(remote)
        origin.push(refspec) if refspec else origin.push()
        return {"pushed": True, "remote": remote}

    def _pull(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        remote = params.get("remote", "origin")
        origin = repo.remote(remote)
        origin.pull()
        return {"pulled": True, "remote": remote}

    def _fetch(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        remote = params.get("remote", "origin")
        origin = repo.remote(remote)
        origin.fetch()
        return {"fetched": True, "remote": remote}

    def _log(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        max_count = params.get("max_count", 10)
        commits = []
        for commit in repo.iter_commits(max_count=max_count):
            commits.append(
                {
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                }
            )
        return {"commits": commits, "count": len(commits)}

    def _diff(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        target = params.get("target", "HEAD")
        diff = repo.git.diff(target)
        return {"diff": diff}

    def _tag(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        op = params.get("op", "list")
        if op == "list":
            tags = [t.name for t in repo.tags]
            return {"tags": tags}
        if op == "create":
            name = params.get("name", "")
            if not name:
                raise ValueError("missing 'name' for tag create")
            repo.create_tag(name)
            return {"created": name}
        raise ValueError(f"unknown tag op: {op!r}")

    def _remote(self, params: dict[str, Any]) -> dict[str, Any]:
        repo = self._get_repo(params)
        op = params.get("op", "list")
        if op == "list":
            remotes = [
                {"name": r.name, "url": list(r.urls)[0] if list(r.urls) else ""}
                for r in repo.remotes
            ]
            return {"remotes": remotes}
        if op == "add":
            name = params.get("name", "")
            url = params.get("url", "")
            if not name or not url:
                raise ValueError("missing 'name' or 'url' for remote add")
            repo.create_remote(name, url)
            return {"added": name}
        if op == "remove":
            name = params.get("name", "")
            if not name:
                raise ValueError("missing 'name' for remote remove")
            repo.delete_remote(name)
            return {"removed": name}
        raise ValueError(f"unknown remote op: {op!r}")

    def _stash(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stash, pop, or list stashes."""
        repo = self._get_repo(params)
        op = params.get("op", "push")
        if op == "push":
            msg = params.get("message", "")
            repo.git.stash("push", "-m", msg) if msg else repo.git.stash("push")
            return {"stashed": True, "message": msg}
        if op == "pop":
            repo.git.stash("pop")
            return {"popped": True}
        if op == "list":
            stashes = list(repo.git.stash("list").splitlines())
            return {"stashes": stashes, "count": len(stashes)}
        if op == "drop":
            index = params.get("index", 0)
            repo.git.stash("drop", str(index))
            return {"dropped": True, "index": index}
        raise ValueError(f"unknown stash op: {op!r}")

    def _merge(self, params: dict[str, Any]) -> dict[str, Any]:
        """Merge a branch into the current branch."""
        repo = self._get_repo(params)
        branch = params.get("branch", "")
        if not branch:
            raise ValueError("branch is required for merge")
        no_ff = params.get("no_ff", False)
        if no_ff:
            repo.git.merge("--no-ff", branch)
        else:
            repo.git.merge(branch)
        return {"merged": True, "branch": branch}

    def _blame(self, params: dict[str, Any]) -> dict[str, Any]:
        """Show blame for a file."""
        repo = self._get_repo(params)
        file_path = params.get("file", "")
        if not file_path:
            raise ValueError("file is required for blame")
        blame_output = repo.git.blame("--porcelain", file_path)
        lines: list[dict[str, str]] = []
        for line in blame_output.splitlines():
            if line and not line.startswith("\t"):
                parts = line.split()
                if len(parts) >= 2:
                    lines.append({"commit": parts[0], "line": parts[1]})
        return {"file": file_path, "blame_lines": lines, "count": len(lines)}

    def _rollback(self, params: dict[str, Any]) -> dict[str, Any]:
        """Rollback to a previous commit (git reset or revert)."""
        repo = self._get_repo(params)
        target = params.get("commit", "")
        if not target:
            raise ValueError("commit is required for rollback")
        mode = params.get("mode", "soft")
        if mode == "hard":
            repo.git.reset("--hard", target)
        elif mode == "soft":
            repo.git.reset("--soft", target)
        elif mode == "mixed":
            repo.git.reset("--mixed", target)
        elif mode == "revert":
            repo.git.revert("--no-edit", target)
        else:
            raise ValueError(f"unknown rollback mode: {mode!r}")
        return {"rolled_back": True, "commit": target, "mode": mode}

    # ------------------------------------------------------------------
    # REST API operations (token required)
    # ------------------------------------------------------------------

    def _rest_request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Make an authenticated GitHub REST API request."""
        import requests

        if not self.token:
            raise PermissionError(
                "GitHub token required for REST API calls — set GITHUB_TOKEN env var"
            )
        url = f"{self.api_base}{endpoint}"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.request(
            method, url, headers=headers, json=json, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _rest_list_repos(self, params: dict[str, Any]) -> dict[str, Any]:
        repos = self._rest_request(
            "GET", "/user/repos", params={"per_page": params.get("per_page", 30)}
        )
        return {
            "repos": [
                {"name": r["name"], "full_name": r["full_name"], "url": r["html_url"]}
                for r in repos
            ]
        }

    def _rest_get_repo(self, params: dict[str, Any]) -> dict[str, Any]:
        owner = params.get("owner", "")
        repo_name = params.get("repo", "")
        if not owner or not repo_name:
            raise ValueError("missing 'owner' or 'repo' parameter")
        data = self._rest_request("GET", f"/repos/{owner}/{repo_name}")
        return {
            "repo": data["full_name"],
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
        }

    def _rest_list_issues(self, params: dict[str, Any]) -> dict[str, Any]:
        owner = params.get("owner", "")
        repo_name = params.get("repo", "")
        if not owner or not repo_name:
            raise ValueError("missing 'owner' or 'repo' parameter")
        data = self._rest_request("GET", f"/repos/{owner}/{repo_name}/issues")
        return {
            "issues": [
                {"id": i["id"], "number": i["number"], "title": i["title"]}
                for i in data
            ]
        }

    def _rest_create_issue(self, params: dict[str, Any]) -> dict[str, Any]:
        owner = params.get("owner", "")
        repo_name = params.get("repo", "")
        title = params.get("title", "")
        body = params.get("body", "")
        if not owner or not repo_name or not title:
            raise ValueError("missing 'owner', 'repo', or 'title' parameter")
        data = self._rest_request(
            "POST",
            f"/repos/{owner}/{repo_name}/issues",
            json={"title": title, "body": body},
        )
        return {
            "issue_number": data["number"],
            "title": data["title"],
            "url": data["html_url"],
        }

    def _rest_create_pr(self, params: dict[str, Any]) -> dict[str, Any]:
        owner = params.get("owner", "")
        repo_name = params.get("repo", "")
        title = params.get("title", "")
        head = params.get("head", "")
        base = params.get("base", self.default_branch)
        body = params.get("body", "")
        if not owner or not repo_name or not title or not head:
            raise ValueError("missing 'owner', 'repo', 'title', or 'head' parameter")
        data = self._rest_request(
            "POST",
            f"/repos/{owner}/{repo_name}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )
        return {
            "pr_number": data["number"],
            "title": data["title"],
            "url": data["html_url"],
        }


__all__ = ["GitHubConnector"]
