"""Diagnostics collector for the integrated Atlas system.

The :class:`DiagnosticsCollector` produces a single
:class:`DiagnosticsReport` snapshot that captures everything an operator
needs to understand the state of the running Atlas instance:

* startup time and uptime
* loaded providers / tools / skills / workflows / agents (counts and names)
* memory and knowledge statistics
* runtime statistics (executions observed, completed, failed)
* configuration summary
* container inventory (registered vs. initialized services)

Diagnostics are read-only. The collector never mutates any subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.integration.container import DIContainer


@dataclass(frozen=True)
class DiagnosticsReport:
    """Point-in-time diagnostics snapshot.

    Attributes:
        timestamp: When the report was generated.
        started_at: When the Atlas instance was started.
        uptime_seconds: Seconds since startup.
        startup_time_seconds: How long the startup sequence took.
        providers: List of loaded provider names.
        tools: List of loaded tool names.
        skills: List of loaded skill names.
        workflows: List of loaded workflow ids.
        agents: List of loaded agent names.
        memory: Memory engine statistics.
        knowledge: Knowledge engine statistics.
        runtime: Runtime engine statistics.
        config: Configuration summary (key subset).
        container: Container inventory (registered + initialized services).
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    uptime_seconds: float = 0.0
    startup_time_seconds: float = 0.0
    providers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    container: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict representation (for JSON export)."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_seconds": self.uptime_seconds,
            "startup_time_seconds": self.startup_time_seconds,
            "providers": list(self.providers),
            "tools": list(self.tools),
            "skills": list(self.skills),
            "workflows": list(self.workflows),
            "agents": list(self.agents),
            "memory": dict(self.memory),
            "knowledge": dict(self.knowledge),
            "runtime": dict(self.runtime),
            "config": dict(self.config),
            "container": dict(self.container),
        }


class DiagnosticsCollector:
    """Produces :class:`DiagnosticsReport` snapshots on demand.

    Parameters:
        container: The :class:`DIContainer` to pull subsystems from.
        started_at: When the Atlas instance was started. Defaults to now.
        startup_time_seconds: How long the startup sequence took.
    """

    def __init__(
        self,
        container: DIContainer,
        started_at: datetime | None = None,
        startup_time_seconds: float = 0.0,
    ) -> None:
        self.container = container
        self.started_at = started_at or datetime.now(UTC)
        self.startup_time_seconds = startup_time_seconds
        self.logger = get_logger("integration.diagnostics")

    def snapshot(self) -> DiagnosticsReport:
        """Produce a :class:`DiagnosticsReport` reflecting the current state."""
        now = datetime.now(UTC)
        uptime = (now - self.started_at).total_seconds()
        return DiagnosticsReport(
            timestamp=now,
            started_at=self.started_at,
            uptime_seconds=uptime,
            startup_time_seconds=self.startup_time_seconds,
            providers=self._provider_names(),
            tools=self._tool_names(),
            skills=self._skill_names(),
            workflows=self._workflow_ids(),
            agents=self._agent_names(),
            memory=self._memory_stats(),
            knowledge=self._knowledge_stats(),
            runtime=self._runtime_stats(),
            config=self._config_summary(),
            container=self._container_inventory(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the latest snapshot as a flat dict."""
        return self.snapshot().to_dict()

    # ------------------------------------------------------------------
    # Per-subsystem collectors
    # ------------------------------------------------------------------

    def _provider_names(self) -> list[str]:
        providers = self.container.get_optional("providers")
        if providers is None:
            return []
        registry = getattr(providers, "registry", None)
        if registry is None:
            return []
        names_fn = getattr(registry, "names", None)
        return list(names_fn()) if callable(names_fn) else []

    def _tool_names(self) -> list[str]:
        tools = self.container.get_optional("tools")
        if tools is None:
            return []
        registry = getattr(tools, "registry", None)
        if registry is None:
            return []
        names_fn = getattr(registry, "names", None)
        return list(names_fn()) if callable(names_fn) else []

    def _skill_names(self) -> list[str]:
        skills = self.container.get_optional("skills")
        if skills is None:
            return []
        names_fn = getattr(skills, "names", None)
        if callable(names_fn):
            return list(names_fn())
        all_fn = getattr(skills, "all", None)
        if callable(all_fn):
            items = all_fn()
            return sorted(getattr(i, "name", "") for i in items)
        return []

    def _workflow_ids(self) -> list[str]:
        workflows = self.container.get_optional("workflows")
        if workflows is None:
            return []
        registry = getattr(workflows, "registry", None)
        if registry is None:
            return []
        names_fn = getattr(registry, "names", None)
        return list(names_fn()) if callable(names_fn) else []

    def _agent_names(self) -> list[str]:
        agents = self.container.get_optional("agents")
        if agents is None:
            return []
        agent_list = getattr(agents, "agents", None) or getattr(agents, "all", None)
        if callable(agent_list):
            agent_list = agent_list()
        if agent_list is None:
            return []
        return sorted(getattr(a, "name", "") for a in agent_list)

    def _memory_stats(self) -> dict[str, Any]:
        memory = self.container.get_optional("memory")
        if memory is None:
            return {}
        stats: dict[str, Any] = {"stores": []}
        for attr in ("working", "episodic", "semantic", "procedural", "reflection"):
            store = getattr(memory, attr, None)
            if store is None:
                continue
            count = len(store) if hasattr(store, "__len__") else 0
            stats["stores"].append({"name": attr, "count": count})
        return stats

    def _knowledge_stats(self) -> dict[str, Any]:
        knowledge = self.container.get_optional("knowledge")
        if knowledge is None:
            return {}
        count_fn = getattr(knowledge, "count", None)
        count = count_fn() if callable(count_fn) else 0
        list_fn = getattr(knowledge, "list_documents", None)
        docs = list_fn() if callable(list_fn) else []
        return {
            "documents": count,
            "document_ids": [getattr(d, "id", "") for d in docs][:20],
        }

    def _runtime_stats(self) -> dict[str, Any]:
        runtime = self.container.get_optional("runtime")
        if runtime is None:
            return {}
        health_fn = getattr(runtime, "health", None)
        rt_health = health_fn() if callable(health_fn) else {}
        if not isinstance(rt_health, dict):
            rt_health = {}
        live = getattr(runtime, "live_executions", None)
        live_count = len(live()) if callable(live) else 0
        return {
            "health": rt_health,
            "live_executions": live_count,
            "queue_depth": rt_health.get("queue_depth", 0),
        }

    def _config_summary(self) -> dict[str, Any]:
        config = self.container.get_optional("config")
        if config is None:
            return {}
        data = getattr(config, "data", None)
        if data is None and isinstance(config, dict):
            data = config
        if not isinstance(data, dict):
            return {}
        # Surface top-level keys only to avoid leaking secrets.
        return {key: type(value).__name__ for key, value in data.items()}

    def _container_inventory(self) -> dict[str, Any]:
        return {
            "registered": self.container.names(),
            "initialized": self.container.initialized(),
            "service_count": len(self.container),
            "initialized_count": len(self.container.initialized()),
        }

    def __repr__(self) -> str:
        return (
            f"<DiagnosticsCollector services={len(self.container)} "
            f"uptime={self.snapshot().uptime_seconds:.1f}s>"
        )


__all__ = ["DiagnosticsCollector", "DiagnosticsReport"]
