"""Atlas Dashboard API package.

Provides a FastAPI backend with REST endpoints and WebSocket live
updates for the Atlas AI Operating System, plus a
:class:`DashboardDataCollector` that aggregates real metrics from
every Atlas subsystem.
"""

from __future__ import annotations

from atlas.dashboard.app import create_app
from atlas.dashboard.collector import DashboardDataCollector

__all__ = ["DashboardDataCollector", "create_app"]
