"""Tests for the Atlas Execution Engine.

Covers models, strategies, planner, dispatcher, executor, reviewer,
reporter, engine, and end-to-end execution. All tests are deterministic
and offline — no external APIs are called.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from atlas.execution import (
    DEPENDENCY_AWARE,
    FALLBACK_ENABLED,
    INTERACTIVE,
    RETRY_AGGRESSIVE,
    TERMINAL_STATUSES,
    BaseDispatcher,
    BaseExecutor,
    BasePlanner,
    BaseReporter,
    BaseReviewer,
    DispatchResult,
    ExecutionContext,
    ExecutionDispatcher,
    ExecutionEngine,
    ExecutionEngineError,
    ExecutionExecutor,
    ExecutionHistory,
    ExecutionHistoryEntry,
    ExecutionMetrics,
    ExecutionPlan,
    ExecutionPlanner,
    ExecutionReport,
    ExecutionReporter,
    ExecutionResult,
    ExecutionReview,
    ExecutionReviewer,
    ExecutionStatus,
    ExecutionStrategy,
    ExecutionSummary,
    ExecutionTask,
    ExecutorError,
    Priority,
    RetryPolicy,
    TaskKind,
    TaskResolution,
    TaskReview,
    all_strategies,
    is_dependency_aware,
    is_fallback_enabled,
    is_interactive,
    is_retry_aggressive,
)

# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    """Tests for atlas.execution.models."""

    def test_execution_status_has_seven_values(self) -> None:
        assert len(list(ExecutionStatus)) == 7

    def test_terminal_statuses(self) -> None:
        assert set(TERMINAL_STATUSES) == {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.SKIPPED,
        }

    def test_task_kind_has_seven_values(self) -> None:
        assert len(list(TaskKind)) == 7

    def test_priority_ordering(self) -> None:
        assert Priority.CRITICAL > Priority.HIGH > Priority.NORMAL > Priority.LOW

    def test_execution_task_is_frozen(self) -> None:
        task = ExecutionTask(id="t1", name="T", action="noop")
        with pytest.raises(dataclasses.FrozenInstanceError):
            task.name = "other"  # type: ignore[misc]

    def test_execution_task_defaults(self) -> None:
        task = ExecutionTask()
        assert task.kind is TaskKind.CUSTOM
        assert task.priority is Priority.NORMAL
        assert task.optional is False
        assert task.dependencies == []
        assert task.params == {}
        assert task.retry_policy.max_attempts == 3

    def test_execution_plan_is_frozen(self) -> None:
        plan = ExecutionPlan(goal="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.goal = "other"  # type: ignore[misc]

    def test_execution_plan_task_ids(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(id="a", name="A", action="noop"),
                ExecutionTask(id="b", name="B", action="noop"),
            ],
        )
        assert plan.task_ids() == ["a", "b"]

    def test_execution_plan_task_by_id(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="a", name="A", action="noop")],
        )
        assert plan.task_by_id("a") is not None
        assert plan.task_by_id("missing") is None

    def test_execution_plan_dependencies_of(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(id="a", name="A", action="noop"),
                ExecutionTask(id="b", name="B", action="noop", dependencies=["a"]),
            ],
        )
        assert plan.dependencies_of("b") == ["a"]
        assert plan.dependencies_of("a") == []
        assert plan.dependencies_of("missing") == []

    def test_execution_result_success_property(self) -> None:
        r = ExecutionResult(task_id="t", status=ExecutionStatus.COMPLETED)
        assert r.success is True
        r2 = ExecutionResult(task_id="t", status=ExecutionStatus.FAILED)
        assert r2.success is False

    def test_execution_result_duration(self) -> None:
        start = datetime.now(UTC) - timedelta(seconds=1)
        end = datetime.now(UTC)
        r = ExecutionResult(
            task_id="t",
            status=ExecutionStatus.COMPLETED,
            started_at=start,
            completed_at=end,
        )
        assert r.duration_seconds >= 0.9

    def test_execution_result_is_frozen(self) -> None:
        r = ExecutionResult(task_id="t")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.status = ExecutionStatus.FAILED  # type: ignore[misc]

    def test_execution_context_with_plan(self) -> None:
        ctx = ExecutionContext(goal="g")
        plan = ExecutionPlan(goal="g")
        ctx2 = ctx.with_plan(plan)
        assert ctx2.plan is plan
        assert ctx.plan is None  # original unchanged

    def test_execution_context_with_result(self) -> None:
        ctx = ExecutionContext(goal="g")
        r = ExecutionResult(task_id="t", status=ExecutionStatus.COMPLETED)
        ctx2 = ctx.with_result(r)
        assert ctx2.results["t"] is r
        assert "t" not in ctx.results  # original unchanged

    def test_execution_context_with_artifact(self) -> None:
        ctx = ExecutionContext(goal="g")
        ctx2 = ctx.with_artifact("key", "value")
        assert ctx2.artifacts["key"] == "value"
        assert "key" not in ctx.artifacts

    def test_execution_context_is_terminal_no_plan(self) -> None:
        ctx = ExecutionContext(goal="g")
        assert ctx.is_terminal() is False

    def test_execution_context_is_terminal_all_done(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t", name="T", action="noop")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t", status=ExecutionStatus.COMPLETED)
        )
        assert ctx.is_terminal() is True

    def test_execution_context_is_terminal_not_all_done(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(id="t1", name="T1", action="noop"),
                ExecutionTask(id="t2", name="T2", action="noop"),
            ],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.COMPLETED)
        )
        assert ctx.is_terminal() is False

    def test_execution_metrics_defaults(self) -> None:
        m = ExecutionMetrics()
        assert m.total_tasks == 0
        assert m.providers_used == frozenset()

    def test_execution_summary_defaults(self) -> None:
        s = ExecutionSummary(execution_id="e")
        assert s.status is ExecutionStatus.PENDING
        assert s.overall_quality_score == 0.0

    def test_execution_report_success_property(self) -> None:
        r = ExecutionReport(
            execution_id="e",
            status=ExecutionStatus.COMPLETED,
        )
        assert r.success is True

    def test_execution_report_to_dict(self) -> None:
        r = ExecutionReport(execution_id="e", goal="g")
        d = r.to_dict()
        assert d["execution_id"] == "e"
        assert d["goal"] == "g"

    def test_retry_policy_defaults(self) -> None:
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.backoff_seconds == 1.0
        assert p.max_backoff_seconds == 60.0
        assert p.retryable_errors == ()

    def test_retry_policy_is_frozen(self) -> None:
        p = RetryPolicy()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.max_attempts = 5  # type: ignore[misc]

    def test_execution_history_record_and_get(self) -> None:
        h = ExecutionHistory()
        entry = ExecutionHistoryEntry(execution_id="e1", goal="g")
        h.record(entry)
        assert h.get("e1") is entry
        assert len(h) == 1

    def test_execution_history_list_newest_first(self) -> None:
        h = ExecutionHistory()
        h.record(ExecutionHistoryEntry(execution_id="e1"))
        h.record(ExecutionHistoryEntry(execution_id="e2"))
        listed = h.list()
        assert listed[0].execution_id == "e2"
        assert listed[1].execution_id == "e1"

    def test_execution_history_list_limit(self) -> None:
        h = ExecutionHistory()
        for i in range(5):
            h.record(ExecutionHistoryEntry(execution_id=f"e{i}"))
        assert len(h.list(limit=2)) == 2

    def test_execution_history_get_missing(self) -> None:
        h = ExecutionHistory()
        assert h.get("missing") is None

    def test_execution_history_clear(self) -> None:
        h = ExecutionHistory()
        h.record(ExecutionHistoryEntry(execution_id="e1"))
        h.clear()
        assert len(h) == 0

    def test_execution_history_contains(self) -> None:
        h = ExecutionHistory()
        h.record(ExecutionHistoryEntry(execution_id="e1"))
        assert "e1" in h
        assert "e2" not in h

    def test_execution_history_iter(self) -> None:
        h = ExecutionHistory()
        h.record(ExecutionHistoryEntry(execution_id="e1"))
        h.record(ExecutionHistoryEntry(execution_id="e2"))
        ids = [e.execution_id for e in h]
        assert ids == ["e1", "e2"]


# ===========================================================================
# Strategy
# ===========================================================================


class TestStrategy:
    """Tests for atlas.execution.strategy."""

    def test_strategy_has_eight_values(self) -> None:
        assert len(list(ExecutionStrategy)) == 8

    def test_all_strategies_returns_tuple(self) -> None:
        strategies = all_strategies()
        assert isinstance(strategies, tuple)
        assert len(strategies) == 8

    def test_dependency_aware_strategies(self) -> None:
        assert ExecutionStrategy.PARALLEL in DEPENDENCY_AWARE
        assert ExecutionStrategy.PRIORITY in DEPENDENCY_AWARE
        assert ExecutionStrategy.DEPENDENCY in DEPENDENCY_AWARE
        assert ExecutionStrategy.AUTOMATIC in DEPENDENCY_AWARE
        assert ExecutionStrategy.SEQUENTIAL not in DEPENDENCY_AWARE

    def test_interactive_strategies(self) -> None:
        assert ExecutionStrategy.MANUAL in INTERACTIVE
        assert ExecutionStrategy.AUTOMATIC not in INTERACTIVE

    def test_retry_aggressive_strategies(self) -> None:
        assert ExecutionStrategy.RETRY in RETRY_AGGRESSIVE
        assert ExecutionStrategy.AUTOMATIC not in RETRY_AGGRESSIVE

    def test_fallback_enabled_strategies(self) -> None:
        assert ExecutionStrategy.FALLBACK in FALLBACK_ENABLED
        assert ExecutionStrategy.AUTOMATIC not in FALLBACK_ENABLED

    def test_is_dependency_aware_helper(self) -> None:
        assert is_dependency_aware(ExecutionStrategy.PARALLEL) is True
        assert is_dependency_aware(ExecutionStrategy.SEQUENTIAL) is False

    def test_is_interactive_helper(self) -> None:
        assert is_interactive(ExecutionStrategy.MANUAL) is True
        assert is_interactive(ExecutionStrategy.AUTOMATIC) is False

    def test_is_retry_aggressive_helper(self) -> None:
        assert is_retry_aggressive(ExecutionStrategy.RETRY) is True
        assert is_retry_aggressive(ExecutionStrategy.AUTOMATIC) is False

    def test_is_fallback_enabled_helper(self) -> None:
        assert is_fallback_enabled(ExecutionStrategy.FALLBACK) is True
        assert is_fallback_enabled(ExecutionStrategy.AUTOMATIC) is False


# ===========================================================================
# Planner
# ===========================================================================


class TestPlanner:
    """Tests for atlas.execution.planner."""

    def test_planner_website_template(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Create website for portfolio")
        assert len(plan.tasks) == 6
        kinds = [t.kind for t in plan.tasks]
        assert TaskKind.RESEARCH in kinds
        assert TaskKind.GENERATE in kinds
        assert TaskKind.TEST in kinds
        assert TaskKind.GIT in kinds
        assert TaskKind.DEPLOY in kinds

    def test_planner_research_template(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Research quantum computing")
        assert len(plan.tasks) == 1
        assert plan.tasks[0].kind is TaskKind.RESEARCH

    def test_planner_code_template(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Generate code for sorting algorithm")
        assert len(plan.tasks) == 3
        assert plan.tasks[0].kind is TaskKind.RESEARCH
        assert plan.tasks[1].kind is TaskKind.GENERATE
        assert plan.tasks[2].kind is TaskKind.TEST

    def test_planner_deploy_template(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Deploy to production")
        assert len(plan.tasks) == 3
        assert plan.tasks[0].kind is TaskKind.TEST
        assert plan.tasks[1].kind is TaskKind.GIT
        assert plan.tasks[2].kind is TaskKind.DEPLOY

    def test_planner_custom_template(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Do something unusual")
        assert len(plan.tasks) == 1
        assert plan.tasks[0].kind is TaskKind.CUSTOM

    def test_planner_empty_goal_raises(self) -> None:
        planner = ExecutionPlanner()
        with pytest.raises(ValueError):
            planner.plan("")

    def test_planner_whitespace_goal_raises(self) -> None:
        planner = ExecutionPlanner()
        with pytest.raises(ValueError):
            planner.plan("   ")

    def test_planner_returns_plan_with_goal(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Research AI")
        assert plan.goal == "Research AI"

    def test_planner_assigns_strategy(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Research AI", strategy=ExecutionStrategy.PARALLEL)
        assert plan.strategy == "parallel"

    def test_planner_website_dependencies(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Create website")
        # generate_code depends on research
        research = plan.tasks[0]
        generate_code = plan.tasks[1]
        assert research.id in generate_code.dependencies

    def test_planner_website_optional_task(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Create website")
        # generate_assets is optional
        generate_assets = plan.tasks[2]
        assert generate_assets.optional is True

    def test_planner_default_retry_policy(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Research AI")
        assert plan.tasks[0].retry_policy.max_attempts == 3

    def test_planner_custom_retry_policy(self) -> None:
        planner = ExecutionPlanner(default_retry_policy=RetryPolicy(max_attempts=5))
        plan = planner.plan("Research AI")
        assert plan.tasks[0].retry_policy.max_attempts == 5

    def test_planner_metadata_contains_template(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Create website")
        assert plan.metadata["planner"] == "deterministic"
        assert plan.metadata["template"] == "website"

    def test_planner_is_base_planner(self) -> None:
        assert issubclass(ExecutionPlanner, BasePlanner)

    def test_planner_plan_has_unique_task_ids(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Create website")
        ids = [t.id for t in plan.tasks]
        assert len(ids) == len(set(ids))


# ===========================================================================
# Dispatcher
# ===========================================================================


class _FakeRegistry:
    """Minimal registry stub for dispatcher tests."""

    def __init__(self, items: dict[str, object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items.values())

    def names(self) -> list[str]:
        return sorted(self._items)

    def get(self, name: str) -> object | None:
        return self._items.get(name)


class _FakeAgent:
    def __init__(self, name: str, capabilities: list[str]) -> None:
        self.name = name
        self.capabilities = capabilities


class _FakeProvider:
    def __init__(self, name: str, capabilities: list[str]) -> None:
        self.name = name
        self.capabilities = capabilities


class _FakeTool:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description


class TestDispatcher:
    """Tests for atlas.execution.dispatcher."""

    def test_dispatcher_resolves_all_tasks(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Create website")
        dispatcher = ExecutionDispatcher()
        result = dispatcher.dispatch(plan)
        assert len(result.resolutions) == 6

    def test_dispatcher_returns_dispatch_result(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Research AI")
        dispatcher = ExecutionDispatcher()
        result = dispatcher.dispatch(plan)
        assert isinstance(result, DispatchResult)
        assert result.plan_id == plan.id

    def test_dispatcher_resolution_has_action(self) -> None:
        planner = ExecutionPlanner()
        plan = planner.plan("Research AI")
        dispatcher = ExecutionDispatcher()
        result = dispatcher.dispatch(plan)
        resolution = next(iter(result.resolutions.values()))
        assert resolution.action == "research"

    def test_dispatcher_default_agent_for_research(self) -> None:
        dispatcher = ExecutionDispatcher()
        task = ExecutionTask(id="t", kind=TaskKind.RESEARCH, action="research")
        resolution = dispatcher.resolve(task)
        assert resolution.agent == "researcher"

    def test_dispatcher_default_provider_for_research(self) -> None:
        dispatcher = ExecutionDispatcher()
        task = ExecutionTask(id="t", kind=TaskKind.RESEARCH, action="research")
        resolution = dispatcher.resolve(task)
        assert resolution.provider == "zai"

    def test_dispatcher_default_tool_for_git(self) -> None:
        dispatcher = ExecutionDispatcher()
        task = ExecutionTask(id="t", kind=TaskKind.GIT, action="git_commit")
        resolution = dispatcher.resolve(task)
        assert resolution.tool == "git"

    def test_dispatcher_selects_agent_from_registry(self) -> None:
        agents = _FakeRegistry(
            {"researcher": _FakeAgent("researcher", ["research", "search"])}
        )
        dispatcher = ExecutionDispatcher(agents=agents)
        task = ExecutionTask(id="t", kind=TaskKind.RESEARCH, action="research")
        resolution = dispatcher.resolve(task)
        assert resolution.agent == "researcher"

    def test_dispatcher_selects_provider_from_registry(self) -> None:
        providers = _FakeRegistry(
            {"openai": _FakeProvider("openai", ["generate", "code"])}
        )
        dispatcher = ExecutionDispatcher(providers=providers)
        task = ExecutionTask(id="t", kind=TaskKind.GENERATE, action="generate_code")
        resolution = dispatcher.resolve(task)
        assert resolution.provider == "openai"

    def test_dispatcher_selects_tool_from_registry(self) -> None:
        tools = _FakeRegistry({"git": _FakeTool("git", "git vcs commit")})
        dispatcher = ExecutionDispatcher(tools=tools)
        task = ExecutionTask(id="t", kind=TaskKind.GIT, action="git_commit")
        resolution = dispatcher.resolve(task)
        assert resolution.tool == "git"

    def test_dispatcher_no_workflow_fallback(self) -> None:
        dispatcher = ExecutionDispatcher()
        task = ExecutionTask(id="t", kind=TaskKind.CUSTOM, action="custom")
        resolution = dispatcher.resolve(task)
        assert resolution.workflow is None

    def test_dispatcher_resolution_has_reason(self) -> None:
        dispatcher = ExecutionDispatcher()
        task = ExecutionTask(id="t", kind=TaskKind.RESEARCH, action="research")
        resolution = dispatcher.resolve(task)
        assert "task=t" in resolution.reason
        assert "kind=research" in resolution.reason

    def test_dispatcher_resolution_carries_params(self) -> None:
        dispatcher = ExecutionDispatcher()
        task = ExecutionTask(
            id="t",
            kind=TaskKind.CUSTOM,
            action="custom",
            params={"key": "value"},
        )
        resolution = dispatcher.resolve(task)
        assert resolution.params == {"key": "value"}

    def test_dispatcher_is_base_dispatcher(self) -> None:
        assert issubclass(ExecutionDispatcher, BaseDispatcher)

    def test_dispatcher_custom_capability_tags(self) -> None:
        dispatcher = ExecutionDispatcher(
            capability_tags={TaskKind.RESEARCH: ("custom_tag",)}
        )
        agents = _FakeRegistry(
            {"custom_agent": _FakeAgent("custom_agent", ["custom_tag"])}
        )
        dispatcher.agents = agents
        task = ExecutionTask(id="t", kind=TaskKind.RESEARCH, action="research")
        resolution = dispatcher.resolve(task)
        assert resolution.agent == "custom_agent"


# ===========================================================================
# Executor
# ===========================================================================


class TestExecutor:
    """Tests for atlas.execution.executor."""

    def test_executor_noop_action_succeeds(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(id="t", name="T", action="noop")
        resolution = TaskResolution(task_id="t", action="noop")
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert result.output == "noop"

    def test_executor_echo_action_returns_params(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(id="t", name="T", action="echo", params={"x": 1})
        resolution = TaskResolution(task_id="t", action="echo", params={"x": 1})
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert result.output == {"x": 1}

    def test_executor_fail_action_fails(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(
            id="t",
            name="T",
            action="fail",
            params={"message": "boom"},
            retry_policy=RetryPolicy(max_attempts=1),
        )
        resolution = TaskResolution(
            task_id="t", action="fail", params={"message": "boom"}
        )
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert not result.success
        assert "boom" in (result.error or "")

    def test_executor_unknown_action_fails(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(
            id="t",
            name="T",
            action="bogus",
            retry_policy=RetryPolicy(max_attempts=1),
        )
        resolution = TaskResolution(task_id="t", action="bogus")
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert not result.success
        assert "Unknown action" in (result.error or "")

    def test_executor_retries_on_failure(self) -> None:
        attempts: list[int] = []

        def flaky(params, context):  # type: ignore[no-untyped-def]
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient")
            return "ok"

        executor = ExecutionExecutor(actions={"flaky": flaky})
        task = ExecutionTask(
            id="t",
            name="T",
            action="flaky",
            retry_policy=RetryPolicy(max_attempts=5),
        )
        resolution = TaskResolution(task_id="t", action="flaky")
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert result.attempts == 3

    def test_executor_respects_max_attempts(self) -> None:
        def always_fail(params, context):  # type: ignore[no-untyped-def]
            raise RuntimeError("permanent")

        executor = ExecutionExecutor(actions={"always_fail": always_fail})
        task = ExecutionTask(
            id="t",
            name="T",
            action="always_fail",
            retry_policy=RetryPolicy(max_attempts=2),
        )
        resolution = TaskResolution(task_id="t", action="always_fail")
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert not result.success
        assert result.attempts == 2

    def test_executor_retryable_errors_filter(self) -> None:
        def fail_with_error(params, context):  # type: ignore[no-untyped-def]
            raise RuntimeError("permission denied")

        executor = ExecutionExecutor(actions={"fail_with_error": fail_with_error})
        task = ExecutionTask(
            id="t",
            name="T",
            action="fail_with_error",
            retry_policy=RetryPolicy(
                max_attempts=3,
                retryable_errors=("timeout",),
            ),
        )
        resolution = TaskResolution(task_id="t", action="fail_with_error")
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert not result.success
        # Should not retry because "permission denied" doesn't match "timeout"
        assert result.attempts == 1

    def test_executor_register_custom_action(self) -> None:
        executor = ExecutionExecutor()
        executor.register_action("double", lambda p, c: p["x"] * 2)
        task = ExecutionTask(id="t", name="T", action="double", params={"x": 21})
        resolution = TaskResolution(task_id="t", action="double", params={"x": 21})
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert result.output == 42

    def test_executor_register_action_rejects_empty_name(self) -> None:
        executor = ExecutionExecutor()
        with pytest.raises(ValueError):
            executor.register_action("", lambda p, c: None)

    def test_executor_register_action_rejects_non_callable(self) -> None:
        executor = ExecutionExecutor()
        with pytest.raises(TypeError):
            executor.register_action("x", "not callable")  # type: ignore[arg-type]

    def test_executor_has_action(self) -> None:
        executor = ExecutionExecutor()
        assert executor.has_action("noop")
        assert not executor.has_action("bogus")

    def test_executor_known_actions_lists_builtins(self) -> None:
        executor = ExecutionExecutor()
        actions = executor.known_actions()
        assert "noop" in actions
        assert "echo" in actions
        assert "fail" in actions
        assert "research" in actions
        assert "generate_code" in actions
        assert "deploy" in actions

    def test_executor_research_action(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(
            id="t", kind=TaskKind.RESEARCH, action="research", params={"topic": "AI"}
        )
        resolution = TaskResolution(
            task_id="t", action="research", params={"topic": "AI"}
        )
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert "findings" in result.output

    def test_executor_generate_code_action(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(
            id="t",
            kind=TaskKind.GENERATE,
            action="generate_code",
            params={"goal": "test"},
        )
        resolution = TaskResolution(
            task_id="t", action="generate_code", params={"goal": "test"}
        )
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert "files_created" in result.output

    def test_executor_git_commit_action(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(
            id="t", kind=TaskKind.GIT, action="git_commit", params={"message": "test"}
        )
        resolution = TaskResolution(
            task_id="t", action="git_commit", params={"message": "test"}
        )
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert result.output["commit_hash"] == "abc123def456"

    def test_executor_deploy_action(self) -> None:
        executor = ExecutionExecutor()
        task = ExecutionTask(
            id="t", kind=TaskKind.DEPLOY, action="deploy", params={"target": "staging"}
        )
        resolution = TaskResolution(
            task_id="t", action="deploy", params={"target": "staging"}
        )
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert result.output["target"] == "staging"

    def test_executor_execute_plan_runs_all_tasks(self) -> None:
        executor = ExecutionExecutor()
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(id="t1", name="T1", action="noop"),
                ExecutionTask(id="t2", name="T2", action="echo", params={"x": 1}),
            ],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        dispatch = DispatchResult(
            plan_id=plan.id,
            resolutions={
                "t1": TaskResolution(task_id="t1", action="noop"),
                "t2": TaskResolution(task_id="t2", action="echo", params={"x": 1}),
            },
        )
        ctx = executor.execute_plan(ctx, dispatch)
        assert len(ctx.results) == 2
        assert ctx.results["t1"].success
        assert ctx.results["t2"].success

    def test_executor_execute_plan_stops_on_failure(self) -> None:
        executor = ExecutionExecutor()
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(
                    id="t1",
                    name="T1",
                    action="fail",
                    params={"message": "boom"},
                    retry_policy=RetryPolicy(max_attempts=1),
                ),
                ExecutionTask(id="t2", name="T2", action="noop"),
            ],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        dispatch = DispatchResult(
            plan_id=plan.id,
            resolutions={
                "t1": TaskResolution(
                    task_id="t1", action="fail", params={"message": "boom"}
                ),
                "t2": TaskResolution(task_id="t2", action="noop"),
            },
        )
        ctx = executor.execute_plan(ctx, dispatch)
        assert ctx.results["t1"].status is ExecutionStatus.FAILED
        # t2 is non-optional and not executed after the failure.
        assert (
            "t2" not in ctx.results
            or ctx.results["t2"].status is ExecutionStatus.SKIPPED
        )

    def test_executor_execute_plan_skips_optional_on_dep_failure(self) -> None:
        executor = ExecutionExecutor()
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(
                    id="t1",
                    name="T1",
                    action="fail",
                    params={"message": "boom"},
                    retry_policy=RetryPolicy(max_attempts=1),
                ),
                ExecutionTask(
                    id="t2",
                    name="T2",
                    action="noop",
                    dependencies=["t1"],
                    optional=True,
                ),
            ],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        dispatch = DispatchResult(
            plan_id=plan.id,
            resolutions={
                "t1": TaskResolution(
                    task_id="t1", action="fail", params={"message": "boom"}
                ),
                "t2": TaskResolution(task_id="t2", action="noop"),
            },
        )
        ctx = executor.execute_plan(ctx, dispatch)
        assert ctx.results["t1"].status is ExecutionStatus.FAILED
        assert ctx.results["t2"].status is ExecutionStatus.SKIPPED

    def test_executor_execute_plan_no_plan_raises(self) -> None:
        executor = ExecutionExecutor()
        ctx = ExecutionContext(goal="g")
        dispatch = DispatchResult(plan_id="missing")
        with pytest.raises(ExecutorError):
            executor.execute_plan(ctx, dispatch)

    def test_executor_is_base_executor(self) -> None:
        assert issubclass(ExecutionExecutor, BaseExecutor)

    def test_executor_records_to_memory(self) -> None:
        recorded: list[dict] = []

        class FakeMemory:
            def remember(
                self, content, source=None, tags=None, **kwargs
            ):  # noqa: ARG002
                recorded.append({"content": content, "tags": tags})

        executor = ExecutionExecutor(memory=FakeMemory())
        task = ExecutionTask(id="t", name="T", action="noop")
        resolution = TaskResolution(task_id="t", action="noop")
        ctx = ExecutionContext(goal="g")
        executor.execute(task, resolution, ctx)
        assert len(recorded) == 1
        assert recorded[0]["content"]["task_id"] == "t"

    def test_executor_records_tool_calls(self) -> None:
        class FakeToolResult:
            def __init__(self, output):
                self.success = True
                self.output = output
                self.error = None

            def is_error(self):
                return False

        class FakeToolManager:
            def __init__(self):
                self.registry = _FakeRegistry({"git": _FakeTool("git")})

            def execute(self, name, **kwargs):
                return FakeToolResult({"committed": True})

        executor = ExecutionExecutor(tools=FakeToolManager())
        task = ExecutionTask(id="t", kind=TaskKind.GIT, action="git_commit")
        resolution = TaskResolution(task_id="t", tool="git", action="git_commit")
        ctx = ExecutionContext(goal="g")
        result = executor.execute(task, resolution, ctx)
        assert result.success
        assert executor.tool_calls == 1


# ===========================================================================
# Reviewer
# ===========================================================================


class TestReviewer:
    """Tests for atlas.execution.reviewer."""

    def test_reviewer_all_completed(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="noop")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.COMPLETED, output="ok")
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert review.overall_status is ExecutionStatus.COMPLETED
        assert review.quality_score == 1.0
        assert review.retry_recommendation == "none"

    def test_reviewer_all_failed(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="fail")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.FAILED, error="boom")
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert review.overall_status is ExecutionStatus.FAILED
        assert review.retry_recommendation == "retry_failed"

    def test_reviewer_missing_output(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="noop")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.COMPLETED, output=None)
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert "t1" in review.missing_outputs
        # Task-level quality score is 0.5 (completed but no output).
        assert review.task_reviews["t1"].quality_score == 0.5
        # Execution-level quality score has a small penalty.
        assert review.quality_score < 1.0

    def test_reviewer_skipped_optional(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="noop", optional=True)],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.SKIPPED)
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert review.overall_status is ExecutionStatus.COMPLETED

    def test_reviewer_retry_penalty(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="noop")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(
                task_id="t1",
                status=ExecutionStatus.COMPLETED,
                output="ok",
                attempts=3,
            )
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        # Task-level quality score is penalised for retries.
        assert review.task_reviews["t1"].quality_score < 1.0

    def test_reviewer_no_plan(self) -> None:
        ctx = ExecutionContext(goal="g")
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert review.overall_status is ExecutionStatus.FAILED

    def test_reviewer_empty_plan(self) -> None:
        plan = ExecutionPlan(goal="g", tasks=[])
        ctx = ExecutionContext(goal="g", plan=plan)
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert review.overall_status is ExecutionStatus.COMPLETED
        assert review.quality_score == 1.0

    def test_reviewer_task_not_executed(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[
                ExecutionTask(id="t1", name="T1", action="noop"),
                ExecutionTask(id="t2", name="T2", action="noop"),
            ],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.COMPLETED, output="ok")
        )
        # t2 not executed
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert "t2" in review.task_reviews
        assert review.task_reviews["t2"].retry_recommended is True

    def test_reviewer_is_base_reviewer(self) -> None:
        assert issubclass(ExecutionReviewer, BaseReviewer)

    def test_reviewer_returns_execution_review(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="noop")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.COMPLETED, output="ok")
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        assert isinstance(review, ExecutionReview)

    def test_reviewer_task_review_has_fields(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="noop")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(task_id="t1", status=ExecutionStatus.COMPLETED, output="ok")
        )
        reviewer = ExecutionReviewer()
        review = reviewer.review(ctx)
        task_review = review.task_reviews["t1"]
        assert isinstance(task_review, TaskReview)
        assert task_review.status is ExecutionStatus.COMPLETED
        assert task_review.quality_score == 1.0


# ===========================================================================
# Reporter
# ===========================================================================


class TestReporter:
    """Tests for atlas.execution.reporter."""

    def _make_context(self) -> ExecutionContext:
        plan = ExecutionPlan(
            goal="test goal",
            tasks=[
                ExecutionTask(id="t1", name="T1", action="noop"),
                ExecutionTask(id="t2", name="T2", action="echo"),
            ],
        )
        ctx = ExecutionContext(goal="test goal", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(
                task_id="t1",
                status=ExecutionStatus.COMPLETED,
                output="ok",
                provider="zai",
                agent="default_agent",
            )
        )
        ctx = ctx.with_result(
            ExecutionResult(
                task_id="t2",
                status=ExecutionStatus.COMPLETED,
                output={"x": 1},
                tool="echo_tool",
            )
        )
        return ctx

    def _make_review(self, ctx: ExecutionContext) -> ExecutionReview:
        return ExecutionReview(
            execution_id=ctx.id,
            overall_status=ExecutionStatus.COMPLETED,
            quality_score=1.0,
            retry_recommendation="none",
        )

    def test_reporter_produces_report(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert isinstance(report, ExecutionReport)
        assert report.status is ExecutionStatus.COMPLETED
        assert report.goal == "test goal"

    def test_reporter_collects_providers(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert "zai" in report.providers_used

    def test_reporter_collects_tools(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert "echo_tool" in report.tools_used

    def test_reporter_collects_agents(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert "default_agent" in report.agents_used

    def test_reporter_metrics(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.metrics.total_tasks == 2
        assert report.metrics.completed_tasks == 2
        assert report.metrics.failed_tasks == 0

    def test_reporter_summary(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.summary is not None
        assert report.summary.execution_id == ctx.id
        assert report.summary.goal == "test goal"
        assert report.summary.status is ExecutionStatus.COMPLETED

    def test_reporter_duration(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.duration_seconds >= 0.0

    def test_reporter_quality_score(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.quality_score == 1.0

    def test_reporter_retry_recommendation(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.retry_recommendation == "none"

    def test_reporter_strategy(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.strategy == ctx.plan.strategy

    def test_reporter_plan_id(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert report.plan_id == ctx.plan.id

    def test_reporter_is_base_reporter(self) -> None:
        assert issubclass(ExecutionReporter, BaseReporter)

    def test_reporter_to_dict(self) -> None:
        ctx = self._make_context()
        review = self._make_review(ctx)
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        d = report.to_dict()
        assert "execution_id" in d
        assert "metrics" in d
        assert "results" in d

    def test_reporter_files_created_from_metadata(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="generate_code")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(
                task_id="t1",
                status=ExecutionStatus.COMPLETED,
                output={"files": ["main.py"]},
                metadata={"files_created": ["main.py"]},
            )
        )
        review = ExecutionReview(
            execution_id=ctx.id,
            overall_status=ExecutionStatus.COMPLETED,
            quality_score=1.0,
        )
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert "main.py" in report.files_created

    def test_reporter_errors_collected(self) -> None:
        plan = ExecutionPlan(
            goal="g",
            tasks=[ExecutionTask(id="t1", name="T1", action="fail")],
        )
        ctx = ExecutionContext(goal="g", plan=plan)
        ctx = ctx.with_result(
            ExecutionResult(
                task_id="t1",
                status=ExecutionStatus.FAILED,
                error="boom",
            )
        )
        review = ExecutionReview(
            execution_id=ctx.id,
            overall_status=ExecutionStatus.FAILED,
            quality_score=0.0,
            retry_recommendation="retry_failed",
        )
        reporter = ExecutionReporter()
        report = reporter.report(ctx, review)
        assert len(report.errors) == 1
        assert "boom" in report.errors[0]


# ===========================================================================
# Engine
# ===========================================================================


class TestEngine:
    """Tests for atlas.execution.engine."""

    def test_engine_run_website_goal(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Create website for portfolio")
        assert report.status is ExecutionStatus.COMPLETED
        assert report.metrics.total_tasks == 6
        assert report.metrics.completed_tasks == 6

    def test_engine_run_research_goal(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Research quantum computing")
        assert report.status is ExecutionStatus.COMPLETED
        assert report.metrics.total_tasks == 1

    def test_engine_run_code_goal(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Generate code for sorting")
        assert report.status is ExecutionStatus.COMPLETED
        assert report.metrics.total_tasks == 3

    def test_engine_run_deploy_goal(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Deploy to production")
        assert report.status is ExecutionStatus.COMPLETED
        assert report.metrics.total_tasks == 3

    def test_engine_run_custom_goal(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Do something unusual")
        assert report.status is ExecutionStatus.COMPLETED
        assert report.metrics.total_tasks == 1

    def test_engine_records_history(self) -> None:
        engine = ExecutionEngine()
        engine.run("Research AI")
        engine.run("Create website")
        assert len(engine.history) == 2

    def test_engine_history_contains_execution(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Research AI")
        assert report.execution_id in engine.history

    def test_engine_status(self) -> None:
        engine = ExecutionEngine()
        status = engine.status()
        assert status["default_strategy"] == "automatic"
        assert status["history_entries"] == 0

    def test_engine_execute_goal_alias(self) -> None:
        engine = ExecutionEngine()
        report = engine.execute_goal("Research AI")
        assert report.status is ExecutionStatus.COMPLETED

    def test_engine_with_strategy(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Research AI", strategy=ExecutionStrategy.PARALLEL)
        assert report.strategy == "parallel"

    def test_engine_default_strategy(self) -> None:
        engine = ExecutionEngine(default_strategy=ExecutionStrategy.SEQUENTIAL)
        report = engine.run("Research AI")
        assert report.strategy == "sequential"

    def test_engine_engine_error_is_runtime_error(self) -> None:
        assert issubclass(ExecutionEngineError, RuntimeError)

    def test_engine_with_injected_memory(self) -> None:
        recorded: list[dict] = []

        class FakeMemory:
            def remember(
                self, content, source=None, tags=None, **kwargs
            ):  # noqa: ARG002
                recorded.append({"content": content})

        engine = ExecutionEngine(memory=FakeMemory())
        engine.run("Research AI")
        assert len(recorded) >= 1

    def test_engine_report_contains_metrics(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Create website")
        assert report.metrics.total_tasks == 6
        assert report.metrics.completed_tasks == 6
        assert report.metrics.failed_tasks == 0

    def test_engine_report_contains_quality_score(self) -> None:
        engine = ExecutionEngine()
        report = engine.run("Create website")
        assert report.quality_score == 1.0

    def test_engine_repr(self) -> None:
        engine = ExecutionEngine()
        text = repr(engine)
        assert "ExecutionEngine" in text


# ===========================================================================
# End-to-end execution
# ===========================================================================


class TestEndToEnd:
    """End-to-end execution tests."""

    def test_full_pipeline_website(self) -> None:
        """Full pipeline: goal → plan → dispatch → execute → review → report."""
        engine = ExecutionEngine()
        report = engine.run("Create website for my portfolio")

        # Plan was produced.
        assert report.plan_id is not None

        # Every task completed.
        assert report.metrics.completed_tasks == report.metrics.total_tasks
        assert report.metrics.failed_tasks == 0

        # Review passed.
        assert report.status is ExecutionStatus.COMPLETED
        assert report.quality_score == 1.0
        assert report.retry_recommendation == "none"

        # History recorded.
        assert len(engine.history) == 1
        entry = engine.history.get(report.execution_id)
        assert entry is not None
        assert entry.status is ExecutionStatus.COMPLETED

    def test_full_pipeline_with_failure(self) -> None:
        """Pipeline with a failing task produces a failed report."""

        def always_fail(params, context):  # type: ignore[no-untyped-def]
            raise RuntimeError("intentional")

        engine = ExecutionEngine()
        engine.executor.register_action("research", always_fail)  # type: ignore[attr-defined]
        report = engine.run("Research AI")
        assert report.status is ExecutionStatus.FAILED
        assert report.metrics.failed_tasks >= 1
        assert report.retry_recommendation == "retry_failed"

    def test_full_pipeline_with_mock_provider(self) -> None:
        """Pipeline with an injected mock provider."""

        class FakeResponse:
            def __init__(self, text: str):
                self.text = text
                self.usage = {"prompt_tokens": 10, "completion_tokens": 20}

        class FakeProviderManager:
            def __init__(self):
                self.registry = _FakeRegistry({})

            def generate(self, prompt, provider=None, **kwargs):  # noqa: ARG002
                return FakeResponse(f"generated: {prompt[:30]}")

        engine = ExecutionEngine(providers=FakeProviderManager())
        report = engine.run("Generate code for app")
        assert report.status is ExecutionStatus.COMPLETED

    def test_full_pipeline_with_mock_tool(self) -> None:
        """Pipeline with an injected mock tool."""

        class FakeToolResult:
            def __init__(self, output):
                self.success = True
                self.output = output
                self.error = None

            def is_error(self):
                return False

        class FakeToolManager:
            def __init__(self):
                self.registry = _FakeRegistry({"git": _FakeTool("git")})

            def execute(self, name, **kwargs):
                return FakeToolResult({"committed": True, "hash": "abc123"})

        engine = ExecutionEngine(tools=FakeToolManager())
        report = engine.run("Deploy to production")
        assert report.status is ExecutionStatus.COMPLETED

    def test_full_pipeline_records_history(self) -> None:
        engine = ExecutionEngine()
        engine.run("Research AI")
        engine.run("Create website")
        engine.run("Deploy to production")
        assert len(engine.history) == 3
        listed = engine.history.list()
        assert listed[0].goal.startswith("Deploy")  # newest first

    def test_full_pipeline_deterministic(self) -> None:
        """Running the same goal twice produces equivalent plans."""
        engine = ExecutionEngine()
        report1 = engine.run("Create website")
        report2 = engine.run("Create website")
        assert report1.metrics.total_tasks == report2.metrics.total_tasks
        assert report1.status == report2.status

    def test_zero_circular_imports(self) -> None:
        """Verify every execution module can be imported independently."""
        import importlib

        modules = [
            "atlas.execution.models",
            "atlas.execution.strategy",
            "atlas.execution.planner",
            "atlas.execution.dispatcher",
            "atlas.execution.executor",
            "atlas.execution.reviewer",
            "atlas.execution.reporter",
            "atlas.execution.engine",
            "atlas.execution",
        ]
        for m in modules:
            importlib.import_module(m)
