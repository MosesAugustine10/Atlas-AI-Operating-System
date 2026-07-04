"""Shutdown manager — graceful teardown in reverse dependency order.

The :class:`ShutdownManager` walks every initialized service in reverse
canonical :class:`LifecyclePhase` order and invokes its ``shutdown()``
method if it has one. Services that do not implement ``shutdown()`` are
skipped silently. Any service that raises during shutdown is logged and
the manager continues with the next service.

The shutdown order is the reverse of :data:`STARTUP_ORDER` so that
dependent services are torn down before their dependencies:

    health -> telemetry -> runtime -> workflows -> agents -> skills ->
    tools -> providers -> knowledge -> memory -> logger -> config

Like the startup manager, the shutdown manager records timing for each
step and produces a :class:`ShutdownReport`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.integration.container import DIContainer
from atlas.integration.dependency import (
    SHUTDOWN_ORDER,
    LifecyclePhase,
)


@dataclass(frozen=True)
class ShutdownStepResult:
    """The outcome of shutting down a single service.

    Attributes:
        name: The service name.
        phase: The :class:`LifecyclePhase` the service belongs to.
        success: Whether the service shut down without error.
        duration_seconds: How long shutdown took.
        skipped: ``True`` if the service has no ``shutdown()`` method.
        error: Error message if ``success`` is ``False``.
    """

    name: str
    phase: LifecyclePhase
    success: bool
    duration_seconds: float
    skipped: bool = False
    error: str | None = None


@dataclass(frozen=True)
class ShutdownReport:
    """The outcome of a full shutdown sequence.

    Attributes:
        started_at: When the shutdown sequence began.
        completed_at: When the shutdown sequence finished.
        duration_seconds: Total wall time of the shutdown sequence.
        steps: Ordered list of :class:`ShutdownStepResult` records.
        success: ``True`` if every non-skipped step succeeded.
        failed_services: Names of services that failed to shut down.
    """

    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    steps: list[ShutdownStepResult] = field(default_factory=list)
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
                    "skipped": s.skipped,
                    "duration_seconds": s.duration_seconds,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }


class ShutdownManager:
    """Walks every initialized service in reverse phase order.

    Parameters:
        container: The :class:`DIContainer` to drive.
        strict: If ``True``, any service that fails to shut down aborts
            the entire shutdown. Defaults to ``False`` so a single bad
            shutdown does not prevent the rest from running.
    """

    def __init__(
        self,
        container: DIContainer,
        strict: bool = False,
    ) -> None:
        self.container = container
        self.strict = strict
        self.logger = get_logger("integration.shutdown")

    def shutdown(self) -> ShutdownReport:
        """Run the full shutdown sequence and return a :class:`ShutdownReport`."""
        started_at = datetime.now(UTC)
        steps: list[ShutdownStepResult] = []
        failed: list[str] = []
        # Only shut down services that have actually been instantiated.
        initialized = set(self.container.initialized())
        for phase in SHUTDOWN_ORDER:
            for descriptor in self.container.descriptors_by_phase(phase):
                if descriptor.name not in initialized:
                    continue
                step = self._shutdown_service(descriptor.name, descriptor.phase)
                steps.append(step)
                if not step.success and not step.skipped:
                    failed.append(descriptor.name)
                    if self.strict:
                        completed_at = datetime.now(UTC)
                        return ShutdownReport(
                            started_at=started_at,
                            completed_at=completed_at,
                            duration_seconds=(
                                completed_at - started_at
                            ).total_seconds(),
                            steps=steps,
                            success=False,
                            failed_services=failed,
                        )
        # Drop cached instances so the container is unusable after shutdown.
        self.container.clear()
        completed_at = datetime.now(UTC)
        report = ShutdownReport(
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            steps=steps,
            success=not failed,
            failed_services=failed,
        )
        self.logger.info(
            "Shutdown %s in %.3fs (%d services, %d failed)",
            "succeeded" if report.success else "completed with errors",
            report.duration_seconds,
            len(steps),
            len(failed),
        )
        return report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _shutdown_service(self, name: str, phase: LifecyclePhase) -> ShutdownStepResult:
        """Invoke ``shutdown()`` on a single service if it has one."""
        start = datetime.now(UTC)
        try:
            instance = self.container.get_optional(name)
        except Exception as exc:  # noqa: BLE001
            duration = (datetime.now(UTC) - start).total_seconds()
            return ShutdownStepResult(
                name=name,
                phase=phase,
                success=False,
                duration_seconds=duration,
                error=f"resolve_failed: {exc}",
            )
        if instance is None:
            return ShutdownStepResult(
                name=name,
                phase=phase,
                success=True,
                duration_seconds=0.0,
                skipped=True,
            )
        shutdown_fn = getattr(instance, "shutdown", None)
        if not callable(shutdown_fn):
            return ShutdownStepResult(
                name=name,
                phase=phase,
                success=True,
                duration_seconds=0.0,
                skipped=True,
            )
        try:
            shutdown_fn()
        except Exception as exc:  # noqa: BLE001
            duration = (datetime.now(UTC) - start).total_seconds()
            self.logger.error(
                "Failed to shut down %s (phase=%s): %s", name, phase.value, exc
            )
            return ShutdownStepResult(
                name=name,
                phase=phase,
                success=False,
                duration_seconds=duration,
                error=f"{type(exc).__name__}: {exc}",
            )
        duration = (datetime.now(UTC) - start).total_seconds()
        self.logger.debug(
            "Shut down %s (phase=%s) in %.3fs",
            name,
            phase.value,
            duration,
        )
        return ShutdownStepResult(
            name=name,
            phase=phase,
            success=True,
            duration_seconds=duration,
        )

    def __repr__(self) -> str:
        return f"<ShutdownManager strict={self.strict} services={len(self.container)}>"


__all__ = ["ShutdownManager", "ShutdownReport", "ShutdownStepResult"]
