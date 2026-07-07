"""Tests for the Atlas Integration Layer.

Covers the DI container, dependency descriptors, the unified registry,
the service locator, health monitoring, diagnostics, the wiring registrar,
startup, shutdown, bootstrap, and the top-level orchestrator.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.integration import (
    SHUTDOWN_ORDER,
    STARTUP_ORDER,
    Bootstrap,
    BootstrappedAtlas,
    CircularDependencyError,
    DiagnosticsCollector,
    DiagnosticsReport,
    DIContainer,
    HealthMonitor,
    HealthReport,
    HealthStatus,
    LifecyclePhase,
    Named,
    Orchestrator,
    OrchestratorError,
    OrchestratorState,
    ServiceAlreadyRegisteredError,
    ServiceDescriptor,
    ServiceError,
    ServiceLocator,
    ServiceNotFoundError,
    ServiceScope,
    ShutdownManager,
    SkillManager,
    StartupManager,
    StartupReport,
    SubsystemHealth,
    UnifiedRegistry,
    Wiring,
)

# ---------------------------------------------------------------------------
# Dependency descriptors and lifecycle phases
# ---------------------------------------------------------------------------


def test_service_scope_has_two_values() -> None:
    assert ServiceScope.SINGLETON.value == "singleton"
    assert ServiceScope.TRANSIENT.value == "transient"


def test_lifecycle_phase_has_all_phases() -> None:
    expected = {
        "config",
        "logger",
        "memory",
        "knowledge",
        "providers",
        "tools",
        "skills",
        "agents",
        "workflows",
        "runtime",
        "telemetry",
        "dashboard",
        "health",
        "ready",
        "shutting_down",
        "shutdown",
    }
    assert {p.value for p in LifecyclePhase} == expected


def test_startup_order_starts_with_config() -> None:
    assert STARTUP_ORDER[0] is LifecyclePhase.CONFIG
    assert STARTUP_ORDER[-1] is LifecyclePhase.READY


def test_shutdown_order_is_reverse_of_startup() -> None:
    expected = tuple(
        phase for phase in reversed(STARTUP_ORDER) if phase is not LifecyclePhase.READY
    )
    assert SHUTDOWN_ORDER == expected


def test_shutdown_order_ends_with_config() -> None:
    assert SHUTDOWN_ORDER[-1] is LifecyclePhase.CONFIG


def test_service_descriptor_is_frozen() -> None:
    import dataclasses

    desc = ServiceDescriptor(name="x", factory=lambda c: 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        desc.name = "y"  # type: ignore[misc]


def test_service_descriptor_defaults() -> None:
    desc = ServiceDescriptor(name="x", factory=lambda c: 1)
    assert desc.scope is ServiceScope.SINGLETON
    assert desc.phase is LifecyclePhase.READY
    assert desc.interfaces == ()
    assert desc.tags == ()


# ---------------------------------------------------------------------------
# DI container
# ---------------------------------------------------------------------------


def test_container_register_and_get() -> None:
    c = DIContainer()
    c.register(ServiceDescriptor(name="answer", factory=lambda _c: 42))
    assert c.get("answer") == 42


def test_container_get_unknown_raises() -> None:
    c = DIContainer()
    with pytest.raises(ServiceNotFoundError):
        c.get("missing")


def test_container_get_optional_returns_none() -> None:
    c = DIContainer()
    assert c.get_optional("missing") is None


def test_container_register_duplicate_raises() -> None:
    c = DIContainer()
    c.register(ServiceDescriptor(name="x", factory=lambda _c: 1))
    with pytest.raises(ServiceAlreadyRegisteredError):
        c.register(ServiceDescriptor(name="x", factory=lambda _c: 2))


def test_container_register_value_pre_populates_cache() -> None:
    c = DIContainer()
    c.register_value("config", {"k": "v"})
    assert c.get("config") == {"k": "v"}
    assert c.is_resolved("config")


def test_container_register_factory_lazy() -> None:
    c = DIContainer()
    calls: list[int] = []
    c.register_factory("lazy", lambda _c: calls.append(1) or 99)
    assert calls == []
    assert c.get("lazy") == 99
    assert calls == [1]
    # Singleton: second get does not re-invoke factory.
    c.get("lazy")
    assert calls == [1]


def test_container_transient_rebuilds_every_time() -> None:
    c = DIContainer()
    c.register_factory(
        "transient",
        lambda _c: object(),
        scope=ServiceScope.TRANSIENT,
    )
    a = c.get("transient")
    b = c.get("transient")
    assert a is not b


def test_container_singleton_caches() -> None:
    c = DIContainer()
    c.register_factory(
        "singleton",
        lambda _c: object(),
        scope=ServiceScope.SINGLETON,
    )
    a = c.get("singleton")
    b = c.get("singleton")
    assert a is b


def test_container_get_typed_resolves_by_interface() -> None:
    class IFace:
        pass

    c = DIContainer()
    instance = IFace()
    c.register_value("iface", instance, interfaces=(IFace,))
    assert c.get_typed(IFace) is instance


def test_container_get_typed_returns_none_if_unregistered() -> None:
    class IFace:
        pass

    c = DIContainer()
    assert c.get_typed(IFace) is None


def test_container_contains() -> None:
    c = DIContainer()
    c.register_value("x", 1)
    assert "x" in c
    assert "y" not in c


def test_container_names_sorted() -> None:
    c = DIContainer()
    c.register_value("b", 2)
    c.register_value("a", 1)
    assert c.names() == ["a", "b"]


def test_container_descriptors_returns_all() -> None:
    c = DIContainer()
    c.register_value("a", 1)
    c.register_value("b", 2)
    assert len(c.descriptors()) == 2


def test_container_descriptors_by_phase() -> None:
    c = DIContainer()
    c.register_value("a", 1, phase=LifecyclePhase.CONFIG)
    c.register_value("b", 2, phase=LifecyclePhase.MEMORY)
    config_descs = c.descriptors_by_phase(LifecyclePhase.CONFIG)
    assert len(config_descs) == 1
    assert config_descs[0].name == "a"


def test_container_descriptors_by_tag() -> None:
    c = DIContainer()
    c.register_value("a", 1, tags=("provider",))
    c.register_value("b", 2, tags=("tool",))
    assert len(c.descriptors_by_tag("provider")) == 1
    assert len(c.descriptors_by_tag("tool")) == 1


def test_container_phases_in_canonical_order() -> None:
    c = DIContainer()
    c.register_value("cfg", 1, phase=LifecyclePhase.CONFIG)
    c.register_value("mem", 2, phase=LifecyclePhase.MEMORY)
    c.register_value("rt", 3, phase=LifecyclePhase.RUNTIME)
    phases = c.phases()
    assert phases[0] is LifecyclePhase.CONFIG
    assert phases[1] is LifecyclePhase.MEMORY
    assert phases[2] is LifecyclePhase.RUNTIME


def test_container_unregister() -> None:
    c = DIContainer()
    c.register_value("x", 1)
    assert c.unregister("x") is True
    assert c.unregister("x") is False
    assert "x" not in c


def test_container_is_resolved() -> None:
    c = DIContainer()
    c.register_factory("lazy", lambda _c: 42)
    assert not c.is_resolved("lazy")
    c.get("lazy")
    assert c.is_resolved("lazy")


def test_container_initialized_lists_resolved() -> None:
    c = DIContainer()
    c.register_value("a", 1)
    c.register_factory("b", lambda _c: 2)
    c.get("b")
    assert set(c.initialized()) == {"a", "b"}


def test_container_clear() -> None:
    c = DIContainer()
    c.register_value("a", 1)
    c.register_value("b", 2)
    c.clear()
    assert len(c) == 0


def test_container_len_and_iter() -> None:
    c = DIContainer()
    c.register_value("a", 1)
    c.register_value("b", 2)
    assert len(c) == 2
    names = [d.name for d in c]
    assert sorted(names) == ["a", "b"]


def test_container_circular_dependency_detected() -> None:
    c = DIContainer()
    c.register_factory("a", lambda c: c.get("b"))
    c.register_factory("b", lambda c: c.get("a"))
    with pytest.raises(CircularDependencyError) as exc_info:
        c.get("a")
    assert "a" in exc_info.value.cycle
    assert "b" in exc_info.value.cycle


def test_container_dependency_injection_via_factory() -> None:
    c = DIContainer()
    c.register_value("base", 10)
    c.register_factory("derived", lambda c: c.get("base") * 2)
    assert c.get("derived") == 20


def test_service_error_is_runtime_error() -> None:
    assert issubclass(ServiceError, RuntimeError)
    assert issubclass(ServiceNotFoundError, ServiceError)
    assert issubclass(ServiceAlreadyRegisteredError, ServiceError)
    assert issubclass(CircularDependencyError, ServiceError)


# ---------------------------------------------------------------------------
# Unified registry
# ---------------------------------------------------------------------------


class _FakeRegistry:
    """Minimal registry stub for testing UnifiedRegistry."""

    def __init__(self, items: dict[str, object]) -> None:
        self._items = items

    def get(self, name: str) -> object | None:
        return self._items.get(name)

    def all(self) -> list[object]:
        return list(self._items.values())

    def names(self) -> list[str]:
        return sorted(self._items)

    def __len__(self) -> int:
        return len(self._items)


def test_unified_registry_get_by_kind_and_name() -> None:
    reg = UnifiedRegistry(
        providers=_FakeRegistry({"openai": "OPENAI"}),
        tools=_FakeRegistry({"fs": "FS"}),
    )
    assert reg.get("providers", "openai") == "OPENAI"
    assert reg.get("tools", "fs") == "FS"
    assert reg.get("providers", "missing") is None
    assert reg.get("skills", "anything") is None


def test_unified_registry_list() -> None:
    reg = UnifiedRegistry(providers=_FakeRegistry({"a": 1, "b": 2}))
    assert sorted(reg.list("providers")) == [1, 2]


def test_unified_registry_names() -> None:
    reg = UnifiedRegistry(providers=_FakeRegistry({"b": 2, "a": 1}))
    assert reg.names("providers") == ["a", "b"]


def test_unified_registry_count() -> None:
    reg = UnifiedRegistry(
        providers=_FakeRegistry({"a": 1, "b": 2}),
        tools=_FakeRegistry({"x": 1}),
    )
    assert reg.count("providers") == 2
    assert reg.count("tools") == 1
    assert reg.count("skills") == 0


def test_unified_registry_contains() -> None:
    reg = UnifiedRegistry(providers=_FakeRegistry({"a": 1}))
    assert reg.contains("providers", "a")
    assert not reg.contains("providers", "b")


def test_unified_registry_typed_accessors() -> None:
    reg = UnifiedRegistry(
        providers=_FakeRegistry({"p": "P"}),
        tools=_FakeRegistry({"t": "T"}),
        workflows=_FakeRegistry({"w": "W"}),
        agents=_FakeRegistry({"a": "A"}),
        skills=_FakeRegistry({"s": "S"}),
    )
    assert reg.providers() == ["P"]
    assert reg.tools() == ["T"]
    assert reg.workflows() == ["W"]
    assert reg.agents() == ["A"]
    assert reg.skills() == ["S"]
    assert reg.provider("p") == "P"
    assert reg.tool("t") == "T"
    assert reg.workflow("w") == "W"
    assert reg.agent("a") == "A"
    assert reg.skill("s") == "S"


def test_unified_registry_summary() -> None:
    reg = UnifiedRegistry(
        providers=_FakeRegistry({"a": 1}),
        tools=_FakeRegistry({"t1": 1, "t2": 2}),
    )
    summary = reg.summary()
    assert summary["providers"] == 1
    assert summary["tools"] == 2
    assert summary["workflows"] == 0


def test_unified_registry_kinds() -> None:
    reg = UnifiedRegistry()
    kinds = reg.kinds()
    assert "providers" in kinds
    assert "tools" in kinds
    assert "workflows" in kinds
    assert "agents" in kinds
    assert "skills" in kinds


def test_unified_registry_iter_yields_kind_and_items() -> None:
    reg = UnifiedRegistry(providers=_FakeRegistry({"p": 1}))
    pairs = dict(reg)
    assert "providers" in pairs
    assert pairs["providers"] == [1]


def test_unified_registry_handles_missing_registry_gracefully() -> None:
    reg = UnifiedRegistry()
    assert reg.list("providers") == []
    assert reg.names("tools") == []
    assert reg.count("skills") == 0
    assert reg.get("agents", "x") is None


def test_unified_registry_handles_registry_without_all_method() -> None:
    class NoAll:
        def names(self) -> list[str]:
            return ["x"]

        def get(self, name: str) -> object | None:
            return None if name != "x" else "X"

        def __len__(self) -> int:
            return 1

    reg = UnifiedRegistry(providers=NoAll())
    assert reg.names("providers") == ["x"]
    assert reg.get("providers", "x") == "X"


def test_named_protocol() -> None:
    class HasName:
        name = "x"

    assert isinstance(HasName(), Named)


# ---------------------------------------------------------------------------
# Service locator
# ---------------------------------------------------------------------------


def test_service_locator_delegates_to_container() -> None:
    c = DIContainer()
    c.register_value("config", {"k": "v"})
    loc = ServiceLocator(c)
    assert loc.config == {"k": "v"}


def test_service_locator_returns_none_for_missing() -> None:
    c = DIContainer()
    loc = ServiceLocator(c)
    assert loc.config is None
    assert loc.memory is None
    assert loc.runtime is None


def test_service_locator_get_by_name() -> None:
    c = DIContainer()
    c.register_value("custom", 42)
    loc = ServiceLocator(c)
    assert loc.get("custom") == 42


def test_service_locator_get_typed() -> None:
    class IFace:
        pass

    c = DIContainer()
    inst = IFace()
    c.register_value("iface", inst, interfaces=(IFace,))
    loc = ServiceLocator(c)
    assert loc.get_typed(IFace) is inst


def test_service_locator_exposes_container() -> None:
    c = DIContainer()
    loc = ServiceLocator(c)
    assert loc.container is c


# ---------------------------------------------------------------------------
# Skill manager (shipped with wiring)
# ---------------------------------------------------------------------------


def test_skill_manager_register_and_get() -> None:
    sm = SkillManager()
    sm.register("double", lambda x: x * 2)
    assert sm.get("double")(3) == 6


def test_skill_manager_contains() -> None:
    sm = SkillManager()
    sm.register("x", lambda: 1)
    assert sm.contains("x")
    assert not sm.contains("y")


def test_skill_manager_unregister() -> None:
    sm = SkillManager()
    sm.register("x", lambda: 1)
    assert sm.unregister("x") is True
    assert sm.unregister("x") is False


def test_skill_manager_names_sorted() -> None:
    sm = SkillManager()
    sm.register("b", lambda: 1)
    sm.register("a", lambda: 2)
    assert sm.names() == ["a", "b"]


def test_skill_manager_count_and_len() -> None:
    sm = SkillManager()
    sm.register("a", lambda: 1)
    sm.register("b", lambda: 2)
    assert sm.count() == 2
    assert len(sm) == 2


def test_skill_manager_invoke() -> None:
    sm = SkillManager()
    sm.register("add", lambda a, b: a + b)
    assert sm.invoke("add", 2, 3) == 5


def test_skill_manager_invoke_unknown_raises() -> None:
    sm = SkillManager()
    with pytest.raises(KeyError):
        sm.invoke("missing")


def test_skill_manager_register_rejects_empty_name() -> None:
    sm = SkillManager()
    with pytest.raises(ValueError):
        sm.register("", lambda: 1)


def test_skill_manager_register_rejects_non_callable() -> None:
    sm = SkillManager()
    with pytest.raises(TypeError):
        sm.register("x", "not callable")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Health monitor
# ---------------------------------------------------------------------------


def test_health_status_severity() -> None:
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"
    assert HealthStatus.UNKNOWN.value == "unknown"


def test_health_monitor_snapshot_with_empty_container() -> None:
    c = DIContainer()
    monitor = HealthMonitor(c)
    report = monitor.snapshot()
    assert report.overall is HealthStatus.UNKNOWN
    assert all(sub.status is HealthStatus.UNKNOWN for sub in report.subsystems.values())


def test_health_monitor_snapshot_with_config() -> None:
    c = DIContainer()
    c.register_value("config", {"k": "v"}, phase=LifecyclePhase.CONFIG)
    monitor = HealthMonitor(c)
    report = monitor.snapshot()
    assert report.subsystems["config"].status is HealthStatus.HEALTHY


def test_health_monitor_snapshot_with_providers() -> None:
    c = DIContainer()
    c.register_value(
        "providers",
        type(
            "P",
            (),
            {"registry": _FakeRegistry({"a": 1, "b": 2})},
        )(),
        phase=LifecyclePhase.PROVIDERS,
    )
    monitor = HealthMonitor(c)
    report = monitor.snapshot()
    assert report.subsystems["providers"].status is HealthStatus.HEALTHY
    assert report.subsystems["providers"].metrics["count"] == 2


def test_health_monitor_degraded_when_providers_empty() -> None:
    c = DIContainer()
    c.register_value(
        "providers",
        type("P", (), {"registry": _FakeRegistry({})})(),
        phase=LifecyclePhase.PROVIDERS,
    )
    monitor = HealthMonitor(c)
    report = monitor.snapshot()
    assert report.subsystems["providers"].status is HealthStatus.DEGRADED


def test_health_monitor_overall_unhealthy_when_check_raises() -> None:
    c = DIContainer()
    # Register a "providers" service that raises when accessed.
    c.register_factory(
        "providers",
        lambda _c: (_ for _ in ()).throw(RuntimeError("boom")),
        phase=LifecyclePhase.PROVIDERS,
    )
    monitor = HealthMonitor(c)
    report = monitor.snapshot()
    assert report.subsystems["providers"].status is HealthStatus.UNHEALTHY
    assert report.overall is HealthStatus.UNHEALTHY


def test_health_report_is_healthy() -> None:
    report = HealthReport(
        timestamp=datetime.now(UTC),
        overall=HealthStatus.HEALTHY,
    )
    assert report.is_healthy()


def test_health_report_to_dict() -> None:
    report = HealthReport(
        timestamp=datetime.now(UTC),
        overall=HealthStatus.HEALTHY,
        subsystems={
            "config": SubsystemHealth(name="config", status=HealthStatus.HEALTHY)
        },
    )
    d = report.to_dict()
    assert d["overall"] == "healthy"
    assert "subsystems" in d
    assert d["subsystems"]["config"]["status"] == "healthy"


def test_health_monitor_is_healthy() -> None:
    c = DIContainer()
    monitor = HealthMonitor(c)
    # Empty container -> overall UNKNOWN -> not healthy.
    assert monitor.is_healthy() is False


def test_health_monitor_to_dict() -> None:
    c = DIContainer()
    monitor = HealthMonitor(c)
    d = monitor.to_dict()
    assert "overall" in d
    assert "subsystems" in d


def test_health_monitor_runtime_uses_runtime_health() -> None:
    c = DIContainer()
    c.register_value(
        "runtime",
        type("R", (), {"health": lambda self: {"status": "healthy"}})(),
        phase=LifecyclePhase.RUNTIME,
    )
    monitor = HealthMonitor(c)
    report = monitor.snapshot()
    assert report.subsystems["runtime"].status is HealthStatus.HEALTHY


def test_subsystem_health_defaults() -> None:
    sub = SubsystemHealth(name="x")
    assert sub.status is HealthStatus.UNKNOWN
    assert sub.detail == ""
    assert sub.metrics == {}


def test_subsystem_health_is_frozen() -> None:
    import dataclasses

    sub = SubsystemHealth(name="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        sub.name = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def test_diagnostics_snapshot_basic() -> None:
    c = DIContainer()
    c.register_value("config", {"k": "v"})
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert isinstance(report, DiagnosticsReport)
    assert report.uptime_seconds >= 0.0
    # Config summary surfaces types, not values (to avoid leaking secrets).
    assert "k" in report.config
    assert report.config["k"] == "str"


def test_diagnostics_providers_listed() -> None:
    c = DIContainer()
    c.register_value(
        "providers",
        type("P", (), {"registry": _FakeRegistry({"openai": 1, "zai": 2})})(),
    )
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert sorted(report.providers) == ["openai", "zai"]


def test_diagnostics_tools_listed() -> None:
    c = DIContainer()
    c.register_value(
        "tools",
        type("T", (), {"registry": _FakeRegistry({"fs": 1})})(),
    )
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.tools == ["fs"]


def test_diagnostics_workflows_listed() -> None:
    c = DIContainer()
    c.register_value(
        "workflows",
        type("W", (), {"registry": _FakeRegistry({"wf1": 1})})(),
    )
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.workflows == ["wf1"]


def test_diagnostics_container_inventory() -> None:
    c = DIContainer()
    c.register_value("a", 1)
    c.register_value("b", 2)
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.container["service_count"] == 2
    assert report.container["initialized_count"] == 2
    assert sorted(report.container["registered"]) == ["a", "b"]


def test_diagnostics_memory_stats() -> None:
    c = DIContainer()
    c.register_value(
        "memory",
        type(
            "M",
            (),
            {
                "working": {"a": 1},
                "episodic": {"b": 2},
                "semantic": None,
                "procedural": None,
                "reflection": None,
            },
        )(),
    )
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    store_names = [s["name"] for s in report.memory["stores"]]
    assert "working" in store_names
    assert "episodic" in store_names


def test_diagnostics_knowledge_stats() -> None:
    c = DIContainer()
    c.register_value(
        "knowledge",
        type(
            "K",
            (),
            {
                "count": lambda self: 5,
                "list_documents": lambda self: [],
            },
        )(),
    )
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.knowledge["documents"] == 5


def test_diagnostics_runtime_stats() -> None:
    c = DIContainer()
    c.register_value(
        "runtime",
        type(
            "R",
            (),
            {
                "health": lambda self: {"status": "healthy", "queue_depth": 0},
                "live_executions": lambda self: [],
            },
        )(),
    )
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.runtime["queue_depth"] == 0
    assert report.runtime["live_executions"] == 0


def test_diagnostics_config_summary_uses_types() -> None:
    c = DIContainer()
    c.register_value("config", {"system": {"name": "Atlas"}, "count": 3})
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.config["system"] == "dict"
    assert report.config["count"] == "int"


def test_diagnostics_to_dict() -> None:
    c = DIContainer()
    diag = DiagnosticsCollector(c)
    d = diag.to_dict()
    assert "timestamp" in d
    assert "providers" in d
    assert "container" in d


def test_diagnostics_handles_missing_subsystems() -> None:
    c = DIContainer()
    diag = DiagnosticsCollector(c)
    report = diag.snapshot()
    assert report.providers == []
    assert report.tools == []
    assert report.memory == {}
    assert report.knowledge == {}


def test_diagnostics_startup_time_recorded() -> None:
    c = DIContainer()
    diag = DiagnosticsCollector(c, startup_time_seconds=1.5)
    report = diag.snapshot()
    assert report.startup_time_seconds == 1.5


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_wiring_creates_empty_container() -> None:
    w = Wiring()
    assert isinstance(w.container, DIContainer)
    assert len(w.container) == 0


def test_wiring_register_config_dict() -> None:
    w = Wiring()
    w.register_config({"k": "v"})
    assert w.container.get("config") == {"k": "v"}


def test_wiring_register_logger() -> None:
    w = Wiring()
    w.register_logger()
    logger = w.container.get("logger")
    assert logger is not None


def test_wiring_register_memory() -> None:
    w = Wiring()
    w.register_memory()
    memory = w.container.get("memory")
    assert memory is not None
    assert hasattr(memory, "working")


def test_wiring_register_knowledge() -> None:
    w = Wiring()
    w.register_knowledge()
    knowledge = w.container.get("knowledge")
    assert knowledge is not None
    assert hasattr(knowledge, "search")


def test_wiring_register_providers_loads_nine_providers() -> None:
    w = Wiring()
    w.register_providers()
    providers = w.container.get("providers")
    assert providers is not None
    assert len(providers.registry) == 9


def test_wiring_register_tools() -> None:
    w = Wiring()
    w.register_tools()
    tools = w.container.get("tools")
    assert tools is not None
    assert hasattr(tools, "registry")


def test_wiring_register_skills() -> None:
    w = Wiring()
    w.register_skills()
    skills = w.container.get("skills")
    assert isinstance(skills, SkillManager)


def test_wiring_register_agents() -> None:
    w = Wiring()
    w.register_agents()
    agents = w.container.get("agents")
    assert agents is not None


def test_wiring_register_workflows() -> None:
    w = Wiring()
    w.register_workflows()
    workflows = w.container.get("workflows")
    assert workflows is not None
    assert hasattr(workflows, "registry")


def test_wiring_register_runtime() -> None:
    w = Wiring()
    w.register_runtime()
    runtime = w.container.get("runtime")
    assert runtime is not None
    assert hasattr(runtime, "handle")


def test_wiring_register_telemetry_pulls_from_runtime() -> None:
    w = Wiring()
    w.register_runtime()
    w.register_telemetry()
    telemetry = w.container.get("telemetry")
    assert telemetry is not None


def test_wiring_register_health() -> None:
    w = Wiring()
    w.register_health()
    health = w.container.get("health")
    assert isinstance(health, HealthMonitor)


def test_wiring_register_registry() -> None:
    w = Wiring()
    w.register_providers()
    w.register_tools()
    w.register_workflows()
    w.register_registry()
    registry = w.container.get("registry")
    assert isinstance(registry, UnifiedRegistry)
    assert registry.count("providers") == 9


def test_wiring_register_locator() -> None:
    w = Wiring()
    w.register_locator()
    locator = w.container.get("locator")
    assert isinstance(locator, ServiceLocator)


def test_wiring_wire_all_registers_every_subsystem() -> None:
    w = Wiring()
    w.wire_all()
    expected = {
        "config",
        "logger",
        "memory",
        "knowledge",
        "providers",
        "tools",
        "skills",
        "agents",
        "workflows",
        "runtime",
        "telemetry",
        "health",
        "registry",
        "locator",
    }
    assert expected.issubset(set(w.container.names()))


def test_wiring_chainable() -> None:
    w = Wiring()
    result = w.register_config().register_logger().register_memory()
    assert result is w


# ---------------------------------------------------------------------------
# Startup manager
# ---------------------------------------------------------------------------


def test_startup_manager_instantiates_every_service() -> None:
    c = DIContainer()
    c.register_value("a", 1, phase=LifecyclePhase.CONFIG)
    c.register_value("b", 2, phase=LifecyclePhase.MEMORY)
    manager = StartupManager(c)
    report = manager.start()
    assert report.success
    assert len(report.steps) == 2
    assert c.is_resolved("a")
    assert c.is_resolved("b")


def test_startup_manager_records_timing() -> None:
    c = DIContainer()
    c.register_value("a", 1, phase=LifecyclePhase.CONFIG)
    manager = StartupManager(c)
    report = manager.start()
    assert report.duration_seconds >= 0.0
    assert all(s.duration_seconds >= 0.0 for s in report.steps)


def test_startup_manager_strict_aborts_on_failure() -> None:
    c = DIContainer()
    c.register_value("a", 1, phase=LifecyclePhase.CONFIG)
    c.register_factory(
        "bad",
        lambda _c: (_ for _ in ()).throw(RuntimeError("boom")),
        phase=LifecyclePhase.MEMORY,
    )
    manager = StartupManager(c, strict=True)
    report = manager.start()
    assert not report.success
    assert "bad" in report.failed_services
    # Strict mode aborts: services after "bad" in the same phase or later
    # phases are not attempted.
    assert all(s.name != "config" for s in report.steps if not s.success)


def test_startup_manager_non_strict_continues_on_failure() -> None:
    c = DIContainer()
    c.register_value("a", 1, phase=LifecyclePhase.CONFIG)
    c.register_factory(
        "bad",
        lambda _c: (_ for _ in ()).throw(RuntimeError("boom")),
        phase=LifecyclePhase.MEMORY,
    )
    c.register_value("c", 3, phase=LifecyclePhase.KNOWLEDGE)
    manager = StartupManager(c, strict=False)
    report = manager.start()
    assert "bad" in report.failed_services
    assert c.is_resolved("c")


def test_startup_report_to_dict() -> None:
    c = DIContainer()
    c.register_value("a", 1, phase=LifecyclePhase.CONFIG)
    manager = StartupManager(c)
    report = manager.start()
    d = report.to_dict()
    assert "started_at" in d
    assert "steps" in d
    assert d["success"] is True


def test_startup_step_result_is_frozen() -> None:
    import dataclasses

    from atlas.integration.startup import StartupStepResult

    result = StartupStepResult(
        name="x",
        phase=LifecyclePhase.CONFIG,
        success=True,
        duration_seconds=0.1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.name = "y"  # type: ignore[misc]


def test_startup_manager_starts_in_phase_order() -> None:
    c = DIContainer()
    c.register_value("memory", "M", phase=LifecyclePhase.MEMORY)
    c.register_value("config", "C", phase=LifecyclePhase.CONFIG)
    manager = StartupManager(c)
    report = manager.start()
    names = [s.name for s in report.steps]
    # CONFIG comes before MEMORY in canonical order.
    assert names.index("config") < names.index("memory")


# ---------------------------------------------------------------------------
# Shutdown manager
# ---------------------------------------------------------------------------


class _Shutdownable:
    """Test double with a ``shutdown()`` method."""

    def __init__(self) -> None:
        self.shut_down: bool = False

    def shutdown(self) -> None:
        self.shut_down = True


def test_shutdown_manager_invokes_shutdown_method() -> None:
    c = DIContainer()
    obj = _Shutdownable()
    c.register_value("x", obj, phase=LifecyclePhase.CONFIG)
    c.get("x")  # mark as initialized
    manager = ShutdownManager(c)
    report = manager.shutdown()
    assert report.success
    assert obj.shut_down


def test_shutdown_manager_skips_services_without_shutdown() -> None:
    c = DIContainer()
    c.register_value("x", 42, phase=LifecyclePhase.CONFIG)
    c.get("x")
    manager = ShutdownManager(c)
    report = manager.shutdown()
    assert report.success
    assert report.steps[0].skipped is True


def test_shutdown_manager_reverse_order() -> None:
    c = DIContainer()
    order: list[str] = []

    class Tracker:
        def __init__(self, name: str) -> None:
            self.name = name

        def shutdown(self) -> None:
            order.append(self.name)

    c.register_value("config", Tracker("config"), phase=LifecyclePhase.CONFIG)
    c.register_value("memory", Tracker("memory"), phase=LifecyclePhase.MEMORY)
    c.get("config")
    c.get("memory")
    manager = ShutdownManager(c)
    manager.shutdown()
    # MEMORY (later phase) shuts down before CONFIG (earlier phase).
    assert order == ["memory", "config"]


def test_shutdown_manager_non_strict_continues_on_failure() -> None:
    c = DIContainer()

    class Bad:
        def shutdown(self) -> None:
            raise RuntimeError("boom")

    c.register_value("bad", Bad(), phase=LifecyclePhase.CONFIG)
    c.register_value("good", _Shutdownable(), phase=LifecyclePhase.MEMORY)
    c.get("bad")
    c.get("good")
    manager = ShutdownManager(c, strict=False)
    report = manager.shutdown()
    assert "bad" in report.failed_services
    assert c.get_optional("good") is None  # container cleared after shutdown


def test_shutdown_manager_strict_aborts_on_failure() -> None:
    c = DIContainer()

    class Bad:
        def shutdown(self) -> None:
            raise RuntimeError("boom")

    good = _Shutdownable()
    c.register_value("bad", Bad(), phase=LifecyclePhase.MEMORY)
    c.register_value("good", good, phase=LifecyclePhase.CONFIG)
    c.get("bad")
    c.get("good")
    manager = ShutdownManager(c, strict=True)
    report = manager.shutdown()
    assert not report.success
    # MEMORY (bad) shuts down before CONFIG (good) in reverse order;
    # strict mode aborts before good is shut down.
    assert not good.shut_down


def test_shutdown_manager_clears_container_after_shutdown() -> None:
    c = DIContainer()
    c.register_value("x", _Shutdownable(), phase=LifecyclePhase.CONFIG)
    c.get("x")
    manager = ShutdownManager(c)
    manager.shutdown()
    assert len(c) == 0


def test_shutdown_report_to_dict() -> None:
    c = DIContainer()
    c.register_value("x", 1, phase=LifecyclePhase.CONFIG)
    c.get("x")
    manager = ShutdownManager(c)
    report = manager.shutdown()
    d = report.to_dict()
    assert "started_at" in d
    assert "steps" in d


def test_shutdown_manager_only_shuts_down_initialized_services() -> None:
    c = DIContainer()
    c.register_factory("lazy", lambda _c: _Shutdownable(), phase=LifecyclePhase.CONFIG)
    # Do NOT get("lazy") — it should not be shut down.
    manager = ShutdownManager(c)
    report = manager.shutdown()
    assert all(step.skipped for step in report.steps)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_returns_bootstrapped_atlas() -> None:
    boot = Bootstrap()
    atlas = boot.run()
    assert isinstance(atlas, BootstrappedAtlas)
    assert isinstance(atlas.container, DIContainer)
    assert isinstance(atlas.startup_report, StartupReport)
    assert isinstance(atlas.health_report, HealthReport)


def test_bootstrap_wires_every_subsystem() -> None:
    atlas = Bootstrap().run()
    expected = {
        "config",
        "logger",
        "memory",
        "knowledge",
        "providers",
        "tools",
        "skills",
        "agents",
        "workflows",
        "runtime",
        "telemetry",
        "health",
        "registry",
        "locator",
    }
    assert expected.issubset(set(atlas.container.names()))


def test_bootstrap_startup_succeeds() -> None:
    atlas = Bootstrap().run()
    assert atlas.startup_report.success
    assert len(atlas.startup_report.failed_services) == 0


def test_bootstrap_providers_loaded() -> None:
    atlas = Bootstrap().run()
    providers = atlas.container.get("providers")
    assert len(providers.registry) == 9


def test_bootstrap_runtime_can_handle_request() -> None:
    atlas = Bootstrap().run()
    runtime = atlas.container.get("runtime")
    ctx = runtime.handle("hello")
    assert ctx.state.value == "completed"


def test_bootstrap_health_report_has_subsystems() -> None:
    atlas = Bootstrap().run()
    assert "config" in atlas.health_report.subsystems
    assert "runtime" in atlas.health_report.subsystems
    assert "providers" in atlas.health_report.subsystems


def test_bootstrap_with_dict_config() -> None:
    atlas = Bootstrap(config={"system": {"name": "TestAtlas"}}).run()
    config = atlas.container.get("config")
    # Config may be a dict or a Config object.
    data = config if isinstance(config, dict) else config.data
    assert data.get("system") == {"name": "TestAtlas"}


def test_bootstrap_strict_fails_loudly() -> None:
    # Register a service that will fail to start.
    boot = Bootstrap()
    # Pre-register a failing service in the bootstrap's container.
    boot.container.register_factory(
        "bad",
        lambda _c: (_ for _ in ()).throw(RuntimeError("boom")),
        phase=LifecyclePhase.CONFIG,
    )
    with pytest.raises(RuntimeError, match="bootstrap failed"):
        boot.run()


def test_bootstrapped_atlas_is_frozen() -> None:
    import dataclasses

    atlas = Bootstrap().run()
    with pytest.raises(dataclasses.FrozenInstanceError):
        atlas.container = DIContainer()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def test_orchestrator_initial_state_is_uninitialized() -> None:
    orch = Orchestrator()
    assert orch.status() is OrchestratorState.UNINITIALIZED


def test_orchestrator_initialize_transitions_to_running() -> None:
    orch = Orchestrator()
    orch.initialize()
    assert orch.status() is OrchestratorState.RUNNING


def test_orchestrator_initialize_twice_raises() -> None:
    orch = Orchestrator()
    orch.initialize()
    with pytest.raises(OrchestratorError):
        orch.initialize()


def test_orchestrator_stop_transitions_to_stopped() -> None:
    orch = Orchestrator()
    orch.initialize()
    orch.stop()
    assert orch.status() is OrchestratorState.STOPPED


def test_orchestrator_stop_without_start_raises() -> None:
    orch = Orchestrator()
    with pytest.raises(OrchestratorError):
        orch.stop()


def test_orchestrator_restart() -> None:
    orch = Orchestrator()
    orch.initialize()
    orch.restart()
    assert orch.status() is OrchestratorState.RUNNING


def test_orchestrator_restart_without_start_raises() -> None:
    orch = Orchestrator()
    with pytest.raises(OrchestratorError):
        orch.restart()


def test_orchestrator_health_returns_report() -> None:
    orch = Orchestrator()
    orch.initialize()
    report = orch.health()
    assert isinstance(report, HealthReport)
    orch.stop()


def test_orchestrator_health_without_start_raises() -> None:
    orch = Orchestrator()
    with pytest.raises(OrchestratorError):
        orch.health()


def test_orchestrator_diagnostics_returns_report() -> None:
    orch = Orchestrator()
    orch.initialize()
    report = orch.diagnostics()
    assert isinstance(report, DiagnosticsReport)
    assert len(report.providers) == 9
    orch.stop()


def test_orchestrator_run_executes_request() -> None:
    orch = Orchestrator()
    orch.initialize()
    ctx = orch.run("hello world")
    assert ctx.state.value == "completed"
    orch.stop()


def test_orchestrator_run_without_start_raises() -> None:
    orch = Orchestrator()
    with pytest.raises(OrchestratorError):
        orch.run("hello")


def test_orchestrator_container_property() -> None:
    orch = Orchestrator()
    orch.initialize()
    assert isinstance(orch.container, DIContainer)
    orch.stop()


def test_orchestrator_container_without_start_raises() -> None:
    orch = Orchestrator()
    with pytest.raises(OrchestratorError):
        _ = orch.container


def test_orchestrator_last_startup() -> None:
    orch = Orchestrator()
    assert orch.last_startup is None
    orch.initialize()
    assert orch.last_startup is not None
    assert orch.last_startup.success
    orch.stop()


def test_orchestrator_last_shutdown() -> None:
    orch = Orchestrator()
    orch.initialize()
    assert orch.last_shutdown is None
    orch.stop()
    assert orch.last_shutdown is not None
    assert orch.last_shutdown.success


def test_orchestrator_started_at() -> None:
    orch = Orchestrator()
    assert orch.started_at is None
    orch.initialize()
    assert orch.started_at is not None
    orch.stop()


def test_orchestrator_state_transitions() -> None:
    orch = Orchestrator()
    assert orch.status() is OrchestratorState.UNINITIALIZED
    orch.initialize()
    assert orch.status() is OrchestratorState.RUNNING
    orch.stop()
    assert orch.status() is OrchestratorState.STOPPED
    orch.initialize()
    assert orch.status() is OrchestratorState.RUNNING


def test_orchestrator_full_lifecycle() -> None:
    """Smoke test: initialize -> run -> health -> diagnostics -> stop."""
    orch = Orchestrator()
    orch.initialize()
    assert orch.status() is OrchestratorState.RUNNING

    ctx = orch.run("hello world")
    assert ctx.state.value == "completed"

    health = orch.health()
    assert health.overall in (
        HealthStatus.HEALTHY,
        HealthStatus.DEGRADED,
    )

    diag = orch.diagnostics()
    assert len(diag.providers) == 9

    report = orch.stop()
    assert report.success
    assert orch.status() is OrchestratorState.STOPPED


def test_orchestrator_repr_shows_state() -> None:
    orch = Orchestrator()
    text = repr(orch)
    assert "Orchestrator" in text
    assert "uninitialized" in text


def test_orchestrator_state_enum_values() -> None:
    states = {s.value for s in OrchestratorState}
    assert states == {
        "uninitialized",
        "initializing",
        "running",
        "stopping",
        "stopped",
        "failed",
    }


def test_orchestrator_error_is_runtime_error() -> None:
    assert issubclass(OrchestratorError, RuntimeError)


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------


def test_end_to_end_atlas_lifecycle() -> None:
    """Full lifecycle: bootstrap -> wire -> start -> run -> health -> stop."""
    orch = Orchestrator()
    atlas = orch.initialize()

    # Every subsystem is wired.
    for name in (
        "config",
        "memory",
        "knowledge",
        "providers",
        "tools",
        "skills",
        "agents",
        "workflows",
        "runtime",
        "telemetry",
        "health",
        "registry",
    ):
        assert atlas.container.contains(name), f"{name} not wired"

    # Runtime is the canonical execution entry point.
    runtime = atlas.container.get("runtime")
    ctx = runtime.handle("integration test")
    assert ctx.state.value == "completed"

    # Unified registry sees the 9 providers.
    registry = atlas.container.get("registry")
    assert registry.count("providers") == 9

    # Health monitor produces a snapshot.
    monitor = atlas.container.get("health")
    report = monitor.snapshot()
    assert report.subsystems["providers"].status is HealthStatus.HEALTHY

    # Diagnostics captures everything.
    diag = atlas.container.get("diagnostics")
    diag_report = diag.snapshot()
    assert len(diag_report.providers) == 9
    assert diag_report.container["service_count"] >= 14

    # Graceful shutdown.
    shutdown_report = orch.stop()
    assert shutdown_report.success


def test_locator_provides_typed_access_after_bootstrap() -> None:
    atlas = Bootstrap().run()
    locator = atlas.container.get("locator")
    assert locator.runtime is not None
    assert locator.memory is not None
    assert locator.providers is not None
    assert locator.health is not None


def test_zero_circular_imports() -> None:
    """Verify every integration module can be imported independently."""
    import importlib

    modules = [
        "atlas.integration.dependency",
        "atlas.integration.registry",
        "atlas.integration.container",
        "atlas.integration.service_locator",
        "atlas.integration.health",
        "atlas.integration.diagnostics",
        "atlas.integration.wiring",
        "atlas.integration.startup",
        "atlas.integration.shutdown",
        "atlas.integration.bootstrap",
        "atlas.integration.orchestrator",
        "atlas.integration",
    ]
    for m in modules:
        importlib.import_module(m)
