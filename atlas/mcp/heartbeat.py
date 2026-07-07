"""Heartbeat monitoring for MCP connectors.

The :class:`HeartbeatMonitor` periodically probes every registered
connector and records the latency of each probe. If a connector fails
to respond (or responds too slowly), the monitor flags it for
reconnection.

The current implementation is **deterministic and synchronous**: the
:meth:`beat` method probes every connector once and returns immediately.
A future version can run on a real timer thread.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from datetime import UTC, datetime

from atlas.core.logger import get_logger
from atlas.mcp.models import MCPHealth, MCPStatus
from atlas.mcp.registry import MCPRegistry


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


@dataclasses.dataclass(frozen=True)
class HeartbeatSample:
    """A single heartbeat sample for one connector.

    Attributes:
        connector: Name of the connector sampled.
        timestamp: When the sample was taken.
        latency_ms: Measured latency in milliseconds (``None`` if the
            connector did not respond).
        status: The :class:`MCPStatus` reported by the connector.
        success: Whether the heartbeat succeeded.
    """

    connector: str
    timestamp: datetime
    latency_ms: float | None
    status: MCPStatus
    success: bool


class HeartbeatMonitor:
    """Monitors connector availability via periodic heartbeats.

    Parameters:
        registry: The :class:`MCPRegistry` to probe.
        interval_seconds: Nominal interval between beats (informational;
            the monitor does not run on a timer).
        latency_warning_ms: Latency above this threshold is flagged as
            ``DEGRADED``.
        latency_critical_ms: Latency above this threshold is flagged as
            ``FAILED``.
        history_size: Maximum number of samples kept per connector.
    """

    def __init__(
        self,
        registry: MCPRegistry,
        interval_seconds: float = 30.0,
        latency_warning_ms: float = 500.0,
        latency_critical_ms: float = 2000.0,
        history_size: int = 100,
    ) -> None:
        self.registry = registry
        self.interval_seconds = interval_seconds
        self.latency_warning_ms = latency_warning_ms
        self.latency_critical_ms = latency_critical_ms
        self.history_size = history_size
        self._history: dict[str, deque[HeartbeatSample]] = {}
        self.logger = get_logger("mcp.heartbeat")

    def beat(self) -> list[HeartbeatSample]:
        """Probe every registered connector once.

        Returns the :class:`HeartbeatSample` for each connector.
        """
        samples: list[HeartbeatSample] = []
        for connector in self.registry.list():
            sample = self._probe(connector.name, connector.health())
            samples.append(sample)
            self._record(sample)
        return samples

    def beat_one(self, connector_name: str) -> HeartbeatSample:
        """Probe a single connector by name."""
        connector = self.registry.get(connector_name)
        sample = self._probe(connector.name, connector.health())
        self._record(sample)
        return sample

    def history(self, connector_name: str) -> list[HeartbeatSample]:
        """Return the heartbeat history for ``connector_name``."""
        return list(self._history.get(connector_name, ()))

    def last_sample(self, connector_name: str) -> HeartbeatSample | None:
        """Return the most recent sample for ``connector_name``."""
        history = self._history.get(connector_name)
        if not history:
            return None
        return history[-1]

    def avg_latency(self, connector_name: str) -> float | None:
        """Return the average latency (ms) for ``connector_name``."""
        history = self._history.get(connector_name)
        if not history:
            return None
        latencies = [s.latency_ms for s in history if s.latency_ms is not None]
        if not latencies:
            return None
        return sum(latencies) / len(latencies)

    def recommend_reconnect(self, connector_name: str) -> bool:
        """Return ``True`` if ``connector_name`` should be reconnected.

        Recommendation is based on the last sample: if the connector is
        not connected or the last latency exceeded the critical
        threshold, a reconnect is recommended.
        """
        sample = self.last_sample(connector_name)
        if sample is None:
            return False
        if sample.status not in (MCPStatus.CONNECTED, MCPStatus.DEGRADED):
            return True
        if (
            sample.latency_ms is not None
            and sample.latency_ms > self.latency_critical_ms
        ):
            return True
        return False

    def clear(self) -> None:
        """Drop all heartbeat history."""
        self._history.clear()

    def __len__(self) -> int:
        return sum(len(h) for h in self._history.values())

    def __repr__(self) -> str:
        return (
            f"<HeartbeatMonitor connectors={len(self._history)} "
            f"samples={len(self)}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _probe(self, connector_name: str, health: MCPHealth) -> HeartbeatSample:
        """Build a :class:`HeartbeatSample` from a connector's health."""
        success = health.status in (MCPStatus.CONNECTED, MCPStatus.DEGRADED)
        latency = health.latency_ms
        if latency is not None and latency > self.latency_critical_ms:
            status = MCPStatus.FAILED
            success = False
        elif latency is not None and latency > self.latency_warning_ms:
            status = MCPStatus.DEGRADED
        else:
            status = health.status
        return HeartbeatSample(
            connector=connector_name,
            timestamp=_utcnow(),
            latency_ms=latency,
            status=status,
            success=success,
        )

    def _record(self, sample: HeartbeatSample) -> None:
        """Record ``sample`` in the history."""
        history = self._history.setdefault(
            sample.connector, deque(maxlen=self.history_size)
        )
        history.append(sample)


__all__ = ["HeartbeatMonitor", "HeartbeatSample"]
