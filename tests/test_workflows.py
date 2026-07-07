"""Tests for the Atlas Workflow Engine.

Covers state transitions, immutable models, validation (including cycle
detection), the registry, history tracking, templates, the placeholder
executor, the in-memory scheduler, and full engine orchestration
(start / pause / resume / retry / cancel / tick).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from atlas.workflows import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    BaseExecutor,
    BaseScheduler,
    InMemoryScheduler,
    InvalidStateTransitionError,
    PlaceholderExecutor,
    RunNotFound,
    ScheduleKind,
    StateTransition,
    StepResult,
    TemplateRegistry,
    ValidationError,
    WaitSignal,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowEngineError,
    WorkflowHistory,
    WorkflowNotFound,
    WorkflowRegistry,
    WorkflowRun,
    WorkflowSchedule,
    WorkflowState,
    WorkflowStep,
    WorkflowTemplate,
    WorkflowValidationError,
    WorkflowValidator,
    all_states,
    assert_transition,
    can_transition,
    is_active,
    is_terminal,
    legal_targets,
    linear_template,
    retry_template,
    sequential_template,
)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_state_enum_has_eight_states() -> None:
    assert len(list(all_states())) == 8
    assert {s.value for s in all_states()} == {
        "pending",
        "planning",
        "waiting",
        "running",
        "paused",
        "completed",
        "failed",
        "cancelled",
    }


def test_terminal_states_are_terminal() -> None:
    assert set(TERMINAL_STATES) == {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    }


def test_active_states_are_non_terminal() -> None:
    assert set(ACTIVE_STATES) == {
        WorkflowState.PENDING,
        WorkflowState.PLANNING,
        WorkflowState.WAITING,
        WorkflowState.RUNNING,
        WorkflowState.PAUSED,
    }
    assert not (set(ACTIVE_STATES) & set(TERMINAL_STATES))


def test_is_terminal_and_is_active_helpers() -> None:
    assert is_terminal(WorkflowState.COMPLETED)
    assert is_terminal(WorkflowState.FAILED)
    assert is_terminal(WorkflowState.CANCELLED)
    assert not is_terminal(WorkflowState.RUNNING)
    assert is_active(WorkflowState.RUNNING)
    assert is_active(WorkflowState.PENDING)
    assert not is_active(WorkflowState.COMPLETED)


def test_can_transition_legal_paths() -> None:
    assert can_transition(WorkflowState.PENDING, WorkflowState.PLANNING)
    assert can_transition(WorkflowState.PLANNING, WorkflowState.RUNNING)
    assert can_transition(WorkflowState.RUNNING, WorkflowState.PAUSED)
    assert can_transition(WorkflowState.RUNNING, WorkflowState.COMPLETED)
    assert can_transition(WorkflowState.RUNNING, WorkflowState.FAILED)
    assert can_transition(WorkflowState.PAUSED, WorkflowState.RUNNING)
    assert can_transition(WorkflowState.FAILED, WorkflowState.PENDING)


def test_cannot_transition_illegal_paths() -> None:
    assert not can_transition(WorkflowState.COMPLETED, WorkflowState.RUNNING)
    assert not can_transition(WorkflowState.CANCELLED, WorkflowState.RUNNING)
    assert not can_transition(WorkflowState.PENDING, WorkflowState.COMPLETED)
    assert not can_transition(WorkflowState.PAUSED, WorkflowState.COMPLETED)


def test_assert_transition_raises_on_illegal() -> None:
    with pytest.raises(InvalidStateTransitionError):
        assert_transition(WorkflowState.COMPLETED, WorkflowState.RUNNING)
    # self-transition is allowed (idempotent)
    assert_transition(WorkflowState.RUNNING, WorkflowState.RUNNING)


def test_assert_transition_raises_with_correct_attributes() -> None:
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        assert_transition(WorkflowState.COMPLETED, WorkflowState.RUNNING)
    assert exc_info.value.from_state is WorkflowState.COMPLETED
    assert exc_info.value.to_state is WorkflowState.RUNNING
    assert "completed" in str(exc_info.value)
    assert "running" in str(exc_info.value)


def test_legal_targets_returns_reachable_states() -> None:
    targets = legal_targets(WorkflowState.RUNNING)
    assert WorkflowState.PAUSED in targets
    assert WorkflowState.COMPLETED in targets
    assert WorkflowState.PENDING not in targets


def test_legal_targets_for_terminal_state_is_empty() -> None:
    assert set(legal_targets(WorkflowState.COMPLETED)) == set()
    assert set(legal_targets(WorkflowState.CANCELLED)) == set()


def test_transitions_table_covers_every_state() -> None:
    for state in all_states():
        assert state in TRANSITIONS


# ---------------------------------------------------------------------------
# Immutable models
# ---------------------------------------------------------------------------


def test_workflow_step_is_frozen() -> None:
    step = WorkflowStep(id="s1", name="S", action="noop")
    with pytest.raises(dataclasses.FrozenInstanceError):
        step.id = "s2"  # type: ignore[misc]


def test_workflow_definition_is_frozen() -> None:
    defn = WorkflowDefinition(
        id="d1", name="D", steps=[WorkflowStep(id="s", name="S", action="noop")]
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        defn.name = "other"  # type: ignore[misc]


def test_workflow_definition_defaults() -> None:
    defn = WorkflowDefinition(name="Empty")
    assert defn.version == "0.1.0"
    assert defn.steps == []
    assert defn.inputs == {}
    assert defn.outputs == []
    assert defn.metadata == {}
    assert defn.created_at is not None


def test_workflow_run_is_frozen() -> None:
    run = WorkflowRun(definition_id="d1", name="D")
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.state = WorkflowState.COMPLETED  # type: ignore[misc]


def test_workflow_run_with_transition_records_history() -> None:
    run = WorkflowRun(definition_id="d1", name="D")
    assert run.state is WorkflowState.PENDING
    run = run.with_transition(WorkflowState.PLANNING, reason="start")
    assert run.state is WorkflowState.PLANNING
    assert len(run.transitions) == 1
    assert run.transitions[0].from_state is WorkflowState.PENDING
    assert run.transitions[0].to_state is WorkflowState.PLANNING
    assert run.transitions[0].reason == "start"


def test_workflow_run_with_transition_sets_started_at() -> None:
    run = WorkflowRun(definition_id="d1", name="D")
    run = run.with_transition(WorkflowState.PLANNING)
    run = run.with_transition(WorkflowState.RUNNING)
    assert run.started_at is not None


def test_workflow_run_with_transition_sets_paused_at() -> None:
    run = WorkflowRun(definition_id="d1", name="D", state=WorkflowState.RUNNING)
    run = run.with_transition(WorkflowState.PAUSED)
    assert run.paused_at is not None


def test_workflow_run_with_transition_sets_completed_at() -> None:
    run = WorkflowRun(definition_id="d1", name="D", state=WorkflowState.RUNNING)
    run = run.with_transition(WorkflowState.COMPLETED)
    assert run.completed_at is not None


def test_workflow_run_with_step_result_merges_results() -> None:
    run = WorkflowRun(definition_id="d1", name="D")
    result_a = StepResult(step_id="a", success=True, output="A")
    run = run.with_step_result(result_a)
    assert run.step_results["a"] is result_a
    result_b = StepResult(step_id="b", success=True, output="B")
    run = run.with_step_result(result_b)
    assert run.step_results["a"] is result_a
    assert run.step_results["b"] is result_b
    assert run.current_step_id == "b"


def test_workflow_run_is_terminal_helper() -> None:
    pending = WorkflowRun(definition_id="d", name="d")
    assert not pending.is_terminal()
    completed = (
        pending.with_transition(WorkflowState.PLANNING)
        .with_transition(WorkflowState.RUNNING)
        .with_transition(WorkflowState.COMPLETED)
    )
    assert completed.is_terminal()


def test_step_result_defaults() -> None:
    result = StepResult(step_id="s1", success=True)
    assert result.output is None
    assert result.error is None
    assert result.started_at is not None
    assert result.completed_at is None


def test_state_transition_records_from_to_and_reason() -> None:
    t = StateTransition(
        from_state=WorkflowState.PENDING,
        to_state=WorkflowState.PLANNING,
        reason="start",
    )
    assert t.from_state is WorkflowState.PENDING
    assert t.to_state is WorkflowState.PLANNING
    assert t.reason == "start"
    assert t.timestamp is not None


def test_workflow_schedule_defaults() -> None:
    sched = WorkflowSchedule(workflow_id="wf1")
    assert sched.kind is ScheduleKind.ONE_TIME
    assert sched.enabled is True
    assert sched.inputs == {}
    assert sched.interval_seconds is None


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def _valid_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        id="wf_valid",
        name="Valid",
        steps=[
            WorkflowStep(id="s1", name="First", action="noop"),
            WorkflowStep(id="s2", name="Second", action="noop", depends_on=["s1"]),
        ],
    )


def test_validator_accepts_valid_definition() -> None:
    validator = WorkflowValidator()
    assert validator.validate(_valid_definition()) == []


def test_validator_rejects_empty_id() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="", name="X", steps=[WorkflowStep(id="s", name="S", action="noop")]
    )
    errors = validator.validate(defn)
    assert any(e.code == "empty_definition_id" for e in errors)


def test_validator_rejects_empty_name() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="x", name="", steps=[WorkflowStep(id="s", name="S", action="noop")]
    )
    errors = validator.validate(defn)
    assert any(e.code == "empty_definition_name" for e in errors)


def test_validator_rejects_no_steps() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(id="x", name="X", steps=[])
    errors = validator.validate(defn)
    assert any(e.code == "no_steps" for e in errors)


def test_validator_rejects_duplicate_step_ids() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="x",
        name="X",
        steps=[
            WorkflowStep(id="s", name="A", action="noop"),
            WorkflowStep(id="s", name="B", action="noop"),
        ],
    )
    errors = validator.validate(defn)
    assert any(e.code == "duplicate_step_id" for e in errors)


def test_validator_rejects_unknown_dependency() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="x",
        name="X",
        steps=[WorkflowStep(id="s1", name="A", action="noop", depends_on=["missing"])],
    )
    errors = validator.validate(defn)
    assert any(e.code == "unknown_dependency" for e in errors)


def test_validator_rejects_self_dependency() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="x",
        name="X",
        steps=[WorkflowStep(id="s1", name="A", action="noop", depends_on=["s1"])],
    )
    errors = validator.validate(defn)
    assert any(e.code == "self_dependency" for e in errors)


def test_validator_detects_cycle() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="x",
        name="X",
        steps=[
            WorkflowStep(id="a", name="A", action="noop", depends_on=["b"]),
            WorkflowStep(id="b", name="B", action="noop", depends_on=["a"]),
        ],
    )
    errors = validator.validate(defn)
    assert any(e.code == "circular_dependency" for e in errors)


def test_validator_detects_longer_cycle() -> None:
    validator = WorkflowValidator()
    defn = WorkflowDefinition(
        id="x",
        name="X",
        steps=[
            WorkflowStep(id="a", name="A", action="noop", depends_on=["c"]),
            WorkflowStep(id="b", name="B", action="noop", depends_on=["a"]),
            WorkflowStep(id="c", name="C", action="noop", depends_on=["b"]),
        ],
    )
    errors = validator.validate(defn)
    assert any(e.code == "circular_dependency" for e in errors)


def test_validator_validate_or_raise_passes_valid() -> None:
    WorkflowValidator().validate_or_raise(_valid_definition())


def test_validator_validate_or_raise_raises() -> None:
    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator().validate_or_raise(
            WorkflowDefinition(id="", name="", steps=[])
        )
    assert len(exc_info.value.errors) >= 3


def test_validation_error_message_lists_errors() -> None:
    error = WorkflowValidationError(
        [
            ValidationError(code="c1", message="msg1", path="a"),
            ValidationError(code="c2", message="msg2", path="b"),
        ]
    )
    text = str(error)
    assert "2 validation error(s)" in text
    assert "c1" in text
    assert "c2" in text


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_register_and_get() -> None:
    registry = WorkflowRegistry()
    defn = _valid_definition()
    registry.register(defn)
    assert registry.get(defn.id) is defn
    assert registry.contains(defn.id)


def test_registry_register_duplicate_raises() -> None:
    registry = WorkflowRegistry()
    defn = _valid_definition()
    registry.register(defn)
    with pytest.raises(ValueError):
        registry.register(defn)


def test_registry_unregister() -> None:
    registry = WorkflowRegistry()
    defn = _valid_definition()
    registry.register(defn)
    assert registry.unregister(defn.id) is registry  # chaining
    assert not registry.contains(defn.id)
    assert registry.get(defn.id) is None


def test_registry_names_sorted() -> None:
    registry = WorkflowRegistry()
    registry.register(
        WorkflowDefinition(
            id="b", name="B", steps=[WorkflowStep(id="s", name="S", action="noop")]
        )
    )
    registry.register(
        WorkflowDefinition(
            id="a", name="A", steps=[WorkflowStep(id="s", name="S", action="noop")]
        )
    )
    assert registry.names() == ["a", "b"]


def test_registry_len_and_iter() -> None:
    registry = WorkflowRegistry()
    assert len(registry) == 0
    registry.register(_valid_definition())
    assert len(registry) == 1
    assert len(list(iter(registry))) == 1


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def test_history_record_and_get() -> None:
    history = WorkflowHistory()
    run = WorkflowRun(definition_id="d1", name="D")
    history.record(run)
    assert history.get(run.id) is run
    assert run.id in history


def test_history_trajectory_keeps_snapshots() -> None:
    history = WorkflowHistory()
    run = WorkflowRun(definition_id="d1", name="D")
    history.record(run)
    next_run = run.with_transition(WorkflowState.PLANNING)
    history.record(next_run)
    trajectory = history.trajectory(run.id)
    assert len(trajectory) == 2
    assert trajectory[0].state is WorkflowState.PENDING
    assert trajectory[1].state is WorkflowState.PLANNING


def test_history_latest_per_workflow() -> None:
    history = WorkflowHistory()
    first = WorkflowRun(definition_id="d1", name="D")
    history.record(first)
    second = WorkflowRun(definition_id="d1", name="D")
    history.record(second)
    other = WorkflowRun(definition_id="d2", name="D2")
    history.record(other)
    latest = history.latest("d1")
    assert latest is second
    assert history.latest("d2") is other
    assert history.latest("missing") is None


def test_history_list_runs_filtered_by_workflow() -> None:
    history = WorkflowHistory()
    history.record(WorkflowRun(definition_id="d1", name="D"))
    history.record(WorkflowRun(definition_id="d2", name="D2"))
    history.record(WorkflowRun(definition_id="d1", name="D"))
    assert len(history.list_runs(workflow_id="d1")) == 2
    assert len(history.list_runs(workflow_id="d2")) == 1
    assert len(history.list_runs()) == 3


def test_history_list_runs_respects_limit() -> None:
    history = WorkflowHistory()
    for _ in range(5):
        history.record(WorkflowRun(definition_id="d1", name="D"))
    assert len(history.list_runs(limit=3)) == 3


def test_history_count() -> None:
    history = WorkflowHistory()
    history.record(WorkflowRun(definition_id="d1", name="D"))
    history.record(WorkflowRun(definition_id="d1", name="D"))
    history.record(WorkflowRun(definition_id="d2", name="D2"))
    assert history.count() == 3
    assert history.count(workflow_id="d1") == 2


def test_history_clear() -> None:
    history = WorkflowHistory()
    history.record(WorkflowRun(definition_id="d1", name="D"))
    history.clear()
    assert len(history) == 0


def test_history_unknown_run_returns_none() -> None:
    history = WorkflowHistory()
    assert history.get("missing") is None
    assert history.trajectory("missing") == []


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def test_executor_noop_action_succeeds() -> None:
    executor = PlaceholderExecutor()
    step = WorkflowStep(id="s1", name="S", action="noop")
    result = executor.execute_step(step, context={})
    assert result.success
    assert result.output == "noop"
    assert result.completed_at is not None


def test_executor_echo_action_returns_params() -> None:
    executor = PlaceholderExecutor()
    step = WorkflowStep(id="s1", name="S", action="echo", params={"msg": "hi"})
    result = executor.execute_step(step, context={})
    assert result.success
    assert result.output == {"msg": "hi"}


def test_executor_fail_action_returns_failure() -> None:
    executor = PlaceholderExecutor()
    step = WorkflowStep(id="s1", name="S", action="fail", params={"message": "boom"})
    result = executor.execute_step(step, context={})
    assert not result.success
    assert "boom" in (result.error or "")


def test_executor_unknown_action_returns_failure() -> None:
    executor = PlaceholderExecutor()
    step = WorkflowStep(id="s1", name="S", action="not_registered")
    result = executor.execute_step(step, context={})
    assert not result.success
    assert "not_registered" in (result.error or "")


def test_executor_wait_action_returns_wait_signal() -> None:
    executor = PlaceholderExecutor()
    step = WorkflowStep(id="s1", name="S", action="wait", params={"reason": "approval"})
    result = executor.execute_step(step, context={})
    assert result.success
    assert isinstance(result.output, WaitSignal)
    assert result.output.reason == "approval"


def test_executor_sleep_action_returns_duration() -> None:
    executor = PlaceholderExecutor()
    step = WorkflowStep(id="s1", name="S", action="sleep", params={"seconds": 5})
    result = executor.execute_step(step, context={})
    assert result.success
    assert result.output == {"slept_seconds": 5}


def test_executor_writes_output_to_context() -> None:
    executor = PlaceholderExecutor()
    context: dict[str, object] = {}
    step = WorkflowStep(id="s1", name="S", action="echo", params={"v": 1})
    executor.execute_step(step, context=context)
    assert "s1" in context


def test_executor_register_custom_action() -> None:
    executor = PlaceholderExecutor()

    def double(params, context):  # type: ignore[no-untyped-def]
        return params.get("value", 0) * 2

    executor.register_action("double", double)
    step = WorkflowStep(id="s1", name="S", action="double", params={"value": 21})
    result = executor.execute_step(step, context={})
    assert result.success
    assert result.output == 42


def test_executor_custom_action_raising_marks_failure() -> None:
    executor = PlaceholderExecutor()

    def boom(params, context):  # type: ignore[no-untyped-def]
        raise ValueError("kaboom")

    executor.register_action("boom", boom)
    step = WorkflowStep(id="s1", name="S", action="boom")
    result = executor.execute_step(step, context={})
    assert not result.success
    assert "kaboom" in (result.error or "")


def test_executor_known_actions_lists_builtins() -> None:
    executor = PlaceholderExecutor()
    actions = executor.known_actions()
    for builtin in ("noop", "echo", "fail", "wait", "sleep"):
        assert builtin in actions


def test_executor_overrides_builtin_via_constructor() -> None:
    def custom_noop(params, context):  # type: ignore[no-untyped-def]
        return "custom"

    executor = PlaceholderExecutor(actions={"noop": custom_noop})
    step = WorkflowStep(id="s", name="S", action="noop")
    result = executor.execute_step(step, context={})
    assert result.output == "custom"


def test_executor_register_action_rejects_empty_name() -> None:
    executor = PlaceholderExecutor()
    with pytest.raises(ValueError):
        executor.register_action("", lambda p, c: None)


def test_executor_is_base_executor() -> None:
    assert issubclass(PlaceholderExecutor, BaseExecutor)


def test_wait_signal_equality() -> None:
    a = WaitSignal(reason="r", foo=1)
    b = WaitSignal(reason="r", foo=1)
    c = WaitSignal(reason="other", foo=1)
    assert a == b
    assert a != c


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


def test_scheduler_register_and_get() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        run_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    sched.register(schedule)
    assert sched.get(schedule.id) is not None
    assert sched.contains(schedule.id)


def test_scheduler_register_duplicate_raises() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(id="s1", workflow_id="wf1")
    sched.register(schedule)
    with pytest.raises(ValueError):
        sched.register(schedule)


def test_scheduler_unregister() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(id="s1", workflow_id="wf1")
    sched.register(schedule)
    assert sched.unregister("s1") is True
    assert sched.unregister("s1") is False


def test_scheduler_due_filters_by_next_run_at() -> None:
    sched = InMemoryScheduler()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    past = WorkflowSchedule(
        id="past",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=now - timedelta(minutes=5),
    )
    future = WorkflowSchedule(
        id="future",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=now + timedelta(minutes=5),
    )
    sched.register(past)
    sched.register(future)
    due = sched.due(now)
    assert {s.id for s in due} == {"past"}


def test_scheduler_due_excludes_disabled() -> None:
    sched = InMemoryScheduler()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=now - timedelta(minutes=5),
        enabled=False,
    )
    sched.register(schedule)
    assert sched.due(now) == []


def test_scheduler_mark_run_disables_one_time() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    sched.register(schedule)
    ran_at = datetime(2026, 1, 1, 12, 1, tzinfo=UTC)
    updated = sched.mark_run("s1", ran_at)
    assert updated is not None
    assert updated.enabled is False
    assert updated.next_run_at is None
    assert updated.last_run_at == ran_at


def test_scheduler_mark_run_advances_interval() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=60,
        next_run_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    sched.register(schedule)
    ran_at = datetime(2026, 1, 1, 12, 0, 5, tzinfo=UTC)
    updated = sched.mark_run("s1", ran_at)
    assert updated is not None
    assert updated.enabled is True
    assert updated.next_run_at == ran_at + timedelta(seconds=60)


def test_scheduler_mark_run_advances_cron_placeholder() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.CRON,
        cron_expr="0 0 * * *",
        next_run_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    sched.register(schedule)
    ran_at = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
    updated = sched.mark_run("s1", ran_at)
    assert updated is not None
    assert updated.next_run_at == ran_at + timedelta(hours=24)


def test_scheduler_mark_run_unknown_returns_none() -> None:
    sched = InMemoryScheduler()
    assert sched.mark_run("missing", datetime.now(UTC)) is None


def test_scheduler_normalizes_one_time_next_run_at() -> None:
    sched = InMemoryScheduler()
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        run_at=run_at,
    )
    sched.register(schedule)
    stored = sched.get("s1")
    assert stored is not None
    assert stored.next_run_at == run_at


def test_scheduler_normalizes_interval_next_run_at() -> None:
    sched = InMemoryScheduler()
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=30,
    )
    sched.register(schedule)
    stored = sched.get("s1")
    assert stored is not None
    assert stored.next_run_at is not None


def test_scheduler_is_base_scheduler() -> None:
    assert issubclass(InMemoryScheduler, BaseScheduler)


def test_scheduler_names_sorted() -> None:
    sched = InMemoryScheduler()
    sched.register(WorkflowSchedule(id="b", workflow_id="wf1"))
    sched.register(WorkflowSchedule(id="a", workflow_id="wf1"))
    assert sched.names() == ["a", "b"]


def test_scheduler_len() -> None:
    sched = InMemoryScheduler()
    assert len(sched) == 0
    sched.register(WorkflowSchedule(id="a", workflow_id="wf1"))
    assert len(sched) == 1


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_template_instantiate_returns_definition() -> None:
    template = linear_template(
        template_id="lt",
        name="Linear",
        actions=[("s1", "noop"), ("s2", "echo")],
    )
    defn = template.instantiate()
    assert defn.name == "Linear"
    assert len(defn.steps) == 2
    assert defn.steps[0].depends_on == []
    assert defn.steps[1].depends_on == ["s1"]


def test_template_instantiate_passes_params_to_steps() -> None:
    template = linear_template("lt", "Linear", [("s1", "echo")])
    defn = template.instantiate(target="value")
    assert defn.steps[0].params == {"target": "value"}


def test_template_registry_register_and_instantiate() -> None:
    registry = TemplateRegistry()
    template = linear_template("lt", "Linear", [("s1", "noop")])
    registry.register(template)
    defn = registry.instantiate("lt")
    assert len(defn.steps) == 1


def test_template_registry_register_duplicate_raises() -> None:
    registry = TemplateRegistry()
    template = linear_template("lt", "Linear", [("s1", "noop")])
    registry.register(template)
    with pytest.raises(ValueError):
        registry.register(template)


def test_template_registry_instantiate_unknown_raises() -> None:
    registry = TemplateRegistry()
    with pytest.raises(KeyError):
        registry.instantiate("missing")


def test_template_registry_get_and_contains() -> None:
    registry = TemplateRegistry()
    template = linear_template("lt", "Linear", [("s1", "noop")])
    registry.register(template)
    assert registry.contains("lt")
    assert registry.get("lt") is template


def test_template_registry_unregister() -> None:
    registry = TemplateRegistry()
    template = linear_template("lt", "Linear", [("s1", "noop")])
    registry.register(template)
    assert registry.unregister("lt") is True
    assert registry.unregister("lt") is False


def test_template_registry_len_and_iter() -> None:
    registry = TemplateRegistry()
    registry.register(linear_template("a", "A", [("s", "noop")]))
    registry.register(linear_template("b", "B", [("s", "noop")]))
    assert len(registry) == 2
    assert len(list(iter(registry))) == 2


def test_sequential_template_no_dependencies() -> None:
    template = sequential_template(
        "st",
        "Sequential",
        [("s1", "noop", {}), ("s2", "echo", {"x": 1})],
    )
    defn = template.instantiate()
    assert defn.steps[0].depends_on == []
    assert defn.steps[1].depends_on == []
    assert defn.steps[1].params["x"] == 1


def test_retry_template_generates_attempts() -> None:
    template = retry_template("rt", "Retry", "fail", max_attempts=3)
    defn = template.instantiate()
    assert len(defn.steps) == 3
    assert defn.steps[0].id == "attempt_1"
    assert defn.steps[2].id == "attempt_3"
    # All but the last are optional.
    assert defn.steps[0].optional is True
    assert defn.steps[2].optional is False


def test_retry_template_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        retry_template("rt", "Retry", "fail", max_attempts=0)


def test_template_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        WorkflowTemplate(
            template_id="", name="X", builder=lambda p: WorkflowDefinition(name="X")
        )


def test_template_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        WorkflowTemplate(
            template_id="t", name="", builder=lambda p: WorkflowDefinition(name="X")
        )


def test_template_rejects_none_builder() -> None:
    with pytest.raises(ValueError):
        WorkflowTemplate(template_id="t", name="X", builder=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Engine — registration & runs
# ---------------------------------------------------------------------------


def _engine_with_workflow() -> tuple[WorkflowEngine, WorkflowDefinition]:
    engine = WorkflowEngine()
    defn = WorkflowDefinition(
        id="wf1",
        name="Demo",
        steps=[
            WorkflowStep(id="s1", name="First", action="noop"),
            WorkflowStep(id="s2", name="Second", action="echo", params={"v": 1}),
        ],
    )
    engine.register_workflow(defn)
    return engine, defn


def test_engine_register_workflow_validates_by_default() -> None:
    engine = WorkflowEngine()
    bad = WorkflowDefinition(id="bad", name="", steps=[])
    with pytest.raises(WorkflowValidationError):
        engine.register_workflow(bad)


def test_engine_register_workflow_can_skip_validation() -> None:
    engine = WorkflowEngine()
    bad = WorkflowDefinition(id="bad", name="", steps=[])
    engine.register_workflow(bad, validate=False)
    assert engine.registry.contains("bad")


def test_engine_get_workflow_raises_on_missing() -> None:
    engine = WorkflowEngine()
    with pytest.raises(WorkflowNotFound):
        engine.get_workflow("missing")


def test_engine_create_run_merges_inputs() -> None:
    engine, defn = _engine_with_workflow()
    run = engine.create_run("wf1", inputs={"extra": "value"})
    assert run.definition_id == "wf1"
    assert run.inputs == {"extra": "value"}
    assert run.state is WorkflowState.PENDING


def test_engine_create_run_unknown_workflow_raises() -> None:
    engine = WorkflowEngine()
    with pytest.raises(WorkflowNotFound):
        engine.create_run("missing")


def test_engine_get_run_raises_on_missing() -> None:
    engine = WorkflowEngine()
    with pytest.raises(RunNotFound):
        engine.get_run("missing")


def test_engine_list_workflows() -> None:
    engine, _ = _engine_with_workflow()
    assert len(engine.list_workflows()) == 1


def test_engine_list_runs_filtered() -> None:
    engine, _ = _engine_with_workflow()
    engine.create_run("wf1")
    assert len(engine.list_runs(workflow_id="wf1")) == 1
    assert engine.list_runs(workflow_id="other") == []


# ---------------------------------------------------------------------------
# Engine — execution control
# ---------------------------------------------------------------------------


def test_engine_start_runs_to_completion() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    run = engine.start(run.id)
    assert run.state is WorkflowState.COMPLETED
    assert set(run.step_results.keys()) == {"s1", "s2"}
    assert run.completed_at is not None
    assert run.started_at is not None


def test_engine_start_records_transitions() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    run = engine.start(run.id)
    states = [t.to_state for t in run.transitions]
    assert states == [
        WorkflowState.PLANNING,
        WorkflowState.RUNNING,
        WorkflowState.COMPLETED,
    ]


def test_engine_start_with_max_steps_pauses() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    run = engine.start(run.id, max_steps=1)
    assert run.state is WorkflowState.PAUSED
    assert "s1" in run.step_results
    assert "s2" not in run.step_results


def test_engine_resume_from_pause() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    run = engine.start(run.id, max_steps=1)
    assert run.state is WorkflowState.PAUSED
    run = engine.resume(run.id)
    assert run.state is WorkflowState.COMPLETED
    assert "s2" in run.step_results


def test_engine_pause_pending_run() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    run = engine.pause(run.id)
    assert run.state is WorkflowState.PAUSED


def test_engine_pause_via_request_flag() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    engine.request_pause(run.id)
    run = engine.start(run.id)
    assert run.state is WorkflowState.PAUSED
    assert run.step_results == {}


def test_engine_resume_from_pause_completes() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    engine.pause(run.id)
    run = engine.resume(run.id)
    assert run.state is WorkflowState.COMPLETED


def test_engine_start_already_running_raises() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    # Simulate an already-running state.
    engine.history.record(
        run.with_transition(WorkflowState.PLANNING).with_transition(
            WorkflowState.RUNNING
        )
    )
    with pytest.raises(WorkflowEngineError):
        engine.start(run.id)


def test_engine_start_terminal_raises() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    engine.cancel(run.id)
    with pytest.raises(WorkflowEngineError):
        engine.start(run.id)


def test_engine_pause_terminal_raises() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    engine.cancel(run.id)
    with pytest.raises(WorkflowEngineError):
        engine.pause(run.id)


def test_engine_resume_invalid_state_raises() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    with pytest.raises(WorkflowEngineError):
        engine.resume(run.id)


def test_engine_cancel_pending_run() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    run = engine.cancel(run.id)
    assert run.state is WorkflowState.CANCELLED
    assert run.completed_at is not None


def test_engine_cancel_terminal_raises() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    engine.cancel(run.id)
    with pytest.raises(WorkflowEngineError):
        engine.cancel(run.id)


def test_engine_retry_failed_run() -> None:
    engine = WorkflowEngine()
    defn = WorkflowDefinition(
        id="wf_fail",
        name="Failing",
        steps=[
            WorkflowStep(id="s1", name="S", action="fail", params={"message": "boom"})
        ],
    )
    engine.register_workflow(defn)
    run = engine.create_run("wf_fail")
    run = engine.start(run.id)
    assert run.state is WorkflowState.FAILED

    retry_run = engine.retry(run.id)
    assert retry_run.parent_run_id == run.id
    assert retry_run.attempts == 2
    assert retry_run.state is WorkflowState.PENDING


def test_engine_retry_non_failed_raises() -> None:
    engine, _ = _engine_with_workflow()
    run = engine.create_run("wf1")
    with pytest.raises(WorkflowEngineError):
        engine.retry(run.id)


def test_engine_start_failed_step_marks_failed() -> None:
    engine = WorkflowEngine()
    defn = WorkflowDefinition(
        id="wf_fail",
        name="Failing",
        steps=[
            WorkflowStep(id="s1", name="First", action="noop"),
            WorkflowStep(
                id="s2", name="Second", action="fail", params={"message": "boom"}
            ),
            WorkflowStep(id="s3", name="Third", action="noop"),
        ],
    )
    engine.register_workflow(defn)
    run = engine.create_run("wf_fail")
    run = engine.start(run.id)
    assert run.state is WorkflowState.FAILED
    assert "s1" in run.step_results
    assert "s2" in run.step_results
    assert "s3" not in run.step_results
    assert run.error is not None
    assert "boom" in run.error


def test_engine_optional_step_failure_does_not_fail_run() -> None:
    engine = WorkflowEngine()
    defn = WorkflowDefinition(
        id="wf_opt",
        name="Optional",
        steps=[
            WorkflowStep(
                id="s1",
                name="Optional",
                action="fail",
                params={"message": "x"},
                optional=True,
            ),
            WorkflowStep(id="s2", name="Required", action="noop"),
        ],
    )
    engine.register_workflow(defn)
    run = engine.create_run("wf_opt")
    run = engine.start(run.id)
    assert run.state is WorkflowState.COMPLETED
    assert not run.step_results["s1"].success
    assert run.step_results["s2"].success


def test_engine_step_dependencies_respected() -> None:
    engine = WorkflowEngine()
    defn = WorkflowDefinition(
        id="wf_dep",
        name="Dep",
        steps=[
            WorkflowStep(id="a", name="A", action="noop"),
            WorkflowStep(id="b", name="B", action="noop", depends_on=["a"]),
            WorkflowStep(id="c", name="C", action="noop", depends_on=["b"]),
        ],
    )
    engine.register_workflow(defn)
    run = engine.create_run("wf_dep")
    run = engine.start(run.id)
    assert run.state is WorkflowState.COMPLETED
    assert set(run.step_results.keys()) == {"a", "b", "c"}


def test_engine_wait_signal_transitions_to_waiting() -> None:
    engine = WorkflowEngine()
    defn = WorkflowDefinition(
        id="wf_wait",
        name="Wait",
        steps=[
            WorkflowStep(
                id="s1", name="First", action="wait", params={"reason": "approval"}
            ),
            WorkflowStep(id="s2", name="Second", action="noop"),
        ],
    )
    engine.register_workflow(defn)
    run = engine.create_run("wf_wait")
    run = engine.start(run.id)
    assert run.state is WorkflowState.WAITING
    assert "s1" in run.step_results
    assert "s2" not in run.step_results
    # Resuming should continue from s2.
    run = engine.resume(run.id)
    assert run.state is WorkflowState.COMPLETED
    assert "s2" in run.step_results


def test_engine_context_carries_outputs_between_steps() -> None:
    engine = WorkflowEngine()

    def add(params, context):  # type: ignore[no-untyped-def]
        return params["x"] + params["y"]

    def read_context(params, context):  # type: ignore[no-untyped-def]
        return context.get("s1")

    executor = PlaceholderExecutor(actions={"add": add, "read": read_context})
    engine = WorkflowEngine(executor=executor)
    defn = WorkflowDefinition(
        id="wf_ctx",
        name="Ctx",
        steps=[
            WorkflowStep(id="s1", name="Add", action="add", params={"x": 1, "y": 2}),
            WorkflowStep(id="s2", name="Read", action="read", depends_on=["s1"]),
        ],
    )
    engine.register_workflow(defn)
    run = engine.create_run("wf_ctx")
    run = engine.start(run.id)
    assert run.state is WorkflowState.COMPLETED
    assert run.step_results["s2"].output == 3


# ---------------------------------------------------------------------------
# Engine — scheduling
# ---------------------------------------------------------------------------


def test_engine_register_schedule_unknown_workflow_raises() -> None:
    engine = WorkflowEngine()
    schedule = WorkflowSchedule(id="s1", workflow_id="missing")
    with pytest.raises(WorkflowNotFound):
        engine.register_schedule(schedule)


def test_engine_tick_fires_due_schedule() -> None:
    engine, _ = _engine_with_workflow()
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        run_at=run_at,
    )
    engine.register_schedule(schedule)
    started = engine.tick(now=run_at + timedelta(minutes=1))
    assert len(started) == 1
    assert started[0].state is WorkflowState.COMPLETED


def test_engine_tick_skips_not_due_schedule() -> None:
    engine, _ = _engine_with_workflow()
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        run_at=run_at,
    )
    engine.register_schedule(schedule)
    started = engine.tick(now=run_at - timedelta(minutes=1))
    assert started == []


def test_engine_tick_disables_one_time_schedule_after_firing() -> None:
    engine, _ = _engine_with_workflow()
    run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.ONE_TIME,
        run_at=run_at,
    )
    engine.register_schedule(schedule)
    engine.tick(now=run_at + timedelta(minutes=1))
    updated = engine.scheduler.get("s1")
    assert updated is not None
    assert updated.enabled is False
    # Second tick should not re-fire.
    started = engine.tick(now=run_at + timedelta(minutes=2))
    assert started == []


def test_engine_tick_advances_interval_schedule() -> None:
    engine, _ = _engine_with_workflow()
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="wf1",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=60,
        next_run_at=start,
    )
    engine.register_schedule(schedule)
    started = engine.tick(now=start)
    assert len(started) == 1
    updated = engine.scheduler.get("s1")
    assert updated is not None
    assert updated.next_run_at == start + timedelta(seconds=60)
    # Next tick at the same moment should not fire.
    assert engine.tick(now=start) == []
    # Tick at the next scheduled moment should fire again.
    started2 = engine.tick(now=start + timedelta(seconds=60))
    assert len(started2) == 1


def test_engine_tick_skips_unknown_workflow_schedule() -> None:
    engine = WorkflowEngine()
    schedule = WorkflowSchedule(
        id="s1",
        workflow_id="missing",
        kind=ScheduleKind.ONE_TIME,
        next_run_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    # Bypass the engine's workflow-existence check by registering directly
    # with the scheduler.
    engine.scheduler.register(schedule)
    started = engine.tick(now=datetime(2026, 1, 2, tzinfo=UTC))
    assert started == []


def test_engine_unregister_schedule() -> None:
    engine, _ = _engine_with_workflow()
    schedule = WorkflowSchedule(id="s1", workflow_id="wf1")
    engine.register_schedule(schedule)
    assert engine.unregister_schedule("s1") is True
    assert engine.unregister_schedule("s1") is False


def test_engine_list_schedules() -> None:
    engine, _ = _engine_with_workflow()
    engine.register_schedule(WorkflowSchedule(id="a", workflow_id="wf1"))
    engine.register_schedule(WorkflowSchedule(id="b", workflow_id="wf1"))
    assert {s.id for s in engine.list_schedules()} == {"a", "b"}


# ---------------------------------------------------------------------------
# Engine — templates & dependency injection
# ---------------------------------------------------------------------------


def test_engine_instantiate_template_registers_workflow() -> None:
    engine = WorkflowEngine()
    template = linear_template("lt", "Linear", [("s1", "noop")])
    engine.templates.register(template)
    defn = engine.instantiate_template("lt")
    assert engine.registry.contains(defn.id)


def test_engine_accepts_injected_dependencies() -> None:
    executor = PlaceholderExecutor()
    scheduler = InMemoryScheduler()
    history = WorkflowHistory()
    validator = WorkflowValidator()
    registry = WorkflowRegistry()
    templates = TemplateRegistry()
    engine = WorkflowEngine(
        registry=registry,
        executor=executor,
        scheduler=scheduler,
        history=history,
        validator=validator,
        templates=templates,
    )
    assert engine.registry is registry
    assert engine.executor is executor
    assert engine.scheduler is scheduler
    assert engine.history is history
    assert engine.validator is validator
    assert engine.templates is templates


def test_engine_repr_summarizes_state() -> None:
    engine, _ = _engine_with_workflow()
    engine.create_run("wf1")
    text = repr(engine)
    assert "WorkflowEngine" in text
    assert "workflows=1" in text
    assert "runs=1" in text
