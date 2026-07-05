"""System controller — collects host resource metrics via psutil.

The :class:`SystemController` periodically samples CPU, RAM, disk and
network utilisation and exposes them as
:class:`~atlas.studio.models.SystemMetric` snapshots. It uses
:mod:`psutil` when available and falls back to zeroed metrics otherwise,
so the Studio can run on hosts without psutil installed.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from atlas.studio.models.studio_models import SystemMetric

#: Default polling interval in seconds.
DEFAULT_INTERVAL: float = 2.0

#: Default number of metric snapshots to retain.
DEFAULT_HISTORY: int = 120


class SystemController:
    """Polls host resources and retains a rolling history of metrics.

    Parameters:
        interval: Seconds between automatic samples when monitoring.
        history_size: Number of :class:`SystemMetric` snapshots to keep.
    """

    def __init__(
        self,
        interval: float = DEFAULT_INTERVAL,
        history_size: int = DEFAULT_HISTORY,
    ) -> None:
        self.interval = float(interval)
        self._history: deque[SystemMetric] = deque(maxlen=history_size)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._monitoring = False
        self._lock = threading.Lock()
        # Cache psutil availability / last network counters.
        self._psutil = _maybe_import_psutil()
        self._last_net: tuple[float, float] | None = None
        self._last_net_ts: float | None = None

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect(self) -> SystemMetric:
        """Sample the host once and return a :class:`SystemMetric`.

        Always returns a fully-populated metric — missing data (e.g. no
        GPU, psutil unavailable) is reported as zero rather than raising.
        """
        if self._psutil is None:
            metric = SystemMetric()
        else:
            metric = self._sample_with_psutil(self._psutil)
        with self._lock:
            self._history.append(metric)
        return metric

    def history(self, limit: int = 100) -> list[SystemMetric]:
        """Return up to ``limit`` most recent metrics (oldest first)."""
        if limit <= 0:
            return []
        with self._lock:
            items = list(self._history)
        return items[-limit:]

    # ------------------------------------------------------------------
    # Monitoring lifecycle
    # ------------------------------------------------------------------

    def start_monitoring(self) -> None:
        """Start a background daemon thread that samples every interval."""
        if self._monitoring:
            return
        self._stop_event.clear()
        self._monitoring = True
        self._thread = threading.Thread(
            target=self._run, name="studio-system-monitor", daemon=True
        )
        self._thread.start()

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread (if running)."""
        if not self._monitoring:
            return
        self._stop_event.set()
        self._monitoring = False
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self.interval + 1.0)
        self._thread = None

    @property
    def monitoring(self) -> bool:
        """Whether the background monitor is currently running."""
        return self._monitoring

    def __len__(self) -> int:
        with self._lock:
            return len(self._history)

    def __repr__(self) -> str:
        return (
            f"<SystemController monitoring={self._monitoring} "
            f"samples={len(self._history)} psutil={self._psutil is not None}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Background loop: sample, sleep, repeat until stopped."""
        while not self._stop_event.is_set():
            try:
                self.collect()
            except Exception:  # noqa: BLE001 — never crash the monitor
                pass
            self._stop_event.wait(self.interval)

    @staticmethod
    def _sample_with_psutil(psutil: Any) -> SystemMetric:
        """Build a :class:`SystemMetric` from a psutil module instance."""
        cpu = _safe(lambda: psutil.cpu_percent(interval=None), 0.0)
        memory = _safe(psutil.virtual_memory, None)
        ram_percent = getattr(memory, "percent", 0.0) if memory else 0.0
        ram_used = getattr(memory, "used", 0) if memory else 0
        ram_total = getattr(memory, "total", 0) if memory else 0
        disk = _safe(psutil.disk_usage, None) if hasattr(psutil, "disk_usage") else None
        disk_percent = getattr(disk, "percent", 0.0) if disk else 0.0
        net_in, net_out = _network_rate(psutil)
        gpu_percent, gpu_name = _gpu_info()
        return SystemMetric(
            cpu_percent=float(cpu),
            ram_percent=float(ram_percent),
            ram_used_mb=float(ram_used) / (1024 * 1024),
            ram_total_mb=float(ram_total) / (1024 * 1024),
            disk_percent=float(disk_percent),
            network_in=float(net_in),
            network_out=float(net_out),
            gpu_percent=float(gpu_percent),
            gpu_name=gpu_name,
        )


def _maybe_import_psutil() -> Any:
    """Return the psutil module, or ``None`` if it is unavailable."""
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil
    except Exception:  # noqa: BLE001 — optional dependency
        return None


def _safe(func: Any, default: Any) -> Any:
    """Call ``func`` and return the result, or ``default`` on error."""
    try:
        return func()
    except Exception:  # noqa: BLE001
        return default


def _network_rate(psutil: Any) -> tuple[float, float]:
    """Return (in_kb_s, out_kb_s) computed from psutil net counters."""
    counters = _safe(lambda: psutil.net_io_counters(), None)
    if counters is None:
        return 0.0, 0.0
    now = time.monotonic()
    in_bytes = getattr(counters, "bytes_recv", 0)
    out_bytes = getattr(counters, "bytes_sent", 0)
    # State is stored on the controller instance via a module-level cache
    # is not feasible across instances; use function attribute storage.
    prev = getattr(_network_rate, "_prev", None)
    _network_rate._prev = in_bytes, out_bytes, now
    if prev is None:
        return 0.0, 0.0
    prev_in, prev_out, prev_ts = prev
    elapsed = max(now - prev_ts, 1e-6)
    rate_in = max((in_bytes - prev_in) / elapsed / 1024.0, 0.0)
    rate_out = max((out_bytes - prev_out) / elapsed / 1024.0, 0.0)
    return rate_in, rate_out


def _gpu_info() -> tuple[float, str]:
    """Return (gpu_percent, gpu_name). Best-effort; zeros if unavailable."""
    try:
        import pynvml  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return 0.0, ""
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return float(util.gpu), str(name)
    except Exception:  # noqa: BLE001
        return 0.0, ""


__all__ = ["DEFAULT_HISTORY", "DEFAULT_INTERVAL", "SystemController"]
