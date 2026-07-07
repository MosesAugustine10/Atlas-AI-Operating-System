"""Runtime executor — runs the planned execution plan.

The :class:`RuntimeExecutor` is the runtime's analog of the workflow
engine's step executor. It accepts a :class:`ExecutionPlan` (a list of
:class:`ExecutionStep` items) and runs them in order, emitting lifecycle
events at each boundary.

The default :class:`PlaceholderExecutor` resolves step ``action`` strings
through an injected action registry and returns a deterministic
:class:`ExecutionResult` for each step. Custom actions can be injected via
the constructor. Real executors (LLM-backed, tool-backed, workflow-backed)
subclass :class:`BaseExecutor` and are injected into the runtime.

The executor is provider-agnostic, tool-agnostic, agent-agnostic, and
workflow-agnostic: it knows nothing about the Atlas subsystems it might
dispatch to. It only knows how to run an ordered list of steps.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import (
    EventBus,
    ExecutionStarted,
    StepCompleted,
    StepFailed,
    StepStarted,
)
from atlas.runtime.telemetry import TelemetryCollector


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "step") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class ExecutionStep:
    """A single unit of work in a runtime execution plan.

    Attributes:
        id: Stable identifier for the step.
        action: The action name resolved by the executor.
        params: Static parameters passed to the action at execution time.
        optional: If ``True``, failure does not fail the execution.
    """

    id: str = field(default_factory=lambda: _new_id("step"))
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    optional: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    """The outcome of a single :class:`ExecutionStep`.

    Attributes:
        step_id: The step that produced this result.
        success: Whether the step completed without error.
        output: The value produced by the step.
        error: An error message if ``success`` is ``False``.
        started_at: When execution began.
        completed_at: When execution finished.
    """

    step_id: str
    success: bool
    output: Any = None
    error: str | None = None
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None


@dataclass(frozen=True)
class ExecutionPlan:
    """An ordered list of :class:`ExecutionStep` items.

    Attributes:
        steps: The steps to execute, in order.
        inputs: Inputs propagated to every step's context.
        metadata: Free-form metadata.
    """

    steps: list[ExecutionStep] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionOutcome:
    """The outcome of running an :class:`ExecutionPlan`.

    Attributes:
        success: Whether every required step succeeded.
        results: Mapping of step ID -> :class:`ExecutionResult`.
        final_output: The output of the last successful step.
        error: Error message if ``success`` is ``False``.
    """

    success: bool
    results: dict[str, ExecutionResult] = field(default_factory=dict)
    final_output: Any = None
    error: str | None = None


Action = Callable[[dict[str, Any], dict[str, Any]], Any]


class BaseExecutor(ABC):
    """Abstract contract for runtime step executors."""

    @abstractmethod
    def execute_plan(
        self,
        plan: ExecutionPlan,
        execution_id: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionOutcome:
        """Run ``plan`` and return the :class:`ExecutionOutcome`."""


class PlaceholderExecutor(BaseExecutor):
    """Deterministic placeholder executor.

    Parameters:
        actions: Optional mapping of action name -> callable. The callable
            receives ``(params, context)`` and may return any object.
            Raising an exception marks the step failed.
        bus: Optional event bus to publish step events to.
        telemetry: Optional telemetry collector to record step outcomes.
        name: Identifier for this executor (used in logs).
    """

    def __init__(
        self,
        actions: dict[str, Action] | None = None,
        bus: EventBus | None = None,
        telemetry: TelemetryCollector | None = None,
        name: str = "placeholder",
    ) -> None:
        self.name = name
        self.logger = get_logger(f"runtime.executor.{name}")
        self.bus = bus
        self.telemetry = telemetry
        self._actions: dict[str, Action] = {}
        for action_name, fn in (actions or {}).items():
            self.register_action(action_name, fn)
        for action_name, fn in _BUILTIN_ACTIONS.items():
            self._actions.setdefault(action_name, fn)

    def register_action(self, name: str, fn: Action) -> None:
        """Register or override an action by name."""
        if not name or not name.strip():
            raise ValueError("Action name must be non-empty.")
        self._actions[name] = fn

    def has_action(self, name: str) -> bool:
        """Return ``True`` if ``name`` is a registered action."""
        return name in self._actions

    def known_actions(self) -> list[str]:
        """Return a sorted list of registered action names."""
        return sorted(self._actions)

    def execute_plan(
        self,
        plan: ExecutionPlan,
        execution_id: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionOutcome:
        """Run ``plan`` step by step, emitting events at each boundary."""
        ctx = dict(context or {})
        ctx.update(plan.inputs)
        self._emit(ExecutionStarted(execution_id=execution_id))

        results: dict[str, ExecutionResult] = {}
        final_output: Any = None
        last_error: str | None = None

        for step in plan.steps:
            self._emit(StepStarted(execution_id=execution_id, step_id=step.id))
            started = _utcnow()
            action = self._actions.get(step.action)
            if action is None:
                result = ExecutionResult(
                    step_id=step.id,
                    success=False,
                    error=f"Unknown action: {step.action!r}",
                    started_at=started,
                    completed_at=_utcnow(),
                )
            else:
                try:
                    output = action(dict(step.params), ctx)
                    result = ExecutionResult(
                        step_id=step.id,
                        success=True,
                        output=output,
                        started_at=started,
                        completed_at=_utcnow(),
                    )
                    ctx[step.id] = output
                    final_output = output
                except Exception as exc:  # noqa: BLE001 — surface to plan
                    result = ExecutionResult(
                        step_id=step.id,
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                        started_at=started,
                        completed_at=_utcnow(),
                    )

            results[step.id] = result
            self._emit(
                StepCompleted(
                    execution_id=execution_id,
                    step_id=step.id,
                    output=result.output,
                )
                if result.success
                else StepFailed(
                    execution_id=execution_id,
                    step_id=step.id,
                    error=result.error or "",
                )
            )

            if not result.success:
                if step.optional:
                    self.logger.info("Optional step %s failed; continuing", step.id)
                    continue
                last_error = result.error
                break

        success = last_error is None
        return ExecutionOutcome(
            success=success,
            results=results,
            final_output=final_output,
            error=last_error,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event: Any) -> None:
        """Publish ``event`` on the bus (if one is attached)."""
        if self.bus is not None:
            self.bus.publish(event)

    def __repr__(self) -> str:
        return (
            f"<PlaceholderExecutor name={self.name!r} " f"actions={len(self._actions)}>"
        )


# ---------------------------------------------------------------------------
# Built-in actions
# ---------------------------------------------------------------------------


def _noop_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always succeed and return a sentinel."""
    return "noop"


def _echo_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Succeed and echo the supplied params."""
    return dict(params)


def _fail_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always raise a :class:`RuntimeError`."""
    message = params.get("message", "intentional failure")
    raise RuntimeError(message)


def _identity_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Return the params unchanged."""
    return params.get("value")


def _context_read_action(params: dict[str, Any], context: dict[str, Any]) -> Any:
    """Read a key from the execution context."""
    return context.get(params.get("key", ""))


_BUILTIN_ACTIONS: dict[str, Action] = {
    "noop": _noop_action,
    "echo": _echo_action,
    "fail": _fail_action,
    "identity": _identity_action,
    "context_read": _context_read_action,
}


__all__ = [
    "Action",
    "BaseExecutor",
    "ExecutionOutcome",
    "ExecutionPlan",
    "ExecutionResult",
    "ExecutionStep",
    "PlaceholderExecutor",
]
