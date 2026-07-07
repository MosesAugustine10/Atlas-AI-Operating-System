"""Runtime lifecycle states and transitions.

This module is a *leaf* in the runtime package dependency graph: it has no
dependencies on any other runtime module. It defines the canonical
:class:`RuntimeState` enum, the legal state-transition table, and helpers
used by the :class:`LifecycleManager` to validate transitions before
applying them.

A runtime execution moves through three broad phases:

* **Intake** — :attr:`PENDING` → :attr:`PLANNING` → :attr:`DISPATCHING`
* **Execution** — :attr:`EXECUTING` → :attr:`REVIEWING`
* **Termination** — :attr:`COMPLETED`, :attr:`FAILED`, :attr:`CANCELLED`,
  :attr:`PAUSED`, :attr:`WAITING`

Every transition is checked against the :data:`TRANSITIONS` table so that
illegal moves (e.g. ``COMPLETED -> EXECUTING``) raise
:class:`InvalidRuntimeTransitionError` rather than silently succeeding.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from collections.abc import Set as AbstractSet


class RuntimeState(enum.StrEnum):
    """Lifecycle states a runtime execution can occupy.

    Attributes:
        PENDING: Execution created but not yet started.
        PLANNING: Planner is decomposing the goal into tasks/steps.
        DISPATCHING: Dispatcher is selecting agent / workflow / provider.
        EXECUTING: Executor is actively running steps.
        REVIEWING: Post-execution review / reflection is running.
        WAITING: Execution is blocked on an external signal or schedule.
        PAUSED: Execution suspended; may be resumed.
        COMPLETED: Execution finished successfully. Terminal.
        FAILED: Execution aborted with an error. Terminal but retryable.
        CANCELLED: Operator cancelled the execution. Terminal.
    """

    PENDING = "pending"
    PLANNING = "planning"
    DISPATCHING = "dispatching"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: States from which an execution cannot be advanced further.
TERMINAL_STATES: frozenset[RuntimeState] = frozenset(
    {
        RuntimeState.COMPLETED,
        RuntimeState.FAILED,
        RuntimeState.CANCELLED,
    }
)

#: States in which the execution is considered "alive" (not terminal).
ACTIVE_STATES: frozenset[RuntimeState] = frozenset(
    {
        RuntimeState.PENDING,
        RuntimeState.PLANNING,
        RuntimeState.DISPATCHING,
        RuntimeState.EXECUTING,
        RuntimeState.REVIEWING,
        RuntimeState.WAITING,
        RuntimeState.PAUSED,
    }
)

#: The legal forward transitions for each state.
#:
#: Note that :attr:`RuntimeState.FAILED` may transition back to
#: :attr:`RuntimeState.PENDING` so that the recovery manager can retry the
#: execution from a clean slate.
TRANSITIONS: dict[RuntimeState, frozenset[RuntimeState]] = {
    RuntimeState.PENDING: frozenset(
        {
            RuntimeState.PLANNING,
            RuntimeState.WAITING,
            RuntimeState.PAUSED,
            RuntimeState.CANCELLED,
        }
    ),
    RuntimeState.PLANNING: frozenset(
        {
            RuntimeState.DISPATCHING,
            RuntimeState.WAITING,
            RuntimeState.FAILED,
            RuntimeState.CANCELLED,
        }
    ),
    RuntimeState.DISPATCHING: frozenset(
        {
            RuntimeState.EXECUTING,
            RuntimeState.WAITING,
            RuntimeState.FAILED,
            RuntimeState.CANCELLED,
        }
    ),
    RuntimeState.EXECUTING: frozenset(
        {
            RuntimeState.PAUSED,
            RuntimeState.WAITING,
            RuntimeState.REVIEWING,
            RuntimeState.COMPLETED,
            RuntimeState.FAILED,
            RuntimeState.CANCELLED,
        }
    ),
    RuntimeState.REVIEWING: frozenset(
        {
            RuntimeState.COMPLETED,
            RuntimeState.FAILED,
            RuntimeState.CANCELLED,
            RuntimeState.EXECUTING,
        }
    ),
    RuntimeState.WAITING: frozenset(
        {
            RuntimeState.PLANNING,
            RuntimeState.DISPATCHING,
            RuntimeState.EXECUTING,
            RuntimeState.PAUSED,
            RuntimeState.CANCELLED,
        }
    ),
    RuntimeState.PAUSED: frozenset(
        {
            RuntimeState.PLANNING,
            RuntimeState.EXECUTING,
            RuntimeState.CANCELLED,
            RuntimeState.FAILED,
        }
    ),
    RuntimeState.COMPLETED: frozenset(),
    RuntimeState.FAILED: frozenset({RuntimeState.PENDING, RuntimeState.CANCELLED}),
    RuntimeState.CANCELLED: frozenset(),
}


class InvalidRuntimeTransitionError(ValueError):
    """Raised when an illegal runtime state transition is attempted."""

    def __init__(
        self,
        from_state: RuntimeState,
        to_state: RuntimeState,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Illegal runtime state transition: "
            f"{from_state.value} -> {to_state.value}"
        )


def can_transition(from_state: RuntimeState, to_state: RuntimeState) -> bool:
    """Return ``True`` if transitioning between the two states is legal."""
    if from_state == to_state:
        return True
    return to_state in TRANSITIONS.get(from_state, frozenset())


def assert_transition(from_state: RuntimeState, to_state: RuntimeState) -> None:
    """Raise :class:`InvalidRuntimeTransitionError` if the move is illegal."""
    if from_state == to_state:
        return
    if not can_transition(from_state, to_state):
        raise InvalidRuntimeTransitionError(from_state, to_state)


def is_terminal(state: RuntimeState) -> bool:
    """Return ``True`` if ``state`` is a terminal lifecycle state."""
    return state in TERMINAL_STATES


def is_active(state: RuntimeState) -> bool:
    """Return ``True`` if ``state`` is a non-terminal lifecycle state."""
    return state in ACTIVE_STATES


def legal_targets(state: RuntimeState) -> AbstractSet[RuntimeState]:
    """Return the set of states reachable in one transition from ``state``."""
    return TRANSITIONS.get(state, frozenset())


def all_states() -> Iterable[RuntimeState]:
    """Return every runtime state in declaration order."""
    return tuple(RuntimeState)


__all__ = [
    "ACTIVE_STATES",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "InvalidRuntimeTransitionError",
    "RuntimeState",
    "all_states",
    "assert_transition",
    "can_transition",
    "is_active",
    "is_terminal",
    "legal_targets",
]
