"""Atlas Dashboard API package.

Provides a FastAPI backend with REST endpoints and WebSocket live
updates for the Atlas AI Operating System.
"""

from __future__ import annotations

from atlas.dashboard.app import create_app

__all__ = ["create_app"]
