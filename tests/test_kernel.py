"""Tests for the Atlas Kernel architecture.

Each test confirms that a kernel component can be instantiated and exposes
the surface expected by the rest of the pipeline. The implementation is
intentionally placeholder; these tests guard the *shape* of the architecture.
"""

from __future__ import annotations

from atlas.core.context import Context
from atlas.core.kernel import Kernel
from atlas.core.planner import Planner, Task
from atlas.core.router import AgentDescriptor, Router
from atlas.core.session import Session
from atlas.core.state import ExecutionState, State

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def test_state_is_instantiable() -> None:
    state = State()
    assert state.phase is ExecutionState.PENDING
    assert state.is_terminal is False
    assert len(state.history) == 1


def test_state_transitions_record_history() -> None:
    state = State()
    state.transition(ExecutionState.PLANNING)
    assert state.phase is ExecutionState.PLANNING
    assert len(state.history) == 2


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


def test_context_is_instantiable() -> None:
    ctx = Context(request="hello")
    assert ctx.request == "hello"
    assert isinstance(ctx.state, State)
    assert ctx.artifacts == {}


def test_context_attach_and_get() -> None:
    ctx = Context(request="hello")
    ctx.attach("plan", ["t1"])
    assert ctx.get("plan") == ["t1"]
    assert ctx.get("missing", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def test_planner_is_instantiable() -> None:
    planner = Planner()
    assert planner.max_tasks == 16


def test_planner_returns_tasks() -> None:
    planner = Planner()
    ctx = Context(request="summarise the report")
    tasks = planner.plan("summarise the report", ctx)
    assert isinstance(tasks, list)
    assert all(isinstance(t, Task) for t in tasks)
    assert len(tasks) >= 1


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def test_router_is_instantiable() -> None:
    router = Router()
    assert router.agents == {}


def test_router_select_without_agents_returns_default() -> None:
    router = Router()
    task = Task(description="do something")
    ctx = Context(request="do something")
    selected = router.select(task, ctx)
    assert selected.name == "default"


def test_router_register_then_select() -> None:
    router = Router(
        agents=[AgentDescriptor(name="researcher", capabilities=["search"])]
    )
    task = Task(description="research topic")
    ctx = Context(request="research topic")
    selected = router.select(task, ctx)
    assert selected.name == "researcher"


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def test_session_is_instantiable() -> None:
    ctx = Context(request="run analysis")
    session = Session(context=ctx)
    assert session.tasks == []
    assert session.results == []
    assert session.state.phase is ExecutionState.PENDING


def test_session_lifecycle_transitions() -> None:
    ctx = Context(request="run analysis")
    session = Session(context=ctx)
    session.begin()
    assert session.state.phase is ExecutionState.PLANNING
    session.set_tasks([Task(description="step 1")])
    assert session.state.phase is ExecutionState.ROUTING
    session.record_result({"step": 1})
    assert session.state.phase is ExecutionState.EXECUTING
    session.complete()
    assert session.state.phase is ExecutionState.COMPLETED
    assert session.state.is_terminal is True


# ---------------------------------------------------------------------------
# Kernel
# ---------------------------------------------------------------------------


def test_kernel_is_instantiable() -> None:
    kernel = Kernel(config={"system": {"name": "Atlas"}})
    assert kernel.config["system"]["name"] == "Atlas"
    assert isinstance(kernel.planner, Planner)
    assert isinstance(kernel.router, Router)


def test_kernel_handle_completes() -> None:
    kernel = Kernel()
    session = kernel.handle("summarise the mining report")
    assert session.state.phase is ExecutionState.COMPLETED
    assert len(session.tasks) >= 1
    assert len(session.results) >= 1
