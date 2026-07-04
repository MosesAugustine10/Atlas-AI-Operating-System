"""Tests for the Atlas Runtime Engine.

Covers the lifecycle state machine, the event bus, hooks, telemetry, the
execution queue, the recovery manager, the system monitor, the executor,
the pipeline, the dispatcher, the scheduler, and the top-level Runtime
orchestrator.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from atlas.runtime import (
    ACTIVE_STATES,
    AFTER_EXECUTE,
    BEFORE_PLANNING,
    TERMINAL_STATES,
    TRANSITIONS,
    BaseExecutor,
    BaseTelemetryCollector,
    Dispatcher,
    EventBus,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionPlan,
    ExecutionQueue,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStarted,
    ExecutionStep,
    HookAbort,
    HookManager,
    InvalidRuntimeTransitionError,
    Pipeline,
    PipelineContext,
    PlaceholderExecutor,
    PlanningStarted,
    QueueFullError,
    RecoveryManager,
    RecoveryPolicy,
    Runtime,
    RuntimeError_,
    RuntimeEvent,
    RuntimeScheduler,
    RuntimeState,
    ScheduledTask,
    ScheduleKind,
    StepCompleted,
    StepFailed,
    SystemMonitor,
    TelemetryCollector,
    all_states,
    assert_transition,
    can_transition,
    default_pipeline,
    is_active,
    is_terminal,
    legal_targets,
)

# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------


def test_runtime_state_has_ten_states() -> None:
    assert len(list(all_states())) == 10


def test_runtime_terminal_states() -> None:
    assert set(TERMINAL_STATES) == {
        RuntimeState.COMPLETED,
        RuntimeState.FAILED,
        RuntimeState.CANCELLED,
    }


def test_runtime_active_states_are_non_terminal() -> None:
    assert not (set(ACTIVE_STATES) & set(TERMINAL_STATES))


def test_runtime_is_terminal_helper() -> None:
    assert is_terminal(RuntimeState.COMPLETED)
    assert is_terminal(RuntimeState.FAILED)
    assert is_terminal(RuntimeState.CANCELLED)
    assert not is_terminal(RuntimeState.EXECUTING)


def test_runtime_is_active_helper() -> None:
    assert is_active(RuntimeState.EXECUTING)
    assert is_active(RuntimeState.PENDING)
    assert not is_active(RuntimeState.COMPLETED)


def test_runtime_can_transition_legal() -> None:
    assert can_transition(RuntimeState.PENDING, RuntimeState.PLANNING)
    assert can_transition(RuntimeState.PLANNING, RuntimeState.DISPATCHING)
    assert can_transition(RuntimeState.DISPATCHING, RuntimeState.EXECUTING)
    assert can_transition(RuntimeState.EXECUTING, RuntimeState.COMPLETED)
    assert can_transition(RuntimeState.EXECUTING, RuntimeState.PAUSED)
    assert can_transition(RuntimeState.PAUSED, RuntimeState.EXECUTING)
    assert can_transition(RuntimeState.FAILED, RuntimeState.PENDING)


def test_runtime_cannot_transition_illegal() -> None:
    assert not can_transition(RuntimeState.COMPLETED, RuntimeState.EXECUTING)
    assert not can_transition(RuntimeState.CANCELLED, RuntimeState.PENDING)
    assert not can_transition(RuntimeState.PENDING, RuntimeState.COMPLETED)


def test_runtime_assert_transition_raises() -> None:
    with pytest.raises(InvalidRuntimeTransitionError):
        assert_transition(RuntimeState.COMPLETED, RuntimeState.EXECUTING)
    # self-transition is allowed (idempotent)
    assert_transition(RuntimeState.EXECUTING, RuntimeState.EXECUTING)


def test_runtime_legal_targets_returns_set() -> None:
    targets = legal_targets(RuntimeState.EXECUTING)
    assert RuntimeState.COMPLETED in targets
    assert RuntimeState.PAUSED in targets
    assert RuntimeState.PENDING not in targets


def test_runtime_legal_targets_for_terminal_is_empty() -> None:
    assert set(legal_targets(RuntimeState.COMPLETED)) == set()
    assert set(legal_targets(RuntimeState.CANCELLED)) == set()


def test_runtime_transitions_table_covers_every_state() -> None:
    for state in all_states():
        assert state in TRANSITIONS


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


def test_event_bus_subscribe_and_publish() -> None:
    bus = EventBus()
    received: list[RuntimeEvent] = []
    bus.subscribe(StepCompleted, received.append)
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    assert len(received) == 1
    assert received[0].step_id == "s1"


def test_event_bus_wildcard_receives_every_event() -> None:
    bus = EventBus()
    received: list[RuntimeEvent] = []
    bus.subscribe("*", received.append)
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    bus.publish(ExecutionFailed(execution_id="e1", error="boom"))
    assert len(received) == 2


def test_event_bus_history_records_every_event() -> None:
    bus = EventBus()
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionCompleted(execution_id="e1"))
    assert len(bus.history()) == 2


def test_event_bus_history_for_execution() -> None:
    bus = EventBus()
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionStarted(execution_id="e2"))
    bus.publish(ExecutionCompleted(execution_id="e1"))
    assert len(bus.history_for("e1")) == 2
    assert len(bus.history_for("e2")) == 1


def test_event_bus_unsubscribe() -> None:
    bus = EventBus()
    received: list[RuntimeEvent] = []
    bus.subscribe(StepCompleted, received.append)
    assert bus.unsubscribe(StepCompleted, received.append) is True
    assert bus.unsubscribe(StepCompleted, received.append) is False
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    assert received == []


def test_event_bus_listener_exception_is_isolated() -> None:
    bus = EventBus()
    received: list[RuntimeEvent] = []

    def bad_listener(event: RuntimeEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe(StepCompleted, bad_listener)
    bus.subscribe(StepCompleted, received.append)
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    assert len(received) == 1


def test_event_bus_subscribe_rejects_non_callable() -> None:
    bus = EventBus()
    with pytest.raises(TypeError):
        bus.subscribe(StepCompleted, "not callable")  # type: ignore[arg-type]


def test_event_bus_listener_count() -> None:
    bus = EventBus()
    bus.subscribe(StepCompleted, lambda e: None)
    bus.subscribe(ExecutionFailed, lambda e: None)
    assert bus.listener_count() == 2
    assert bus.listener_count(StepCompleted) == 1


def test_event_bus_clear_drops_listeners_and_history() -> None:
    bus = EventBus()
    bus.subscribe(StepCompleted, lambda e: None)
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    bus.clear()
    assert bus.listener_count() == 0
    assert bus.history() == []


def test_event_bus_suspend_and_resume() -> None:
    bus = EventBus()
    received: list[RuntimeEvent] = []
    bus.subscribe(StepCompleted, received.append)
    bus.suspend()
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    assert received == []
    assert len(bus.history()) == 1
    bus.resume_dispatch()
    bus.publish(StepCompleted(execution_id="e1", step_id="s2"))
    assert len(received) == 1


def test_event_bus_topics_lists_active_topics() -> None:
    bus = EventBus()
    bus.subscribe(StepCompleted, lambda e: None)
    bus.subscribe(ExecutionFailed, lambda e: None)
    topics = bus.topics()
    assert StepCompleted in topics
    assert ExecutionFailed in topics


def test_event_subclasses_dispatch_to_base_listener() -> None:
    bus = EventBus()
    received: list[RuntimeEvent] = []
    bus.subscribe(RuntimeEvent, received.append)
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    assert len(received) == 1


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def test_hook_manager_register_and_run() -> None:
    hm = HookManager()
    calls: list[str] = []
    hm.register(BEFORE_PLANNING, lambda ctx, event: calls.append("hook1"))
    hm.run(BEFORE_PLANNING)
    assert calls == ["hook1"]


def test_hook_manager_priority_order() -> None:
    hm = HookManager()
    calls: list[str] = []
    hm.register(BEFORE_PLANNING, lambda ctx, event: calls.append("low"), priority=10)
    hm.register(BEFORE_PLANNING, lambda ctx, event: calls.append("high"), priority=1)
    hm.run(BEFORE_PLANNING)
    assert calls == ["high", "low"]


def test_hook_manager_before_short_circuits() -> None:
    hm = HookManager()
    hm.register(BEFORE_PLANNING, lambda ctx, event: "short_circuit")
    result = hm.run(BEFORE_PLANNING)
    assert result == "short_circuit"


def test_hook_manager_after_does_not_short_circuit() -> None:
    hm = HookManager()
    hm.register(AFTER_EXECUTE, lambda ctx, event: "ignored")
    result = hm.run(AFTER_EXECUTE)
    assert result is None


def test_hook_manager_raises_on_unknown_phase() -> None:
    hm = HookManager()
    with pytest.raises(ValueError):
        hm.register("bogus_phase", lambda ctx, event: None)


def test_hook_manager_rejects_non_callable() -> None:
    hm = HookManager()
    with pytest.raises(TypeError):
        hm.register(BEFORE_PLANNING, "not callable")  # type: ignore[arg-type]


def test_hook_manager_unsubscribe() -> None:
    hm = HookManager()
    reg = hm.register(BEFORE_PLANNING, lambda ctx, event: None)
    assert hm.unregister(reg) is True
    assert hm.unregister(reg) is False
    assert hm.hook_count(BEFORE_PLANNING) == 0


def test_hook_manager_clear() -> None:
    hm = HookManager()
    hm.register(BEFORE_PLANNING, lambda ctx, event: None)
    hm.register(AFTER_EXECUTE, lambda ctx, event: None)
    hm.clear()
    assert hm.hook_count() == 0


def test_hook_manager_clear_single_phase() -> None:
    hm = HookManager()
    hm.register(BEFORE_PLANNING, lambda ctx, event: None)
    hm.register(AFTER_EXECUTE, lambda ctx, event: None)
    hm.clear(BEFORE_PLANNING)
    assert hm.hook_count(BEFORE_PLANNING) == 0
    assert hm.hook_count(AFTER_EXECUTE) == 1


def test_hook_manager_isolates_exceptions() -> None:
    hm = HookManager()
    calls: list[str] = []

    def boom(ctx, event):  # type: ignore[no-untyped-def]
        raise RuntimeError("kaboom")

    hm.register(BEFORE_PLANNING, boom)
    hm.register(BEFORE_PLANNING, lambda ctx, event: calls.append("after"))
    hm.run(BEFORE_PLANNING)
    assert calls == ["after"]


def test_hook_abort_propagates() -> None:
    hm = HookManager()

    def abort_hook(ctx, event):  # type: ignore[no-untyped-def]
        raise HookAbort("aborted")

    hm.register(BEFORE_PLANNING, abort_hook)
    with pytest.raises(HookAbort):
        hm.run(BEFORE_PLANNING)


def test_hook_manager_phases_returns_active_phases() -> None:
    hm = HookManager()
    hm.register(BEFORE_PLANNING, lambda ctx, event: None)
    phases = hm.phases()
    assert BEFORE_PLANNING in phases


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


def test_telemetry_records_execution_started() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    assert tel.metrics("e1") is not None
    assert tel.metrics("e1").started_at is not None


def test_telemetry_records_step_outcomes() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(StepCompleted(execution_id="e1", step_id="s1"))
    bus.publish(StepFailed(execution_id="e1", step_id="s2", error="boom"))
    metrics = tel.metrics("e1")
    assert metrics.steps_succeeded == 1
    assert metrics.steps_failed == 1


def test_telemetry_records_provider_selection() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(
        type(tel).__name__  # placeholder
        if False
        else __import__(
            "atlas.runtime.events",
            fromlist=["ProviderSelected"],
        ).ProviderSelected(execution_id="e1", provider="openai")
    )
    metrics = tel.metrics("e1")
    assert "openai" in metrics.providers_used


def test_telemetry_records_terminal_state() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionCompleted(execution_id="e1"))
    metrics = tel.metrics("e1")
    assert metrics.final_state == "completed"
    assert metrics.completed_at is not None


def test_telemetry_summary() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionCompleted(execution_id="e1"))
    bus.publish(ExecutionStarted(execution_id="e2"))
    bus.publish(ExecutionFailed(execution_id="e2", error="boom"))
    summary = tel.summary()
    assert summary["executions_observed"] == 2
    assert summary["executions_completed"] == 1
    assert summary["executions_failed"] == 1


def test_telemetry_reset_clears_all() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    tel.reset()
    assert tel.metrics("e1") is None
    assert tel.summary()["executions_observed"] == 0


def test_telemetry_all_metrics() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionStarted(execution_id="e2"))
    assert len(tel.all_metrics()) == 2


def test_telemetry_is_base_telemetry_collector() -> None:
    assert issubclass(TelemetryCollector, BaseTelemetryCollector)


def test_telemetry_planning_duration() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(PlanningStarted(execution_id="e1"))
    bus.publish(
        __import__(
            "atlas.runtime.events",
            fromlist=["PlanningCompleted"],
        ).PlanningCompleted(execution_id="e1", task_count=3)
    )
    metrics = tel.metrics("e1")
    assert metrics.planning_duration_seconds >= 0.0


# ---------------------------------------------------------------------------
# Execution queue
# ---------------------------------------------------------------------------


def test_queue_enqueue_and_dequeue() -> None:
    q = ExecutionQueue()
    req = q.enqueue(ExecutionRequest(request="hello"))
    assert req.id > 0
    dequeued = q.dequeue()
    assert dequeued is not None
    assert dequeued.id == req.id
    assert q.dequeue() is None


def test_queue_fifo_order() -> None:
    q = ExecutionQueue()
    q.enqueue(ExecutionRequest(request="first"))
    q.enqueue(ExecutionRequest(request="second"))
    q.enqueue(ExecutionRequest(request="third"))
    assert q.dequeue().request == "first"
    assert q.dequeue().request == "second"
    assert q.dequeue().request == "third"


def test_queue_priority_order() -> None:
    q = ExecutionQueue()
    q.enqueue(ExecutionRequest(request="low", priority=1))
    q.enqueue(ExecutionRequest(request="high", priority=10))
    q.enqueue(ExecutionRequest(request="med", priority=5))
    assert q.dequeue().request == "high"
    assert q.dequeue().request == "med"
    assert q.dequeue().request == "low"


def test_queue_peek_does_not_remove() -> None:
    q = ExecutionQueue()
    q.enqueue(ExecutionRequest(request="hello"))
    assert q.peek().request == "hello"
    assert len(q) == 1


def test_queue_capacity_raises_when_full() -> None:
    q = ExecutionQueue(capacity=1)
    q.enqueue(ExecutionRequest(request="first"))
    with pytest.raises(QueueFullError):
        q.enqueue(ExecutionRequest(request="second"))


def test_queue_capacity_zero_is_unbounded() -> None:
    q = ExecutionQueue()
    for i in range(100):
        q.enqueue(ExecutionRequest(request=f"r{i}"))
    assert len(q) == 100


def test_queue_rejects_negative_capacity() -> None:
    with pytest.raises(ValueError):
        ExecutionQueue(capacity=-1)


def test_queue_clear() -> None:
    q = ExecutionQueue()
    q.enqueue(ExecutionRequest(request="a"))
    q.enqueue(ExecutionRequest(request="b"))
    q.clear()
    assert len(q) == 0


def test_queue_len_and_bool() -> None:
    q = ExecutionQueue()
    assert len(q) == 0
    assert not q
    q.enqueue(ExecutionRequest(request="a"))
    assert len(q) == 1
    assert q


def test_queue_iter_returns_in_priority_order() -> None:
    q = ExecutionQueue()
    q.enqueue(ExecutionRequest(request="low", priority=1))
    q.enqueue(ExecutionRequest(request="high", priority=10))
    items = list(q)
    assert [i.request for i in items] == ["high", "low"]


def test_execution_request_with_id_returns_copy() -> None:
    req = ExecutionRequest(request="hello")
    req2 = req.with_id(42)
    assert req2.id == 42
    assert req.id == 0


def test_execution_request_is_frozen() -> None:
    req = ExecutionRequest(request="hello")
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.request = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Recovery manager
# ---------------------------------------------------------------------------


def test_recovery_decide_retry_within_limit() -> None:
    rm = RecoveryManager(policy=RecoveryPolicy(max_retries=3))
    rm.record_start("e1")
    decision = rm.decide(ExecutionFailed(execution_id="e1", error="boom"))
    assert decision.action == "retry"
    assert decision.retry is True
    assert decision.wait_until is not None
    assert decision.attempt == 1


def test_recovery_decide_abort_when_max_exceeded() -> None:
    rm = RecoveryManager(policy=RecoveryPolicy(max_retries=1))
    rm.record_start("e1")
    rm.decide(ExecutionFailed(execution_id="e1", error="boom"))
    # Second attempt should exceed max.
    rm.record_start("e1")
    decision = rm.decide(ExecutionFailed(execution_id="e1", error="boom"))
    assert decision.action == "abort"


def test_recovery_decide_compensate_when_compensator_returns_payload() -> None:
    def compensator(failure):  # type: ignore[no-untyped-def]
        return {"fallback": "default"}

    rm = RecoveryManager(
        policy=RecoveryPolicy(max_retries=1),
        compensator=compensator,
    )
    rm.record_start("e1")
    rm.decide(ExecutionFailed(execution_id="e1", error="boom"))
    rm.record_start("e1")
    decision = rm.decide(ExecutionFailed(execution_id="e1", error="boom"))
    assert decision.action == "compensate"
    assert decision.payload == {"fallback": "default"}


def test_recovery_retryable_errors_filter() -> None:
    rm = RecoveryManager(
        policy=RecoveryPolicy(
            max_retries=3,
            retryable_errors=("timeout",),
        )
    )
    rm.record_start("e1")
    decision = rm.decide(ExecutionFailed(execution_id="e1", error="timeout occurred"))
    assert decision.action == "retry"
    rm.record_start("e2")
    decision = rm.decide(ExecutionFailed(execution_id="e2", error="permission denied"))
    assert decision.action == "abort"


def test_recovery_records_attempts() -> None:
    rm = RecoveryManager(policy=RecoveryPolicy(max_retries=3))
    rm.record_start("e1")
    assert rm.attempts("e1") == 1
    rm.record_start("e1")
    assert rm.attempts("e1") == 2


def test_recovery_mark_recovered() -> None:
    rm = RecoveryManager()
    rm.record_start("e1")
    rm.mark_recovered("e1")
    assert rm.recovered("e1") is True


def test_recovery_reset() -> None:
    rm = RecoveryManager()
    rm.record_start("e1")
    rm.reset()
    assert rm.attempts("e1") == 0


def test_recovery_decide_without_execution_id_aborts() -> None:
    rm = RecoveryManager()
    decision = rm.decide(ExecutionFailed(execution_id=None, error="x"))
    assert decision.action == "abort"


def test_recovery_backoff_doubles() -> None:
    rm = RecoveryManager(
        policy=RecoveryPolicy(
            max_retries=5, base_delay_seconds=1.0, max_delay_seconds=100.0
        )
    )
    rm.record_start("e1")
    d1 = rm.decide(ExecutionFailed(execution_id="e1", error="x"))
    rm.record_start("e1")
    d2 = rm.decide(ExecutionFailed(execution_id="e1", error="x"))
    rm.record_start("e1")
    d3 = rm.decide(ExecutionFailed(execution_id="e1", error="x"))
    assert d1.wait_until is not None
    assert d2.wait_until is not None
    assert d3.wait_until is not None
    assert d2.wait_until > d1.wait_until
    assert d3.wait_until > d2.wait_until


def test_recovery_subscribes_to_bus() -> None:
    bus = EventBus()
    rm = RecoveryManager(bus=bus)
    bus.publish(ExecutionStarted(execution_id="e1"))
    assert rm.attempts("e1") == 1


# ---------------------------------------------------------------------------
# System monitor
# ---------------------------------------------------------------------------


def test_monitor_snapshot_healthy() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(tel, q)
    report = monitor.snapshot()
    assert report.status == "healthy"
    assert report.queue_depth == 0


def test_monitor_snapshot_degraded_on_high_failure_rate() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(
        tel,
        q,
        failure_rate_threshold=0.1,
        unhealthy_failure_rate=0.9,
    )
    # 1 failed, 1 completed -> failure_rate = 0.5 (degraded but not unhealthy)
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionCompleted(execution_id="e1"))
    bus.publish(ExecutionStarted(execution_id="e2"))
    bus.publish(ExecutionFailed(execution_id="e2", error="boom"))
    report = monitor.snapshot()
    assert report.status == "degraded"


def test_monitor_snapshot_unhealthy_on_very_high_failure_rate() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(
        tel,
        q,
        failure_rate_threshold=0.1,
        unhealthy_failure_rate=0.5,
    )
    bus.publish(ExecutionStarted(execution_id="e1"))
    bus.publish(ExecutionFailed(execution_id="e1", error="boom"))
    report = monitor.snapshot()
    assert report.status == "unhealthy"


def test_monitor_queue_depth_reflects_queue() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(tel, q)
    q.enqueue(ExecutionRequest(request="hello"))
    report = monitor.snapshot()
    assert report.queue_depth == 1


def test_monitor_is_healthy() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(tel, q)
    assert monitor.is_healthy() is True


def test_monitor_to_dict() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(tel, q)
    d = monitor.to_dict()
    assert "status" in d
    assert "queue_depth" in d
    assert "warnings" in d


def test_monitor_warns_on_active_cap_exceeded() -> None:
    bus = EventBus()
    tel = TelemetryCollector(bus)
    q = ExecutionQueue()
    monitor = SystemMonitor(tel, q, max_active_executions=0)
    bus.publish(ExecutionStarted(execution_id="e1"))
    report = monitor.snapshot()
    assert any("active_executions" in w for w in report.warnings)


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def test_executor_noop_action_succeeds() -> None:
    ex = PlaceholderExecutor()
    plan = ExecutionPlan(steps=[ExecutionStep(id="s1", action="noop")])
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert outcome.success
    assert outcome.results["s1"].success


def test_executor_echo_action_returns_params() -> None:
    ex = PlaceholderExecutor()
    plan = ExecutionPlan(
        steps=[ExecutionStep(id="s1", action="echo", params={"msg": "hi"})]
    )
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert outcome.success
    assert outcome.results["s1"].output == {"msg": "hi"}


def test_executor_fail_action_fails_outcome() -> None:
    ex = PlaceholderExecutor()
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(
                id="s1",
                action="fail",
                params={"message": "boom"},
            )
        ]
    )
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert not outcome.success
    assert "boom" in outcome.error


def test_executor_optional_step_failure_does_not_fail_plan() -> None:
    ex = PlaceholderExecutor()
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(
                id="s1",
                action="fail",
                params={"message": "boom"},
                optional=True,
            ),
            ExecutionStep(id="s2", action="noop"),
        ]
    )
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert outcome.success


def test_executor_unknown_action_fails_step() -> None:
    ex = PlaceholderExecutor()
    plan = ExecutionPlan(steps=[ExecutionStep(id="s1", action="bogus")])
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert not outcome.success


def test_executor_context_read_action() -> None:
    ex = PlaceholderExecutor()
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(id="s1", action="identity", params={"value": "v1"}),
            ExecutionStep(
                id="s2",
                action="context_read",
                params={"key": "s1"},
            ),
        ]
    )
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert outcome.success
    assert outcome.results["s2"].output == "v1"


def test_executor_register_custom_action() -> None:
    ex = PlaceholderExecutor()

    def double(params, context):  # type: ignore[no-untyped-def]
        return params.get("value", 0) * 2

    ex.register_action("double", double)
    plan = ExecutionPlan(
        steps=[ExecutionStep(id="s1", action="double", params={"value": 21})]
    )
    outcome = ex.execute_plan(plan, execution_id="e1")
    assert outcome.success
    assert outcome.results["s1"].output == 42


def test_executor_register_action_rejects_empty_name() -> None:
    ex = PlaceholderExecutor()
    with pytest.raises(ValueError):
        ex.register_action("", lambda p, c: None)


def test_executor_publishes_events() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor(bus=bus)
    plan = ExecutionPlan(steps=[ExecutionStep(id="s1", action="noop")])
    ex.execute_plan(plan, execution_id="e1")
    types = [type(e).__name__ for e in bus.history()]
    assert "ExecutionStarted" in types
    assert "StepStarted" in types
    assert "StepCompleted" in types


def test_executor_publishes_step_failed_on_error() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor(bus=bus)
    plan = ExecutionPlan(
        steps=[
            ExecutionStep(
                id="s1",
                action="fail",
                params={"message": "boom"},
            )
        ]
    )
    ex.execute_plan(plan, execution_id="e1")
    types = [type(e).__name__ for e in bus.history()]
    assert "StepFailed" in types


def test_executor_known_actions_lists_builtins() -> None:
    ex = PlaceholderExecutor()
    actions = ex.known_actions()
    for builtin in ("noop", "echo", "fail", "identity", "context_read"):
        assert builtin in actions


def test_executor_is_base_executor() -> None:
    assert issubclass(PlaceholderExecutor, BaseExecutor)


def test_execution_step_is_frozen() -> None:
    step = ExecutionStep(id="s1", action="noop")
    with pytest.raises(dataclasses.FrozenInstanceError):
        step.action = "other"  # type: ignore[misc]


def test_execution_result_defaults() -> None:
    r = ExecutionResult(step_id="s1", success=True)
    assert r.output is None
    assert r.error is None
    assert r.completed_at is None


def test_execution_plan_is_frozen() -> None:
    plan = ExecutionPlan()
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.steps = []  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def test_pipeline_runs_default_stages() -> None:
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.state.value == "completed"
    assert ctx.response == "noop"


def test_pipeline_records_plan() -> None:
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.plan is not None
    assert len(ctx.plan.steps) == 1


def test_pipeline_records_outcome() -> None:
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.outcome is not None
    assert ctx.outcome.success


def test_pipeline_failed_stage_marks_failed() -> None:
    def failing_stage(ctx: PipelineContext) -> None:  # noqa: ARG001
        ctx.error = "boom"

    pipeline = Pipeline(stages=[failing_stage])
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.state.value == "failed"


def test_pipeline_exception_in_stage_marks_failed() -> None:
    def bad_stage(ctx: PipelineContext) -> None:  # noqa: ARG001
        raise RuntimeError("kaboom")

    pipeline = Pipeline(stages=[bad_stage])
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.state.value == "failed"
    assert "kaboom" in ctx.error


def test_pipeline_publishes_events() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex, bus=bus)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    types = [type(e).__name__ for e in bus.history()]
    assert "ExecutionStarted" in types
    assert "ExecutionCompleted" in types


def test_pipeline_emits_failure_on_error() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex, bus=bus)

    def failing_stage(ctx: PipelineContext) -> None:  # noqa: ARG001
        ctx.error = "boom"

    pipeline.add_stage(failing_stage)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    types = [type(e).__name__ for e in bus.history()]
    assert "ExecutionFailed" in types


def test_pipeline_add_stage_chains() -> None:
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex)
    extra_called: list[bool] = []
    pipeline.add_stage(lambda ctx: extra_called.append(True))
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert extra_called == [True]


def test_pipeline_planning_stage_emits_events() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex, bus=bus)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    types = [type(e).__name__ for e in bus.history()]
    assert "PlanningStarted" in types
    assert "PlanningCompleted" in types


def test_pipeline_dispatch_stage_emits_events() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex, bus=bus)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    types = [type(e).__name__ for e in bus.history()]
    assert "DispatchStarted" in types
    assert "DispatchCompleted" in types


def test_pipeline_review_stage_emits_events() -> None:
    bus = EventBus()
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex, bus=bus)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    types = [type(e).__name__ for e in bus.history()]
    assert "ReviewStarted" in types
    assert "ReviewCompleted" in types


def test_pipeline_context_is_terminal_after_run() -> None:
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(executor=ex)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.is_terminal()


def test_pipeline_custom_planner() -> None:
    ex = PlaceholderExecutor()
    custom_plan = ExecutionPlan(
        steps=[
            ExecutionStep(
                id="custom",
                action="echo",
                params={"x": 1},
            )
        ]
    )
    pipeline = default_pipeline(executor=ex, planner=lambda req, ctx: custom_plan)
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.outcome.results["custom"].output == {"x": 1}


def test_pipeline_custom_assembler() -> None:
    ex = PlaceholderExecutor()
    pipeline = default_pipeline(
        executor=ex,
        assembler=lambda ctx: f"response:{ctx.request}",
    )
    ctx = PipelineContext(request="hello")
    pipeline.run(ctx)
    assert ctx.response == "response:hello"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def test_dispatcher_dispatch_one_empty_returns_none() -> None:
    q = ExecutionQueue()
    pipeline = default_pipeline(executor=PlaceholderExecutor())
    d = Dispatcher(q, lambda ctx: pipeline)
    assert d.dispatch_one() is None


def test_dispatcher_dispatch_request_runs_pipeline() -> None:
    q = ExecutionQueue()
    pipeline = default_pipeline(executor=PlaceholderExecutor())
    d = Dispatcher(q, lambda ctx: pipeline)
    req = ExecutionRequest(request="hello")
    ctx = d.dispatch_request(req)
    assert ctx.state.value == "completed"


def test_dispatcher_drain_processes_all() -> None:
    q = ExecutionQueue()
    pipeline = default_pipeline(executor=PlaceholderExecutor())
    d = Dispatcher(q, lambda ctx: pipeline)
    q.enqueue(ExecutionRequest(request="a"))
    q.enqueue(ExecutionRequest(request="b"))
    results = d.drain()
    assert len(results) == 2


def test_dispatcher_drain_respects_max_items() -> None:
    q = ExecutionQueue()
    pipeline = default_pipeline(executor=PlaceholderExecutor())
    d = Dispatcher(q, lambda ctx: pipeline)
    q.enqueue(ExecutionRequest(request="a"))
    q.enqueue(ExecutionRequest(request="b"))
    results = d.drain(max_items=1)
    assert len(results) == 1


def test_dispatcher_processed_and_failed_counts() -> None:
    q = ExecutionQueue()
    pipeline = default_pipeline(executor=PlaceholderExecutor())
    d = Dispatcher(q, lambda ctx: pipeline)
    d.dispatch_request(ExecutionRequest(request="ok"))
    assert d.processed_count == 1
    assert d.failed_count == 0


def test_dispatcher_failed_count_increments_on_failure() -> None:
    q = ExecutionQueue()

    def failing_stage(ctx: PipelineContext) -> None:  # noqa: ARG001
        ctx.error = "boom"

    pipeline = default_pipeline(executor=PlaceholderExecutor())
    pipeline.add_stage(failing_stage)
    d = Dispatcher(q, lambda ctx: pipeline)
    d.dispatch_request(ExecutionRequest(request="bad"))
    assert d.failed_count == 1


def test_dispatcher_reset_counters() -> None:
    q = ExecutionQueue()
    pipeline = default_pipeline(executor=PlaceholderExecutor())
    d = Dispatcher(q, lambda ctx: pipeline)
    d.dispatch_request(ExecutionRequest(request="ok"))
    d.reset_counters()
    assert d.processed_count == 0


# ---------------------------------------------------------------------------
# Runtime scheduler
# ---------------------------------------------------------------------------


def test_runtime_scheduler_register_and_get() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    task = ScheduledTask(
        request="ping",
        kind=ScheduleKind.ONE_TIME,
        run_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    sched.register(task)
    assert sched.get(task.id) is not None
    assert sched.contains(task.id)


def test_runtime_scheduler_register_duplicate_raises() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    task = ScheduledTask(id="t1", request="ping")
    sched.register(task)
    with pytest.raises(ValueError):
        sched.register(task)


def test_runtime_scheduler_unregister() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    sched.register(ScheduledTask(id="t1", request="ping"))
    assert sched.unregister("t1") is True
    assert sched.unregister("t1") is False


def test_runtime_scheduler_due_filters_by_next_run_at() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    past = ScheduledTask(
        id="past",
        request="p",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=now - timedelta(minutes=5),
    )
    future = ScheduledTask(
        id="future",
        request="f",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=now + timedelta(minutes=5),
    )
    sched.register(past)
    sched.register(future)
    due = sched.due(now)
    assert {t.id for t in due} == {"past"}


def test_runtime_scheduler_tick_enqueues_and_advances_one_time() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    task = ScheduledTask(
        id="t1",
        request="ping",
        kind=ScheduleKind.ONE_TIME,
        run_at=run_at,
    )
    sched.register(task)
    enqueued = sched.tick(now=run_at + timedelta(minutes=1))
    assert len(enqueued) == 1
    assert enqueued[0].request == "ping"
    updated = sched.get("t1")
    assert updated.enabled is False


def test_runtime_scheduler_tick_advances_interval() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    task = ScheduledTask(
        id="t1",
        request="ping",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=60,
        next_run_at=start,
    )
    sched.register(task)
    sched.tick(now=start)
    updated = sched.get("t1")
    assert updated.next_run_at == start + timedelta(seconds=60)


def test_runtime_scheduler_tick_advances_cron_placeholder() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    task = ScheduledTask(
        id="t1",
        request="daily",
        kind=ScheduleKind.CRON,
        cron_expr="0 0 * * *",
        next_run_at=start,
    )
    sched.register(task)
    sched.tick(now=start)
    updated = sched.get("t1")
    assert updated.next_run_at == start + timedelta(hours=24)


def test_runtime_scheduler_tick_skips_not_due() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    sched.register(
        ScheduledTask(
            id="t1",
            request="ping",
            kind=ScheduleKind.ONE_TIME,
            run_at=run_at,
        )
    )
    enqueued = sched.tick(now=run_at - timedelta(minutes=1))
    assert enqueued == []


def test_runtime_scheduler_tick_skips_disabled() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    sched.register(
        ScheduledTask(
            id="t1",
            request="ping",
            kind=ScheduleKind.ONE_TIME,
            next_run_at=datetime(2026, 1, 1, tzinfo=UTC),
            enabled=False,
        )
    )
    enqueued = sched.tick(now=datetime(2026, 1, 2, tzinfo=UTC))
    assert enqueued == []


def test_runtime_scheduler_len() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    assert len(sched) == 0
    sched.register(ScheduledTask(id="a", request="ping"))
    assert len(sched) == 1


def test_runtime_scheduler_normalizes_one_time_next_run_at() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    task = ScheduledTask(
        id="t1",
        request="ping",
        kind=ScheduleKind.ONE_TIME,
        run_at=run_at,
    )
    sched.register(task)
    stored = sched.get("t1")
    assert stored.next_run_at == run_at


def test_runtime_scheduler_all_returns_sorted() -> None:
    q = ExecutionQueue()
    sched = RuntimeScheduler(q)
    sched.register(ScheduledTask(id="b", request="b"))
    sched.register(ScheduledTask(id="a", request="a"))
    assert [t.id for t in sched.all()] == ["a", "b"]


# ---------------------------------------------------------------------------
# Runtime — top-level
# ---------------------------------------------------------------------------


def test_runtime_handle_returns_completed_context() -> None:
    rt = Runtime()
    ctx = rt.handle("hello world")
    assert ctx.state.value == "completed"
    assert ctx.response == "noop"


def test_runtime_handle_records_live_execution() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    assert rt.get_execution(ctx.execution_id) is ctx


def test_runtime_handle_emits_events() -> None:
    rt = Runtime()
    rt.handle("hello")
    assert len(rt.events()) > 0


def test_runtime_submit_does_not_dispatch() -> None:
    rt = Runtime()
    rt.submit("hello")
    assert len(rt.live_executions()) == 0
    assert len(rt.queue) == 1


def test_runtime_drain_dispatches_pending() -> None:
    rt = Runtime()
    rt.submit("hello")
    results = rt.drain()
    assert len(results) == 1
    assert results[0].state.value == "completed"


def test_runtime_health_returns_dict() -> None:
    rt = Runtime()
    health = rt.health()
    assert health["status"] == "healthy"


def test_runtime_metrics_returns_metrics() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    metrics = rt.metrics(ctx.execution_id)
    assert metrics is not None
    assert metrics.final_state == "completed"


def test_runtime_events_filtered_by_execution() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    events = rt.events(ctx.execution_id)
    assert all(e.execution_id == ctx.execution_id for e in events)


def test_runtime_live_executions_lists_all() -> None:
    rt = Runtime()
    rt.handle("a")
    rt.handle("b")
    assert len(rt.live_executions()) == 2


def test_runtime_accepts_injected_dependencies() -> None:
    bus = EventBus()
    queue = ExecutionQueue()
    executor = PlaceholderExecutor()
    hooks = HookManager()
    telemetry = TelemetryCollector(bus)
    monitor = SystemMonitor(telemetry, queue)
    recovery = RecoveryManager(bus=bus)
    scheduler = RuntimeScheduler(queue)
    rt = Runtime(
        queue=queue,
        executor=executor,
        bus=bus,
        hooks=hooks,
        telemetry=telemetry,
        monitor=monitor,
        recovery=recovery,
        scheduler=scheduler,
    )
    assert rt.queue is queue
    assert rt.executor is executor
    assert rt.bus is bus
    assert rt.hooks is hooks
    assert rt.telemetry is telemetry
    assert rt.monitor is monitor
    assert rt.recovery is recovery
    assert rt.scheduler is scheduler


def test_runtime_pause_marks_paused() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    # Simulate a non-terminal state for testing pause.
    ctx.state = RuntimeState.EXECUTING
    paused = rt.pause(ctx.execution_id)
    assert paused.state is RuntimeState.PAUSED


def test_runtime_pause_terminal_raises() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    with pytest.raises(RuntimeError_):
        rt.pause(ctx.execution_id)


def test_runtime_resume_restores_executing() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    ctx.state = RuntimeState.PAUSED
    resumed = rt.resume(ctx.execution_id)
    assert resumed.state is RuntimeState.EXECUTING


def test_runtime_resume_non_paused_raises() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    # completed is terminal — pause would raise, but resume also raises.
    with pytest.raises(RuntimeError_):
        rt.resume(ctx.execution_id)


def test_runtime_cancel_terminal_raises() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    with pytest.raises(RuntimeError_):
        rt.cancel(ctx.execution_id)


def test_runtime_cancel_non_terminal() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    ctx.state = RuntimeState.EXECUTING
    cancelled = rt.cancel(ctx.execution_id, reason="operator")
    assert cancelled.state is RuntimeState.CANCELLED
    assert cancelled.error == "operator"


def test_runtime_retry_failed_execution() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    ctx.state = RuntimeState.FAILED
    ctx.error = "boom"
    retried = rt.retry(ctx.execution_id)
    assert retried.state.value in ("completed", "failed")


def test_runtime_retry_non_failed_raises() -> None:
    rt = Runtime()
    ctx = rt.handle("hello")
    with pytest.raises(RuntimeError_):
        rt.retry(ctx.execution_id)


def test_runtime_register_schedule() -> None:
    rt = Runtime()
    task = ScheduledTask(
        id="t1",
        request="ping",
        kind=ScheduleKind.ONE_TIME,
        run_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    rt.register_schedule(task)
    assert rt.scheduler.contains("t1")


def test_runtime_unregister_schedule() -> None:
    rt = Runtime()
    rt.register_schedule(
        ScheduledTask(id="t1", request="ping", kind=ScheduleKind.ONE_TIME)
    )
    assert rt.unregister_schedule("t1") is True
    assert rt.unregister_schedule("t1") is False


def test_runtime_list_schedules() -> None:
    rt = Runtime()
    rt.register_schedule(ScheduledTask(id="a", request="a"))
    rt.register_schedule(ScheduledTask(id="b", request="b"))
    assert {t.id for t in rt.list_schedules()} == {"a", "b"}


def test_runtime_tick_fires_due_and_dispatches() -> None:
    rt = Runtime()
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    rt.register_schedule(
        ScheduledTask(
            id="t1",
            request="ping",
            kind=ScheduleKind.ONE_TIME,
            run_at=run_at,
        )
    )
    results = rt.tick(now=run_at + timedelta(minutes=1))
    assert len(results) == 1
    assert results[0].state.value == "completed"


def test_runtime_unknown_execution_raises_on_pause() -> None:
    rt = Runtime()
    with pytest.raises(RuntimeError_):
        rt.pause("unknown")


def test_runtime_unknown_execution_raises_on_resume() -> None:
    rt = Runtime()
    with pytest.raises(RuntimeError_):
        rt.resume("unknown")


def test_runtime_unknown_execution_raises_on_cancel() -> None:
    rt = Runtime()
    with pytest.raises(RuntimeError_):
        rt.cancel("unknown")


def test_runtime_repr_summarizes_state() -> None:
    rt = Runtime()
    rt.handle("hello")
    text = repr(rt)
    assert "Runtime" in text
    assert "live=" in text


def test_runtime_handles_concurrent_requests() -> None:
    rt = Runtime()
    ctx_a = rt.handle("a")
    ctx_b = rt.handle("b")
    assert ctx_a.execution_id != ctx_b.execution_id
    assert ctx_a.state.value == "completed"
    assert ctx_b.state.value == "completed"


def test_runtime_uses_injected_pipeline_factory() -> None:
    rt = Runtime()
    calls: list[str] = []
    original_factory = rt.pipeline_factory

    def factory(ctx: PipelineContext) -> Pipeline:  # noqa: ARG001
        calls.append(ctx.request)
        return original_factory(ctx)

    rt.pipeline_factory = factory
    rt.dispatcher.pipeline_factory = factory
    rt.handle("custom")
    assert calls == ["custom"]


def test_runtime_health_reflects_failures() -> None:
    rt = Runtime()
    # Force a failure by injecting a failing executor action.
    rt.executor.register_action(
        "fail_always", lambda p, c: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    # The default planner uses "noop", so we need a custom planner.
    from atlas.runtime import ExecutionPlan, ExecutionStep, default_pipeline

    def failing_planner(req, ctx):  # type: ignore[no-untyped-def]
        return ExecutionPlan(steps=[ExecutionStep(id="s1", action="fail_always")])

    rt.pipeline_factory = lambda ctx: default_pipeline(
        executor=rt.executor,
        bus=rt.bus,
        hooks=rt.hooks,
        planner=failing_planner,
    )
    rt.dispatcher.pipeline_factory = rt.pipeline_factory
    rt.handle("fail please")
    health = rt.health()
    assert health["failed_executions"] >= 1
