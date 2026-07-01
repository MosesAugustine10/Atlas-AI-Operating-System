"""Execution state representation for the Atlas Kernel.

The :class:`State` object is the kernel's source of truth for *where* an
execution is in its lifecycle, *what* has happened so far, and *what* has
gone wrong. It is intentionally a passive data structure: lifecycle
transitions are driven by the Kernel and Session, not by the state itself.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class ExecutionState(enum.StrEnum):
    """Lifecycle phases of a single execution.

    The kernel moves an execution through these phases in order. Any
    phase may transition to :attr:`FAILED`; only the terminal phases
    (:attr:`COMPLETED`, :attr:`FAILED`) end the run.
    """

    PENDING = "pending"
    PLANNING = "planning"
    ROUTING = "routing"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


@dataclass
class State:
    """Represents the current execution state of one request.

    Attributes:
        id: Unique identifier for this execution state.
        phase: Current lifecycle phase.
        history: Ordered log of ``(phase, timestamp)`` transitions.
        errors: Accumulated error messages (populated on failure).
        metadata: Free-form bag for additional runtime information.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    phase: ExecutionState = ExecutionState.PENDING
    history: list[tuple[ExecutionState, datetime]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append((self.phase, _utcnow()))

    def transition(self, phase: ExecutionState) -> None:
        """Move to ``phase`` and record the transition in history."""
        self.phase = phase
        self.history.append((phase, _utcnow()))

    def record_error(self, message: str) -> None:
        """Record an error message and transition to :attr:`FAILED`."""
        self.errors.append(message)
        self.transition(ExecutionState.FAILED)

    @property
    def is_terminal(self) -> bool:
        """Whether the execution has reached a final phase."""
        return self.phase in (ExecutionState.COMPLETED, ExecutionState.FAILED)
