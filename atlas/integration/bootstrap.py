"""Bootstrap — load config, build container, wire dependencies, start Atlas.

The :class:`Bootstrap` is the single entry point that turns a raw
configuration into a fully-running Atlas instance. It:

1. Loads the configuration (from a path, a dict, or a :class:`Config`).
2. Builds an empty :class:`DIContainer`.
3. Uses :class:`Wiring` to register every Atlas subsystem.
4. Runs the :class:`StartupManager` to instantiate every service in order.
5. Runs an initial health check via :class:`HealthMonitor`.
6. Returns a :class:`BootstrappedAtlas` bundle holding the container,
   startup report, and health report.

The bootstrapped bundle is what the :class:`Orchestrator` wraps; users
should never call :class:`Bootstrap` directly outside of tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from atlas.core.config import Config
from atlas.core.logger import get_logger
from atlas.integration.container import DIContainer
from atlas.integration.dependency import LifecyclePhase
from atlas.integration.health import HealthMonitor, HealthReport
from atlas.integration.startup import StartupManager, StartupReport
from atlas.integration.wiring import Wiring


@dataclass(frozen=True)
class BootstrappedAtlas:
    """The bundle returned by :class:`Bootstrap`.

    Attributes:
        container: The wired and started :class:`DIContainer`.
        startup_report: The :class:`StartupReport` produced by the
            :class:`StartupManager`.
        health_report: The :class:`HealthReport` produced by the initial
            health check.
        started_at: When the bootstrap completed.
        config: The loaded configuration (raw config object).
    """

    container: DIContainer
    startup_report: StartupReport
    health_report: HealthReport
    started_at: datetime
    config: Any = None


class Bootstrap:
    """Turns a configuration into a fully-running Atlas instance.

    Parameters:
        config: A :class:`Config`, a dict, a path string, or ``None``
            (loads the default ``atlas/configs/atlas.yaml``).
        container: Optional pre-built container. If omitted, a fresh one
            is created.
        strict: If ``True`` (default), any startup failure aborts the
            bootstrap.
    """

    def __init__(
        self,
        config: Config | dict[str, Any] | str | None = None,
        container: DIContainer | None = None,
        strict: bool = True,
    ) -> None:
        self.config_input = config
        self.container = container if container is not None else DIContainer()
        self.strict = strict
        self.logger = get_logger("integration.bootstrap")

    def run(self) -> BootstrappedAtlas:
        """Run the full bootstrap sequence and return a :class:`BootstrappedAtlas`.

        Raises:
            RuntimeError: If startup fails and ``strict=True``.
        """
        started = datetime.now(UTC)
        self.logger.info("Bootstrapping Atlas...")

        # 1. Resolve the config into a concrete object.
        config_obj = self._resolve_config(self.config_input)

        # 2. Wire every subsystem into the container.
        Wiring(self.container).wire_all(config=config_obj)

        # 3. Run the startup manager to instantiate every service in order.
        startup_manager = StartupManager(self.container, strict=self.strict)
        startup_report = startup_manager.start()
        if not startup_report.success and self.strict:
            raise RuntimeError(
                f"Atlas bootstrap failed: {len(startup_report.failed_services)} "
                f"service(s) failed to start: {startup_report.failed_services}"
            )

        # 4. Register the diagnostics collector with startup timing.
        startup_duration = startup_report.duration_seconds
        from atlas.integration.diagnostics import DiagnosticsCollector

        self.container.register_value(
            "diagnostics",
            DiagnosticsCollector(
                self.container,
                started_at=started,
                startup_time_seconds=startup_duration,
            ),
            phase=LifecyclePhase.HEALTH,
        )

        # 5. Run an initial health check.
        health_monitor = self.container.get_optional("health")
        if health_monitor is None:
            # Construct on-the-fly if not registered (defensive).
            health_monitor = HealthMonitor(self.container)
        health_report = health_monitor.snapshot()

        self.logger.info(
            "Atlas bootstrapped in %.3fs — overall health: %s",
            startup_duration,
            health_report.overall.value,
        )

        return BootstrappedAtlas(
            container=self.container,
            startup_report=startup_report,
            health_report=health_report,
            started_at=started,
            config=config_obj,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_config(
        self, config: Config | dict[str, Any] | str | None
    ) -> Config | dict[str, Any]:
        """Normalise the config input into a concrete object."""
        if config is None:
            return Config()
        if isinstance(config, Config):
            return config
        if isinstance(config, dict):
            return config
        if isinstance(config, str):
            return Config(config)
        # Fall back to default for unknown types.
        return Config()


__all__ = ["BootstrappedAtlas", "Bootstrap"]
