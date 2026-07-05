"""Browser MCP connector — real implementation.

Uses :mod:`requests` for HTTP fetching, downloads, cookies, and
session management. Supports opening URLs, downloading files, reading
HTML, managing cookies, and setting headers.

Capabilities:

* ``browser.navigate`` — fetch a URL and return HTML + status.
* ``browser.download`` — download a file to disk.
* ``browser.html`` — fetch a URL and return raw HTML.
* ``browser.cookies`` — get / set / clear cookies for the session.
* ``browser.headers`` — get / set custom headers for the session.
* ``browser.session`` — session management (create, reset, info).
"""

from __future__ import annotations

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


class BrowserConnector(BaseConnector):
    """Real browser MCP connector (HTTP fetcher).

    Parameters:
        user_agent: User-Agent string for requests.
        timeout: Request timeout in seconds.
        max_redirects: Maximum number of redirects to follow.
        verify_ssl: Whether to verify SSL certificates.
    """

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: int | None = None,
        max_redirects: int | None = None,
        verify_ssl: bool | None = None,
    ) -> None:
        cfg = get_connector_config("browser")
        self.user_agent = user_agent or cfg.get("user_agent", "Atlas/1.0")
        self.timeout = (
            timeout if timeout is not None else cfg.get("timeout_seconds", 30)
        )
        self.max_redirects = (
            max_redirects if max_redirects is not None else cfg.get("max_redirects", 10)
        )
        self.verify_ssl = (
            verify_ssl if verify_ssl is not None else cfg.get("verify_ssl", True)
        )
        self._session: Any = None
        self._headers: dict[str, str] = {"User-Agent": self.user_agent}
        self._cookies: dict[str, str] = {}
        super().__init__(
            name="browser",
            description=(
                "Browser automation via HTTP (navigate, download, html, "
                "cookies, headers, session)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.WEBSOCKET),
            default_transport=TransportKind.WEBSOCKET,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="browser.navigate",
                    description="Fetch a URL",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="browser.download",
                    description="Download a file",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="browser.html",
                    description="Fetch raw HTML",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="browser.cookies",
                    description="Get / set / clear cookies",
                    permissions=("read", "write"),
                ),
                MCPCapability(
                    name="browser.headers",
                    description="Get / set headers",
                    permissions=("read", "write"),
                ),
                MCPCapability(
                    name="browser.session",
                    description="Session management",
                    permissions=("read", "write"),
                ),
            ),
            metadata={
                "user_agent": self.user_agent,
                "timeout": self.timeout,
                "max_redirects": self.max_redirects,
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _do_connect(self, transport: MCPTransport) -> None:
        import requests

        self._session = requests.Session()
        self._session.headers.update(self._headers)
        self._session.max_redirects = self.max_redirects

    def _do_disconnect(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def _do_health(self) -> MCPHealth:
        available = self._session is not None
        status = MCPStatus.CONNECTED if available else MCPStatus.DEGRADED
        level = HealthLevel.HEALTHY if available else HealthLevel.WARNING
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=1.0,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={"session_active": available},
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        cap = request.capability
        params = request.params
        if cap == "browser.navigate":
            return self._navigate(params)
        if cap == "browser.download":
            return self._download(params)
        if cap == "browser.html":
            return self._html(params)
        if cap == "browser.cookies":
            return self._cookies_op(params)
        if cap == "browser.headers":
            return self._headers_op(params)
        if cap == "browser.session":
            return self._session_op(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    # ------------------------------------------------------------------
    # Session helper
    # ------------------------------------------------------------------

    def _ensure_session(self) -> Any:
        if self._session is None:
            self._do_connect(MCPTransport())
        return self._session

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _navigate(self, params: dict[str, Any]) -> dict[str, Any]:
        url = params.get("url", "")
        if not url:
            raise ValueError("missing 'url' parameter")
        # Handle file:// URLs by reading the file directly.
        if url.startswith("file://"):
            path = url[7:]  # strip "file://"
            from pathlib import Path

            content = Path(path).read_text(encoding="utf-8")
            return {
                "url": url,
                "status": 200,
                "title": self._extract_title(content),
                "html_length": len(content),
                "content_type": "text/html",
            }
        session = self._ensure_session()
        response = session.get(
            url, timeout=self.timeout, verify=self.verify_ssl, allow_redirects=True
        )
        return {
            "url": response.url,
            "status": response.status_code,
            "title": self._extract_title(response.text),
            "html_length": len(response.text),
            "content_type": response.headers.get("content-type", ""),
        }

    def _download(self, params: dict[str, Any]) -> dict[str, Any]:
        url = params.get("url", "")
        dest = params.get("dest") or params.get("path", "")
        if not url or not dest:
            raise ValueError("missing 'url' or 'dest' parameter")
        session = self._ensure_session()
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with session.get(
            url, timeout=self.timeout, verify=self.verify_ssl, stream=True
        ) as response:
            response.raise_for_status()
            with dest_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        return {"url": url, "dest": str(dest_path), "bytes": dest_path.stat().st_size}

    def _html(self, params: dict[str, Any]) -> dict[str, Any]:
        url = params.get("url", "")
        if not url:
            raise ValueError("missing 'url' parameter")
        # Handle file:// URLs by reading the file directly.
        if url.startswith("file://"):
            path = url[7:]
            from pathlib import Path

            content = Path(path).read_text(encoding="utf-8")
            return {
                "url": url,
                "status": 200,
                "html": content,
            }
        session = self._ensure_session()
        response = session.get(
            url, timeout=self.timeout, verify=self.verify_ssl, allow_redirects=True
        )
        return {
            "url": response.url,
            "status": response.status_code,
            "html": response.text,
        }

    def _cookies_op(self, params: dict[str, Any]) -> dict[str, Any]:
        op = params.get("op", "get")
        session = self._ensure_session()
        if op == "get":
            return {"cookies": dict(session.cookies)}
        if op == "set":
            name = params.get("name", "")
            value = params.get("value", "")
            if not name:
                raise ValueError("missing 'name' for cookie set")
            session.cookies.set(name, value)
            self._cookies[name] = value
            return {"set": name}
        if op == "clear":
            session.cookies.clear()
            self._cookies.clear()
            return {"cleared": True}
        raise ValueError(f"unknown cookies op: {op!r}")

    def _headers_op(self, params: dict[str, Any]) -> dict[str, Any]:
        op = params.get("op", "get")
        session = self._ensure_session()
        if op == "get":
            return {"headers": dict(session.headers)}
        if op == "set":
            name = params.get("name", "")
            value = params.get("value", "")
            if not name:
                raise ValueError("missing 'name' for header set")
            session.headers[name] = value
            self._headers[name] = value
            return {"set": name}
        raise ValueError(f"unknown headers op: {op!r}")

    def _session_op(self, params: dict[str, Any]) -> dict[str, Any]:
        op = params.get("op", "info")
        if op == "info":
            return {
                "active": self._session is not None,
                "headers": dict(self._headers),
                "cookies": dict(self._cookies),
            }
        if op == "reset":
            self._do_disconnect()
            self._do_connect(MCPTransport())
            return {"reset": True}
        raise ValueError(f"unknown session op: {op!r}")

    @staticmethod
    def _extract_title(html: str) -> str:
        """Extract the <title> from HTML (best-effort)."""
        import re

        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""


__all__ = ["BrowserConnector"]
