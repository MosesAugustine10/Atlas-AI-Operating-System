"""Health monitoring for the integrated Atlas system.

The :class:`HealthMonitor` aggregates per-subsystem health signals into
a single :class:`HealthReport`. It is a read-only facade: it pulls data
from the subsystems that the container has wired into it, and it never
mutates them.

Each subsystem contributes a :class:`SubsystemHealth` record with:

* ``name`` — the subsystem identifier.
* ``status`` — ``"healthy"``, ``"degraded"``, ``"unhealthy"``, or
  ``"unknown"`` (when the subsystem is not registered).
* ``detail`` — a short human-readable string (e.g. ``"9 online"``).
* ``metrics`` — a free-form dict of subsystem-specific metrics.

The overall :class:`HealthReport` rolls up every subsystem status into
a single ``overall`` status: if any subsystem is ``"unhealthy"`` the
overall is ``"unhealthy"``; if any is ``"degraded"`` the overall is
``"degraded"``; otherwise it is ``"healthy"``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.integration.container import DIContainer


class HealthStatus(enum.StrEnum):
    """Roll-up health statuses.

    Attributes:
        HEALTHY: All subsystems report healthy.
        DEGRADED: At least one subsystem is degraded; none unhealthy.
        UNHEALTHY: At least one subsystem is unhealthy.
        UNKNOWN: The subsystem is not registered or has no signal.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


#: Status severity for roll-up. Higher = worse.
_SEVERITY: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.DEGRADED: 2,
    HealthStatus.UNHEALTHY: 3,
}


