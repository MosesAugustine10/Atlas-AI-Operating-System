"""Workflow lifecycle states and transitions.

This module is a *leaf* in the workflows package dependency graph: it has no
dependencies on any other workflow module. It defines the canonical
:class:`WorkflowState` enum, the legal state-transition table, and a small set
of helpers used by the engine to validate transitions before applying them.

The lifecycle is intentionally explicit — every transition is checked against
the :data:`TRANSITIONS` table so that illegal moves (e.g. ``COMPLETED ->
RUNNING``) raise :class:`InvalidStateTransitionError` rather than silently
succeeding.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from collections.abc import Set as AbstractSet


class WorkflowState(enum.StrEnum):
    """Lifecycle states a workflow run can occupy.

    The states form a directed graph rooted at :attr:`PENDING` and terminating
    in one of :attr:`COMPLETED`, :attr:`FAILED`, or :attr:`CANCELLED`.

    Attributes:
        PENDING: The run has been created but not yet started.
        PLANNING: The engine is preparing execution (resolving steps, etc.).
        WAITING: The run is blocked on an external signal or scheduled time.
        RUNNING: The run is actively executing steps.
        PAUSED: Execution has been suspended and may be resumed.
        COMPLETED: All steps finished successfully. Terminal.
        FAILED: A step failed or the run aborted. Terminal but retryable.
        CANCELLED: The run was cancelled by an operator. Terminal.
    """

    PENDING = "pending"
    PLANNING = "planning"
    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: States from which a run cannot be advanced further.
TERMINAL_STATES: frozenset[WorkflowState] = frozenset(
    {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    }
)

#: States in which the run is considered "alive" (not terminal).
ACTIVE_STATES: frozenset[WorkflowState] = frozenset(
    {
        WorkflowState.PENDING,
        WorkflowState.PLANNING,
        WorkflowState.WAITING,
        WorkflowState.RUNNING,
        WorkflowState.PAUSED,
    }
)

#: The legal forward transitions for each state.
#:
#: Note that :attr:`WorkflowState.FAILED` may transition back to
#: :attr:`WorkflowState.PENDING` so that the engine can retry the run via a
#: fresh child run.
TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.PENDING: frozenset(
        {
            WorkflowState.PLANNING,
            WorkflowState.WAITING,
            WorkflowState.PAUSED,
            WorkflowState.CANCELLED,
        }
    ),
    WorkflowState.PLANNING: frozenset(
        {
            WorkflowState.RUNNING,
            WorkflowState.WAITING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        }
    ),
    WorkflowState.WAITING: frozenset(
        {WorkflowState.RUNNING, WorkflowState.PAUSED, WorkflowState.CANCELLED}
    ),
    WorkflowState.RUNNING: frozenset(
        {
            WorkflowState.PAUSED,
            WorkflowState.WAITING,
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        }
    ),
    WorkflowState.PAUSED: frozenset(
        {WorkflowState.RUNNING, WorkflowState.CANCELLED, WorkflowState.FAILED}
    ),
    WorkflowState.COMPLETED: frozenset(),
    WorkflowState.FAILED: frozenset({WorkflowState.PENDING, WorkflowState.CANCELLED}),
    WorkflowState.CANCELLED: frozenset(),
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""

    def __init__(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Illegal workflow state transition: {from_state.value} -> {to_state.value}"
        )


def can_transition(from_state: WorkflowState, to_state: WorkflowState) -> bool:
    """Return ``True`` if transitioning between the two states is legal."""
    return to_state in TRANSITIONS.get(from_state, frozenset())


def assert_transition(from_state: WorkflowState, to_state: WorkflowState) -> None:
    """Raise :class:`InvalidStateTransitionError` if the move is illegal.

    A self-transition (``from_state == to_state``) is treated as legal so
    that idempotent state setters do not raise.
    """
    if from_state == to_state:
        return
    if not can_transition(from_state, to_state):
        raise InvalidStateTransitionError(from_state, to_state)


def is_terminal(state: WorkflowState) -> bool:
    """Return ``True`` if ``state`` is a terminal lifecycle state."""
    return state in TERMINAL_STATES


def is_active(state: WorkflowState) -> bool:
    """Return ``True`` if ``state`` is a non-terminal lifecycle state."""
    return state in ACTIVE_STATES


def legal_targets(state: WorkflowState) -> AbstractSet[WorkflowState]:
    """Return the set of states reachable in one transition from ``state``."""
    return TRANSITIONS.get(state, frozenset())


def all_states() -> Iterable[WorkflowState]:
    """Return every workflow state in declaration order."""
    return tuple(WorkflowState)


__all__ = [
    "ACTIVE_STATES",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "InvalidStateTransitionError",
    "WorkflowState",
    "all_states",
    "assert_transition",
    "can_transition",
    "is_active",
    "is_terminal",
    "legal_targets",
]
