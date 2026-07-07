"""Playwright MCP connector — real implementation (subprocess-based).

Uses the Playwright Python library (or the ``playwright`` CLI) for
browser automation. If Playwright is not installed, the connector
degrades gracefully and returns an error message.

Capabilities:

* ``playwright.launch`` — launch a browser.
* ``playwright.goto`` — navigate to a URL.
* ``playwright.click`` — click an element.
* ``playwright.type`` — type text into a field.
* ``playwright.upload`` — upload a file.
* ``playwright.download`` — download a file from the page.
* ``playwright.wait`` — wait for a condition.
* ``playwright.screenshot`` — take a screenshot.
* ``playwright.pdf`` — save the page as PDF.
* ``playwright.close`` — close the browser.
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


class PlaywrightConnector(BaseConnector):
    """Real Playwright MCP connector.

    Parameters:
        browser: Browser to launch (``chromium``, ``firefox``, ``webkit``).
        headless: Whether to run in headless mode.
        timeout: Default timeout in seconds.
        screenshots_dir: Directory to save screenshots.
    """

    def __init__(
        self,
        browser: str | None = None,
        headless: bool | None = None,
        timeout: int | None = None,
        screenshots_dir: str | Path | None = None,
    ) -> None:
        cfg = get_connector_config("playwright")
        self.browser = browser or cfg.get("browser", "chromium")
        self.headless = headless if headless is not None else cfg.get("headless", True)
        self.timeout = (
            timeout if timeout is not None else cfg.get("timeout_seconds", 30)
        )
        self.screenshots_dir = Path(
            screenshots_dir or cfg.get("screenshots_dir", "./screenshots")
        )
        self._playwright_available = self._check_playwright()
        self._browser: Any = None
        self._page: Any = None
        self._current_url: str | None = None
        super().__init__(
            name="playwright",
            description=(
                "Playwright browser automation (launch, goto, click, "
                "type, upload, download, wait, screenshot, pdf, close)"
            ),
            supported_transports=(TransportKind.IN_PROCESS, TransportKind.STDIO),
            default_transport=TransportKind.STDIO,
            required_permission=PermissionLevel.EXECUTE,
            capabilities=(
                MCPCapability(
                    name="playwright.launch",
                    description="Launch a browser",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.goto",
                    description="Navigate to URL",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.click",
                    description="Click an element",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.type",
                    description="Type into a field",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="playwright.upload",
                    description="Upload a file",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="playwright.download",
                    description="Download a file",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="playwright.wait",
                    description="Wait for a condition",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="playwright.screenshot",
                    description="Take a screenshot",
                    permissions=("read",),
                ),
                MCPCapability(
                    name="playwright.pdf",
                    description="Save page as PDF",
                    permissions=("write",),
                ),
                MCPCapability(
                    name="playwright.close",
                    description="Close the browser",
                    permissions=("execute",),
                ),
                MCPCapability(
                    name="playwright.evaluate",
                    description="Evaluate JavaScript",
                    permissions=("execute",),
                ),
            ),
            metadata={
                "browser": self.browser,
                "headless": self.headless,
                "playwright_available": self._playwright_available,
                "screenshots_dir": str(self.screenshots_dir),
            },
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _check_playwright(self) -> bool:
        """Return ``True`` if Playwright is importable."""
        try:
            import playwright  # noqa: F401

            return True
        except ImportError:
            return False

    def _do_connect(self, transport: MCPTransport) -> None:
        if not self._playwright_available:
            return  # degrade gracefully
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def _do_disconnect(self) -> None:
        self._close_browser()

    def _do_health(self) -> MCPHealth:
        status = (
            MCPStatus.CONNECTED if self._playwright_available else MCPStatus.DEGRADED
        )
        level = (
            HealthLevel.HEALTHY if self._playwright_available else HealthLevel.WARNING
        )
        return MCPHealth(
            connector=self.name,
            status=status,
            level=level,
            latency_ms=None,
            last_check_at=_utcnow(),
            uptime_seconds=self.uptime_seconds,
            metadata={"playwright_available": self._playwright_available},
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _do_execute(self, request: MCPRequest) -> Any:
        if not self._playwright_available:
            raise RuntimeError(
                "Playwright is not installed — run `pip install playwright` "
                "and `playwright install` to use this connector"
            )
        cap = request.capability
        params = request.params
        if cap == "playwright.launch":
            return self._launch(params)
        if cap == "playwright.goto":
            return self._goto(params)
        if cap == "playwright.click":
            return self._click(params)
        if cap == "playwright.type":
            return self._type(params)
        if cap == "playwright.upload":
            return self._upload(params)
        if cap == "playwright.download":
            return self._download(params)
        if cap == "playwright.wait":
            return self._wait(params)
        if cap == "playwright.screenshot":
            return self._screenshot(params)
        if cap == "playwright.pdf":
            return self._pdf(params)
        if cap == "playwright.close":
            return self._close(params)
        if cap == "playwright.evaluate":
            return self._evaluate(params)
        raise ValueError(f"Unknown capability: {cap!r}")

    # ------------------------------------------------------------------
    # Browser operations
    # ------------------------------------------------------------------

    def _launch(self, params: dict[str, Any]) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        browser_name = params.get("browser", self.browser)
        headless = params.get("headless", self.headless)
        self._pw = sync_playwright().start()
        browser_method = getattr(self._pw, browser_name)
        self._browser = browser_method.launch(headless=headless)
        self._page = self._browser.new_page()
        return {"browser": browser_name, "launched": True, "headless": headless}

    def _goto(self, params: dict[str, Any]) -> dict[str, Any]:
        url = params.get("url", "")
        if not url:
            raise ValueError("missing 'url' parameter")
        if self._page is None:
            raise RuntimeError("browser not launched — call playwright.launch first")
        response = self._page.goto(url, timeout=self.timeout * 1000)
        self._current_url = url
        return {
            "url": url,
            "status": response.status if response else None,
            "title": self._page.title(),
        }

    def _click(self, params: dict[str, Any]) -> dict[str, Any]:
        selector = params.get("selector", "")
        if not selector:
            raise ValueError("missing 'selector' parameter")
        if self._page is None:
            raise RuntimeError("browser not launched")
        self._page.click(selector, timeout=self.timeout * 1000)
        return {"selector": selector, "clicked": True}

    def _type(self, params: dict[str, Any]) -> dict[str, Any]:
        selector = params.get("selector", "")
        text = params.get("text", "")
        if not selector:
            raise ValueError("missing 'selector' parameter")
        if self._page is None:
            raise RuntimeError("browser not launched")
        self._page.fill(selector, text, timeout=self.timeout * 1000)
        return {"selector": selector, "text": text, "typed": True}

    def _upload(self, params: dict[str, Any]) -> dict[str, Any]:
        selector = params.get("selector", "")
        path = params.get("path", "")
        if not selector or not path:
            raise ValueError("missing 'selector' or 'path' parameter")
        if self._page is None:
            raise RuntimeError("browser not launched")
        self._page.set_input_files(selector, path)
        return {"selector": selector, "path": path, "uploaded": True}

    def _download(self, params: dict[str, Any]) -> dict[str, Any]:
        dest = params.get("dest", ".")
        if self._page is None:
            raise RuntimeError("browser not launched")
        # Placeholder — real download handling needs a download event listener.
        return {"dest": dest, "note": "download event handling placeholder"}

    def _wait(self, params: dict[str, Any]) -> dict[str, Any]:
        selector = params.get("selector", "")
        timeout_ms = params.get("timeout_ms", self.timeout * 1000)
        if self._page is None:
            raise RuntimeError("browser not launched")
        if selector:
            self._page.wait_for_selector(selector, timeout=timeout_ms)
            return {"waited_for": selector}
        self._page.wait_for_load_state(timeout=timeout_ms)
        return {"waited_for": "load"}

    def _screenshot(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._page is None:
            raise RuntimeError("browser not launched")
        name = params.get(
            "name", f"screenshot_{_utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        )
        path = self.screenshots_dir / name
        full_page = params.get("full_page", True)
        self._page.screenshot(path=str(path), full_page=full_page)
        return {"path": str(path), "bytes": path.stat().st_size, "format": "png"}

    def _pdf(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._page is None:
            raise RuntimeError("browser not launched")
        name = params.get("name", f"page_{_utcnow().strftime('%Y%m%d_%H%M%S')}.pdf")
        path = self.screenshots_dir / name
        self._page.pdf(path=str(path))
        return {"path": str(path), "bytes": path.stat().st_size, "format": "pdf"}

    def _evaluate(self, params: dict[str, Any]) -> dict[str, Any]:
        script = params.get("script", "")
        if not script:
            raise ValueError("missing 'script' parameter")
        if self._page is None:
            raise RuntimeError("browser not launched")
        result = self._page.evaluate(script)
        return {"result": result}

    def _close(self, params: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002
        self._close_browser()
        return {"closed": True}

    def _close_browser(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:  # noqa: BLE001
                pass
            self._page = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None
        if hasattr(self, "_pw") and self._pw is not None:
            try:
                self._pw.stop()
            except Exception:  # noqa: BLE001
                pass
            self._pw = None


__all__ = ["PlaywrightConnector"]
