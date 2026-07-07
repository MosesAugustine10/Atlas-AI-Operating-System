"""Browser service — placeholder for browser-automation domain logic.

The browser service will eventually wrap navigation, scraping, and
interaction operations against a headless browser (e.g. Playwright).
"""

from __future__ import annotations

from typing import Any

from atlas.tools.services import BaseService


class BrowserService(BaseService):
    """Domain service for browser automation.

    .. note::
        Placeholder implementation. Methods raise :class:`NotImplementedError`
        until the real browser integration is wired in.
    """

    def __init__(self) -> None:
        super().__init__(name="browser")

    def connect(self, **config: Any) -> None:
        """Connect to the browser. Not yet implemented."""
        raise NotImplementedError("BrowserService.connect is not implemented")

    def disconnect(self) -> None:
        """Disconnect from the browser. Not yet implemented."""
        raise NotImplementedError("BrowserService.disconnect is not implemented")

    def is_connected(self) -> bool:
        """Return whether the service is connected. Always ``False`` for now."""
        return False
