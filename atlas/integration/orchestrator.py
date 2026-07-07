"""Orchestrator — the single user-facing façade for Atlas.

The :class:`Orchestrator` is the only object users should interact with.
It wraps a :class:`BootstrappedAtlas` and exposes a small, stable API:

* :meth:`initialize` — build the container and start every subsystem.
* :meth:`start` — alias for :meth:`initialize` (idempotent).
* :meth:`stop` — gracefully shut down every subsystem.
* :meth:`restart` — stop and re-initialize.
* :meth:`status` — return the current lifecycle phase.
* :meth:`health` — return the latest :class:`HealthReport`.
* :meth:`run` — execute a user request via the runtime.

The orchestrator owns no business logic. Every call delegates to the
appropriate subsystem resolved from the container.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.integration.bootstrap import Bootstrap, BootstrappedAtlas
from atlas.integration.container import DIContainer
from atlas.integration.diagnostics import DiagnosticsCollector, DiagnosticsReport
from atlas.integration.health import HealthMonitor, HealthReport
from atlas.integration.shutdown import ShutdownManager, ShutdownReport
from atlas.integration.startup import StartupReport


class OrchestratorState(enum.StrEnum):
    """Lifecycle states of the :class:`Orchestrator` itself.

    Attributes:
        UNINITIALIZED: The orchestrator has been constructed but not
            started.
        INITIALIZING: :meth:`initialize` is in progress.
        RUNNING: Every subsystem is up and the runtime is accepting
            requests.
        STOPPING: :meth:`stop` is in progress.
        STOPPED: Every subsystem has been shut down.
        FAILED: Initialization or shutdown failed.
    """

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class OrchestratorError(RuntimeError):
    """Raised when the orchestrator cannot perform the requested operation."""


class Orchestrator:
    """The single user-facing façade for Atlas.

    Parameters:
        config: A config object, dict, or path passed through to
            :class:`Bootstrap`.
        bootstrap: Optional pre-built :class:`Bootstrap`. If omitted, a
            fresh one is created with ``config``.
    """

    def __init__(
        self,
        config: Any = None,
        bootstrap: Bootstrap | None = None,
    ) -> None:
        self._config = config
        self._bootstrap = (
            bootstrap if bootstrap is not None else Bootstrap(config=config)
        )
        self.logger = get_logger("integration.orchestrator")
        self._state: OrchestratorState = OrchestratorState.UNINITIALIZED
        self._atlas: BootstrappedAtlas | None = None
        self._last_startup: StartupReport | None = None
        self._last_shutdown: ShutdownReport | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> BootstrappedAtlas:
        """Build the container and start every subsystem.

        Raises:
            OrchestratorError: If already running or initialization fails.

        Returns:
            The :class:`BootstrappedAtlas` bundle.
        """
        if self._state is OrchestratorState.RUNNING:
            raise OrchestratorError("Orchestrator is already running")
        self._state = OrchestratorState.INITIALIZING
        try:
            self._atlas = self._bootstrap.run()
            self._last_startup = self._atlas.startup_report
        except Exception as exc:
            self._state = OrchestratorState.FAILED
            raise OrchestratorError(f"Initialization failed: {exc}") from exc
        self._state = OrchestratorState.RUNNING
        self.logger.info("Orchestrator initialized")
        return self._atlas

    def start(self) -> BootstrappedAtlas:
        """Alias for :meth:`initialize`."""
        return self.initialize()

    def stop(self) -> ShutdownReport:
        """Gracefully shut down every subsystem.

        Raises:
            OrchestratorError: If not running.
        """
        if self._state is not OrchestratorState.RUNNING:
            raise OrchestratorError(
                f"Cannot stop orchestrator in state {self._state.value}"
            )
        if self._atlas is None:
            raise OrchestratorError("No bootstrapped atlas to stop")
        self._state = OrchestratorState.STOPPING
        try:
            manager = ShutdownManager(self._atlas.container)
            report = manager.shutdown()
            self._last_shutdown = report
        except Exception as exc:
            self._state = OrchestratorState.FAILED
            raise OrchestratorError(f"Shutdown failed: {exc}") from exc
        self._state = OrchestratorState.STOPPED
        self.logger.info("Orchestrator stopped")
        return report

    def restart(self) -> BootstrappedAtlas:
        """Stop and re-initialize.

        Raises:
            OrchestratorError: If not currently running.
        """
        if self._state is not OrchestratorState.RUNNING:
            raise OrchestratorError("Cannot restart: orchestrator is not running")
        self.stop()
        # Rebuild bootstrap so the container is fresh.
        self._bootstrap = Bootstrap(config=self._config)
        return self.initialize()

    # ------------------------------------------------------------------
    # Status / health / diagnostics
    # ------------------------------------------------------------------

    def status(self) -> OrchestratorState:
        """Return the current orchestrator lifecycle state."""
        return self._state

    def health(self) -> HealthReport:
        """Return the latest :class:`HealthReport`.

        Raises:
            OrchestratorError: If not running.
        """
        monitor = self._require_health_monitor()
        return monitor.snapshot()

    def diagnostics(self) -> DiagnosticsReport:
        """Return the latest :class:`DiagnosticsReport`.

        Raises:
            OrchestratorError: If not running.
        """
        collector = self._atlas.container.get_optional("diagnostics")
        if collector is None:
            collector = DiagnosticsCollector(
                self._atlas.container,
                started_at=self._atlas.started_at,
                startup_time_seconds=self._atlas.startup_report.duration_seconds,
            )
        return collector.snapshot()

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------

    def run(self, request: str, user: str | None = None) -> Any:
        """Execute a user request via the runtime.

        Raises:
            OrchestratorError: If not running or the runtime is not
                registered.
        """
        runtime = self._require_runtime()
        try:
            return runtime.handle(request, user=user)
        except Exception as exc:
            raise OrchestratorError(f"Request failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def container(self) -> DIContainer:
        """Return the wired container.

        Raises:
            OrchestratorError: If not running.
        """
        if self._atlas is None:
            raise OrchestratorError("Orchestrator is not initialized")
        return self._atlas.container

    @property
    def atlas(self) -> BootstrappedAtlas:
        """Return the bootstrapped atlas bundle."""
        if self._atlas is None:
            raise OrchestratorError("Orchestrator is not initialized")
        return self._atlas

    @property
    def last_startup(self) -> StartupReport | None:
        """Return the most recent :class:`StartupReport` (or ``None``)."""
        return self._last_startup

    @property
    def last_shutdown(self) -> ShutdownReport | None:
        """Return the most recent :class:`ShutdownReport` (or ``None``)."""
        return self._last_shutdown

    @property
    def started_at(self) -> datetime | None:
        """Return when the orchestrator was initialized (or ``None``)."""
        if self._atlas is None:
            return None
        return self._atlas.started_at

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_atlas(self) -> BootstrappedAtlas:
        if self._atlas is None or self._state is not OrchestratorState.RUNNING:
            raise OrchestratorError(
                f"Orchestrator is not running (state={self._state.value})"
            )
        return self._atlas

    def _require_health_monitor(self) -> HealthMonitor:
        atlas = self._require_atlas()
        monitor = atlas.container.get_optional("health")
        if monitor is None:
            monitor = HealthMonitor(atlas.container)
        return monitor

    def _require_runtime(self) -> Any:
        atlas = self._require_atlas()
        runtime = atlas.container.get_optional("runtime")
        if runtime is None:
            raise OrchestratorError("Runtime is not registered")
        return runtime

    def __repr__(self) -> str:
        return f"<Orchestrator state={self._state.value!r}>"


__all__ = ["Orchestrator", "OrchestratorError", "OrchestratorState"]
