"""Aggregate health monitoring for every MCP connector.

The :class:`MCPHealthMonitor` pulls a health snapshot from every
registered connector and rolls them up into a single
:class:`~atlas.mcp.models.MCPHealth`-based report.

The roll-up rules are:

* If every connector is connected → :attr:`HealthLevel.HEALTHY`.
* If any connector is degraded (and none offline) → :attr:`HealthLevel.WARNING`.
* If any connector is offline → :attr:`HealthLevel.CRITICAL`.
* If every connector is offline → :attr:`HealthLevel.OFFLINE`.
* If no connectors are registered → :attr:`HealthLevel.UNKNOWN`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.models import (
    HealthLevel,
    MCPHealth,
    MCPStatistics,
    MCPStatus,
)
from atlas.mcp.registry import MCPRegistry


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class MCPHealthMonitor:
    """Aggregates per-connector health into a single report.

    Parameters:
        registry: The :class:`MCPRegistry` to pull health from.
    """

    def __init__(self, registry: MCPRegistry) -> None:
        self.registry = registry
        self.logger = get_logger("mcp.health")

    def snapshot(self) -> dict[str, MCPHealth]:
        """Return a ``{connector_name: MCPHealth}`` map for every connector."""
        result: dict[str, MCPHealth] = {}
        for connector in self.registry.list():
            try:
                result[connector.name] = connector.health()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Health check failed for %s: %s", connector.name, exc
                )
                result[connector.name] = MCPHealth(
                    connector=connector.name,
                    status=MCPStatus.FAILED,
                    level=HealthLevel.CRITICAL,
                    last_error=str(exc),
                    last_check_at=_utcnow(),
                )
        return result

    def overall(self) -> HealthLevel:
        """Return the roll-up :class:`HealthLevel` across every connector."""
        stats = self.registry.statistics()
        return stats.overall_health

    def is_healthy(self) -> bool:
        """Return ``True`` if the overall health is ``HEALTHY``."""
        return self.overall() is HealthLevel.HEALTHY

    def degraded_connectors(self) -> list[str]:
        """Return the names of every degraded connector."""
        return [
            name
            for name, health in self.snapshot().items()
            if health.level is HealthLevel.WARNING
        ]

    def offline_connectors(self) -> list[str]:
        """Return the names of every offline connector."""
        return [
            name
            for name, health in self.snapshot().items()
            if health.level in (HealthLevel.CRITICAL, HealthLevel.OFFLINE)
        ]

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict representation of the current health state."""
        snapshot = self.snapshot()
        return {
            "overall": self.overall().value,
            "connectors": {
                name: {
                    "status": h.status.value,
                    "level": h.level.value,
                    "latency_ms": h.latency_ms,
                    "last_error": h.last_error,
                    "uptime_seconds": h.uptime_seconds,
                }
                for name, h in snapshot.items()
            },
            "statistics": _statistics_to_dict(self.registry.statistics()),
        }

    def __repr__(self) -> str:
        return f"<MCPHealthMonitor overall={self.overall().value!r}>"


def _statistics_to_dict(stats: MCPStatistics) -> dict[str, Any]:
    """Convert an :class:`MCPStatistics` to a flat dict."""
    return {
        "connectors_total": stats.connectors_total,
        "connectors_connected": stats.connectors_connected,
        "connectors_degraded": stats.connectors_degraded,
        "connectors_offline": stats.connectors_offline,
        "overall_health": stats.overall_health.value,
    }


__all__ = ["MCPHealthMonitor"]