@dataclass(frozen=True)
class SubsystemHealth:
    """Health contribution from a single subsystem.

    Attributes:
        name: Subsystem identifier (e.g. ``"memory"``, ``"runtime"``).
        status: The :class:`HealthStatus` for this subsystem.
        detail: Short human-readable description.
        metrics: Free-form subsystem-specific metrics.
    """

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthReport:
    """Aggregate health snapshot across every Atlas subsystem.

    Attributes:
        timestamp: When the report was generated.
        overall: The roll-up :class:`HealthStatus`.
        subsystems: Mapping of subsystem name -> :class:`SubsystemHealth`.
    """

    timestamp: datetime
    overall: HealthStatus = HealthStatus.UNKNOWN
    subsystems: dict[str, SubsystemHealth] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Return ``True`` if the overall status is healthy."""
        return self.overall is HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict representation (for logging / JSON export)."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall": self.overall.value,
            "subsystems": {
                name: {
                    "status": sub.status.value,
                    "detail": sub.detail,
                    "metrics": dict(sub.metrics),
                }
                for name, sub in self.subsystems.items()
            },
        }


class HealthMonitor:
    """Aggregates per-subsystem health into a :class:`HealthReport`.

    Parameters:
        container: The :class:`DIContainer` to pull subsystems from.
    """

    def __init__(self, container: DIContainer) -> None:
        self.container = container
        self.logger = get_logger("integration.health")

    def snapshot(self) -> HealthReport:
        """Produce a :class:`HealthReport` reflecting the current state."""
        subsystems: dict[str, SubsystemHealth] = {}
        for name in _SUBSYSTEM_CHECKS:
            check = _SUBSYSTEM_CHECKS[name]
            try:
                subsystems[name] = check(self.container)
            except Exception as exc:  # noqa: BLE001 — never crash a snapshot
                self.logger.warning("Health check for %s raised: %s", name, exc)
                subsystems[name] = SubsystemHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    detail=f"check_error: {exc}",
                )
        overall = _roll_up(subsystems)
        return HealthReport(
            timestamp=datetime.now(UTC),
            overall=overall,
            subsystems=subsystems,
        )

    def is_healthy(self) -> bool:
        """Return ``True`` if the latest snapshot is overall healthy."""
        return self.snapshot().is_healthy()

    def to_dict(self) -> dict[str, Any]:
        """Return the latest snapshot as a flat dict."""
        return self.snapshot().to_dict()

    def __repr__(self) -> str:
        return f"<HealthMonitor overall={self.snapshot().overall.value!r}>"


# ---------------------------------------------------------------------------
# Per-subsystem checks
# ---------------------------------------------------------------------------


def _check_config(container: DIContainer) -> SubsystemHealth:
    config = container.get_optional("config")
    if config is None:
        return SubsystemHealth(name="config", status=HealthStatus.UNKNOWN)
    data = getattr(config, "data", None)
    if data is None and isinstance(config, dict):
        data = config
    return SubsystemHealth(
        name="config",
        status=HealthStatus.HEALTHY,
        detail="loaded" if data else "empty",
        metrics={"keys": len(data) if isinstance(data, dict) else 0},
    )


def _check_memory(container: DIContainer) -> SubsystemHealth:
    memory = container.get_optional("memory")
    if memory is None:
        return SubsystemHealth(name="memory", status=HealthStatus.UNKNOWN)
    stores = []
    for attr in ("working", "episodic", "semantic", "procedural", "reflection"):
        if getattr(memory, attr, None) is not None:
            stores.append(attr)
    return SubsystemHealth(
        name="memory",
        status=HealthStatus.HEALTHY,
        detail=f"{len(stores)} stores",
        metrics={"stores": stores},
    )


def _check_knowledge(container: DIContainer) -> SubsystemHealth:
    knowledge = container.get_optional("knowledge")
    if knowledge is None:
        return SubsystemHealth(name="knowledge", status=HealthStatus.UNKNOWN)
    count_fn = getattr(knowledge, "count", None)
    count = count_fn() if callable(count_fn) else 0
    return SubsystemHealth(
        name="knowledge",
        status=HealthStatus.HEALTHY,
        detail=f"{count} documents",
        metrics={"documents": count},
    )


def _check_providers(container: DIContainer) -> SubsystemHealth:
    providers = container.get_optional("providers")
    if providers is None:
        return SubsystemHealth(name="providers", status=HealthStatus.UNKNOWN)
    registry = getattr(providers, "registry", None)
    count = len(registry) if registry is not None else 0
    return SubsystemHealth(
        name="providers",
        status=HealthStatus.HEALTHY if count > 0 else HealthStatus.DEGRADED,
        detail=f"{count} online",
        metrics={"count": count},
    )


def _check_tools(container: DIContainer) -> SubsystemHealth:
    tools = container.get_optional("tools")
    if tools is None:
        return SubsystemHealth(name="tools", status=HealthStatus.UNKNOWN)
    registry = getattr(tools, "registry", None)
    count = len(registry) if registry is not None else 0
    return SubsystemHealth(
        name="tools",
        status=HealthStatus.HEALTHY if count > 0 else HealthStatus.DEGRADED,
        detail=f"{count} loaded",
        metrics={"count": count},
    )


def _check_agents(container: DIContainer) -> SubsystemHealth:
    agents = container.get_optional("agents")
    if agents is None:
        return SubsystemHealth(name="agents", status=HealthStatus.UNKNOWN)
    # The agent manager may be the kernel's Router (with ``agents`` list)
    # or a future AgentManager.
    agent_list = getattr(agents, "agents", None) or getattr(agents, "all", None)
    if callable(agent_list):
        agent_list = agent_list()
    count = len(agent_list) if agent_list is not None else 0
    return SubsystemHealth(
        name="agents",
        status=HealthStatus.HEALTHY if count > 0 else HealthStatus.DEGRADED,
        detail=f"{count} ready",
        metrics={"count": count},
    )


def _check_skills(container: DIContainer) -> SubsystemHealth:
    skills = container.get_optional("skills")
    if skills is None:
        return SubsystemHealth(name="skills", status=HealthStatus.UNKNOWN)
    count_fn = getattr(skills, "count", None)
    if callable(count_fn):
        count = count_fn()
    else:
        all_fn = getattr(skills, "all", None)
        count = len(all_fn()) if callable(all_fn) else 0
    return SubsystemHealth(
        name="skills",
        status=HealthStatus.HEALTHY if count > 0 else HealthStatus.DEGRADED,
        detail=f"{count} installed",
        metrics={"count": count},
    )


def _check_workflows(container: DIContainer) -> SubsystemHealth:
    workflows = container.get_optional("workflows")
    if workflows is None:
        return SubsystemHealth(name="workflows", status=HealthStatus.UNKNOWN)
    registry = getattr(workflows, "registry", None)
    count = len(registry) if registry is not None else 0
    return SubsystemHealth(
        name="workflows",
        status=HealthStatus.HEALTHY,
        detail="ready" if count == 0 else f"{count} registered",
        metrics={"count": count},
    )


def _check_runtime(container: DIContainer) -> SubsystemHealth:
    runtime = container.get_optional("runtime")
    if runtime is None:
        return SubsystemHealth(name="runtime", status=HealthStatus.UNKNOWN)
    # Prefer the runtime's own health() if it has one.
    health_fn = getattr(runtime, "health", None)
    if callable(health_fn):
        rt_health = health_fn()
        status_str = (
            rt_health.get("status", "healthy")
            if isinstance(rt_health, dict)
            else "healthy"
        )
        try:
            status = HealthStatus(status_str)
        except ValueError:
            status = HealthStatus.HEALTHY
        return SubsystemHealth(
            name="runtime",
            status=status,
            detail=status_str,
            metrics=rt_health if isinstance(rt_health, dict) else {},
        )
    return SubsystemHealth(
        name="runtime",
        status=HealthStatus.HEALTHY,
        detail="running",
    )


def _check_telemetry(container: DIContainer) -> SubsystemHealth:
    telemetry = container.get_optional("telemetry")
    if telemetry is None:
        return SubsystemHealth(name="telemetry", status=HealthStatus.UNKNOWN)
    summary_fn = getattr(telemetry, "summary", None)
    summary = summary_fn() if callable(summary_fn) else {}
    observed = summary.get("executions_observed", 0) if isinstance(summary, dict) else 0
    return SubsystemHealth(
        name="telemetry",
        status=HealthStatus.HEALTHY,
        detail=f"{observed} executions observed",
        metrics=summary if isinstance(summary, dict) else {},
    )


_SUBSYSTEM_CHECKS: dict[str, Any] = {
    "config": _check_config,
    "memory": _check_memory,
    "knowledge": _check_knowledge,
    "providers": _check_providers,
    "tools": _check_tools,
    "agents": _check_agents,
    "skills": _check_skills,
    "workflows": _check_workflows,
    "runtime": _check_runtime,
    "telemetry": _check_telemetry,
}


def _roll_up(subsystems: dict[str, SubsystemHealth]) -> HealthStatus:
    """Combine per-subsystem statuses into a single overall status."""
    if not subsystems:
        return HealthStatus.UNKNOWN
    worst = HealthStatus.HEALTHY
    for sub in subsystems.values():
        if _SEVERITY[sub.status] > _SEVERITY[worst]:
            worst = sub.status
    return worst


__all__ = [
    "HealthMonitor",
    "HealthReport",
    "HealthStatus",
    "SubsystemHealth",
]
