"""Startup manager — ordered initialization of every Atlas subsystem.

The :class:`StartupManager` walks every registered service in canonical
:class:`LifecyclePhase` order and forces it to be instantiated by the
container. This guarantees that:

* Every singleton is constructed exactly once.
* The construction order matches the dependency order (config first,
  logger second, memory third, etc.).
* Any service that fails to construct is reported and either aborts the
  startup (``strict=True``) or is skipped (``strict=False``).

The manager also records timing for each phase and produces a
:class:`StartupReport` at the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.integration.container import DIContainer
from atlas.integration.dependency import (
    STARTUP_ORDER,
    LifecyclePhase,
)


@dataclass(frozen=True)
class StartupStepResult:
    """The outcome of starting a single service.

    Attributes:
        name: The service name.
        phase: The :class:`LifecyclePhase` the service belongs to.
        success: Whether the service was instantiated without error.
        duration_seconds: How long instantiation took.
        error: Error message if ``success`` is ``False``.
    """

    name: str
    phase: LifecyclePhase
    success: bool
    duration_seconds: float
    error: str | None = None


@dataclass(frozen=True)
class StartupReport:
    """The outcome of a full startup sequence.

    Attributes:
        started_at: When the startup sequence began.
        completed_at: When the startup sequence finished.
        duration_seconds: Total wall time of the startup sequence.
        steps: Ordered list of :class:`StartupStepResult` records.
        success: ``True`` if every step succeeded.
        failed_services: Names of services that failed to start.
    """

    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    steps: list[StartupStepResult] = field(default_factory=list)
    success: bool = True
    failed_services: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict representation."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "failed_services": list(self.failed_services),
            "steps": [
                {
                    "name": s.name,
                    "phase": s.phase.value,
                    "success": s.success,
                    "duration_seconds": s.duration_seconds,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }


class StartupManager:
    """Walks every registered service in canonical phase order.

    Parameters:
        container: The :class:`DIContainer` to drive.
        strict: If ``True`` (default), any service that fails to
            instantiate aborts the entire startup. If ``False``, the
            manager logs the failure and continues.
    """

    def __init__(
        self,
        container: DIContainer,
        strict: bool = True,
    ) -> None:
        self.container = container
        self.strict = strict
        self.logger = get_logger("integration.startup")

    def start(self) -> StartupReport:
        """Run the full startup sequence and return a :class:`StartupReport`."""
        started_at = datetime.now(UTC)
        steps: list[StartupStepResult] = []
        failed: list[str] = []
        for phase in STARTUP_ORDER:
            for descriptor in self.container.descriptors_by_phase(phase):
                step = self._start_service(descriptor.name, descriptor.phase)
                steps.append(step)
                if not step.success:
                    failed.append(descriptor.name)
                    if self.strict:
                        completed_at = datetime.now(UTC)
                        return StartupReport(
                            started_at=started_at,
                            completed_at=completed_at,
                            duration_seconds=(
                                completed_at - started_at
                            ).total_seconds(),
                            steps=steps,
                            success=False,
                            failed_services=failed,
                        )
        completed_at = datetime.now(UTC)
        report = StartupReport(
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            steps=steps,
            success=not failed,
            failed_services=failed,
        )
        self.logger.info(
            "Startup %s in %.3fs (%d services, %d failed)",
            "succeeded" if report.success else "failed",
            report.duration_seconds,
            len(steps),
            len(failed),
        )
        return report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_service(self, name: str, phase: LifecyclePhase) -> StartupStepResult:
        """Force-instantiate a single service and record the outcome."""
        start = datetime.now(UTC)
        try:
            self.container.get(name)
        except Exception as exc:  # noqa: BLE001 — capture every failure
            duration = (datetime.now(UTC) - start).total_seconds()
            self.logger.error(
                "Failed to start %s (phase=%s): %s", name, phase.value, exc
            )
            return StartupStepResult(
                name=name,
                phase=phase,
                success=False,
                duration_seconds=duration,
                error=f"{type(exc).__name__}: {exc}",
            )
        duration = (datetime.now(UTC) - start).total_seconds()
        self.logger.debug(
            "Started %s (phase=%s) in %.3fs",
            name,
            phase.value,
            duration,
        )
        return StartupStepResult(
            name=name,
            phase=phase,
            success=True,
            duration_seconds=duration,
        )

    def __repr__(self) -> str:
        return f"<StartupManager strict={self.strict} services={len(self.container)}>"


__all__ = ["StartupManager", "StartupReport", "StartupStepResult"]
