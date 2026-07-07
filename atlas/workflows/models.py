"""Immutable data models for the Atlas Workflow Engine.

Every model in this module is a frozen dataclass: once constructed, the
instance cannot be mutated in place. Updates are performed by producing a new
copy via :func:`dataclasses.replace`. This makes workflow runs safe to share
across components, store in history, and inspect concurrently without
defensive copies.

The module is a *leaf* in the workflows package dependency graph: it depends
only on :mod:`atlas.workflows.state` (an enum) and the standard library.
"""

from __future__ import annotations

import dataclasses
import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.workflows.state import WorkflowState


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "wf") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class WorkflowStep:
    """A single unit of work inside a workflow definition.

    Attributes:
        id: Stable identifier used by other steps to express dependencies.
        name: Human-readable label for the step.
        action: The action name resolved by the executor. Provider-agnostic —
            the executor decides how to dispatch this string.
        params: Static parameters passed to the action at execution time.
        depends_on: IDs of steps that must complete successfully before this
            step may execute.
        optional: If ``True``, failure of this step does not fail the run.
    """

    id: str
    name: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    optional: bool = False


@dataclass(frozen=True)
class WorkflowDefinition:
    """An immutable, named, versioned workflow definition.

    A definition is a template: it describes *what* to run, not *when* or
    *how*. Runs are created from definitions via the engine.

    Attributes:
        id: Unique identifier for the definition.
        name: Human-readable name.
        version: Semantic version of the definition.
        description: Free-form documentation.
        steps: Ordered list of :class:`WorkflowStep` objects.
        inputs: Schema or default values for run inputs.
        outputs: Names of expected output keys produced by the run.
        metadata: Free-form bag for tooling (tags, owner, etc.).
        created_at: When the definition was created.
    """

    id: str = field(default_factory=lambda: _new_id("def"))
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class StateTransition:
    """A single recorded state change for a workflow run.

    Attributes:
        from_state: The state the run was in before the transition.
        to_state: The state the run moved to.
        timestamp: When the transition occurred.
        reason: Optional human-readable reason for the transition.
    """

    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime = field(default_factory=_utcnow)
    reason: str | None = None


@dataclass(frozen=True)
class StepResult:
    """The outcome of executing a single :class:`WorkflowStep`.

    Attributes:
        step_id: The step that produced this result.
        success: Whether the step completed without error.
        output: The value produced by the step (any picklable object).
        error: An error message if ``success`` is ``False``.
        started_at: When execution began.
        completed_at: When execution finished. ``None`` if interrupted.
    """

    step_id: str
    success: bool
    output: Any = None
    error: str | None = None
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None


@dataclass(frozen=True)
class WorkflowRun:
    """An immutable snapshot of a single workflow execution.

    Because the dataclass is frozen, every state change produces a new
    instance via :func:`dataclasses.replace`. The :attr:`transitions` list
    accumulates the full history of state changes; the :attr:`step_results`
    mapping accumulates the outcome of each executed step.

    Attributes:
        id: Unique identifier for this run.
        definition_id: The :attr:`WorkflowDefinition.id` this run executes.
        name: Convenience copy of the definition name.
        state: Current lifecycle state.
        inputs: Inputs supplied when the run was created.
        step_results: Mapping of step ID -> :class:`StepResult`.
        current_step_id: The step currently or most recently executing.
        started_at: When the run first entered the ``RUNNING`` state.
        completed_at: When the run reached a terminal state.
        paused_at: When the run was last paused.
        attempts: Number of execution attempts (1 for the first run).
        parent_run_id: If this is a retry, the ID of the original run.
        transitions: Ordered list of recorded state transitions.
        error: Optional error message associated with failure.
        metadata: Free-form runtime metadata.
    """

    id: str = field(default_factory=lambda: _new_id("run"))
    definition_id: str = ""
    name: str = ""
    state: WorkflowState = WorkflowState.PENDING
    inputs: dict[str, Any] = field(default_factory=dict)
    step_results: dict[str, StepResult] = field(default_factory=dict)
    current_step_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    attempts: int = 1
    parent_run_id: str | None = None
    transitions: list[StateTransition] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_transition(
        self,
        to_state: WorkflowState,
        reason: str | None = None,
        timestamp: datetime | None = None,
    ) -> WorkflowRun:
        """Return a new run with a recorded state transition applied.

        Does *not* validate the transition — the caller is expected to use
        :func:`atlas.workflows.state.assert_transition` first.
        """
        transition = StateTransition(
            from_state=self.state,
            to_state=to_state,
            timestamp=timestamp or _utcnow(),
            reason=reason,
        )
        new_transitions = [*self.transitions, transition]
        updates: dict[str, Any] = {
            "state": to_state,
            "transitions": new_transitions,
        }
        if to_state == WorkflowState.RUNNING and self.started_at is None:
            updates["started_at"] = transition.timestamp
        if to_state == WorkflowState.PAUSED:
            updates["paused_at"] = transition.timestamp
        if to_state in (
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ):
            updates["completed_at"] = transition.timestamp
        return dataclasses.replace(self, **updates)

    def with_step_result(self, result: StepResult) -> WorkflowRun:
        """Return a new run with ``result`` merged into :attr:`step_results`."""
        new_results = {**self.step_results, result.step_id: result}
        return dataclasses.replace(
            self,
            step_results=new_results,
            current_step_id=result.step_id,
        )

    def is_terminal(self) -> bool:
        """Return ``True`` if the run is in a terminal state."""
        return self.state in (
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        )


@dataclass(frozen=True)
class WorkflowResult:
    """A summary view of a completed workflow run.

    Attributes:
        run_id: The run this result summarizes.
        state: The final state of the run.
        outputs: Outputs produced by the run (merged step outputs).
        error: Error message if the run failed.
        started_at: When the run started.
        completed_at: When the run reached its final state.
    """

    run_id: str
    state: WorkflowState
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ScheduleKind(enum.StrEnum):
    """Trigger kinds supported by the workflow scheduler.

    Attributes:
        ONE_TIME: Fire once at a fixed timestamp.
        INTERVAL: Fire on a fixed cadence (every ``interval_seconds``).
        CRON: Fire according to a (simplified) cron expression.
    """

    ONE_TIME = "one_time"
    INTERVAL = "interval"
    CRON = "cron"


@dataclass(frozen=True)
class WorkflowSchedule:
    """A schedule that triggers a workflow definition on a cadence.

    Attributes:
        id: Unique schedule identifier.
        workflow_id: The :attr:`WorkflowDefinition.id` to trigger.
        kind: The :class:`ScheduleKind` governing when the schedule fires.
        inputs: Inputs passed to each run created by this schedule.
        interval_seconds: Cadence in seconds when ``kind`` is INTERVAL.
        run_at: Trigger timestamp when ``kind`` is ONE_TIME.
        cron_expr: Cron expression when ``kind`` is CRON.
        next_run_at: When the schedule should next fire. ``None`` disables it.
        last_run_at: When the schedule last fired.
        enabled: Master toggle for the schedule.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("sched"))
    workflow_id: str = ""
    kind: ScheduleKind = ScheduleKind.ONE_TIME
    inputs: dict[str, Any] = field(default_factory=dict)
    interval_seconds: int | None = None
    run_at: datetime | None = None
    cron_expr: str | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ScheduleKind",
    "StateTransition",
    "StepResult",
    "WorkflowDefinition",
    "WorkflowResult",
    "WorkflowRun",
    "WorkflowSchedule",
    "WorkflowStep",
]
