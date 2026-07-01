"""Browser adapter — placeholder connector to a headless browser.

The browser adapter will eventually translate Atlas tool calls into browser
automation commands (e.g. via Playwright).
"""

from __future__ import annotations

from typing import Any

from atlas.tools.adapters import BaseAdapter
from atlas.tools.services.browser import BrowserService


class BrowserAdapter(BaseAdapter):
    """Connects :class:`BrowserService` to a headless browser.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real browser transport is wired in.
    """

    def __init__(self, service: BrowserService | None = None) -> None:
        super().__init__(service or BrowserService())

    def open(self, **config: Any) -> None:
        """Open the browser connection. Not yet implemented."""
        raise NotImplementedError("BrowserAdapter.open is not implemented")

    def close(self) -> None:
        """Close the browser connection. Not yet implemented."""
        raise NotImplementedError("BrowserAdapter.close is not implemented")

    def is_open(self) -> bool:
        """Return whether the adapter is open. Always ``False`` for now."""
        return False
