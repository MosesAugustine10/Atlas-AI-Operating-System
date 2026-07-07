"""Execution session — tracks one run from start to finish.

A :class:`Session` bundles the :class:`~atlas.core.context.Context`, the
planned :class:`~atlas.core.planner.Task` list, and the accumulating results,
and owns the lifecycle transitions of the
:class:`~atlas.core.state.State`. The Kernel creates one Session per request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from atlas.core.context import Context
from atlas.core.planner import Task
from atlas.core.state import ExecutionState, State


@dataclass
class Session:
    """Tracks a single execution from start to finish.

    Attributes:
        context: The request context carried through the pipeline.
        tasks: The planned task list for this execution.
        results: Outputs collected as each task is executed.
    """

    context: Context
    tasks: list[Task] = field(default_factory=list)
    results: list[Any] = field(default_factory=list)

    @property
    def state(self) -> State:
        """The live execution state for this session."""
        return self.context.state

    def begin(self) -> None:
        """Mark the session as having entered the planning phase."""
        self.state.transition(ExecutionState.PLANNING)

    def set_tasks(self, tasks: list[Task]) -> None:
        """Store the planned tasks and advance to routing."""
        self.tasks = list(tasks)
        self.state.transition(ExecutionState.ROUTING)

    def record_result(self, result: Any) -> None:
        """Append a task result and advance to executing."""
        self.state.transition(ExecutionState.EXECUTING)
        self.results.append(result)

    def complete(self) -> None:
        """Mark the session as successfully completed."""
        self.state.transition(ExecutionState.COMPLETED)

    def fail(self, message: str) -> None:
        """Record a failure and mark the session as failed."""
        self.state.record_error(message)
