"""Goal-to-task planning for the Atlas Kernel.

The :class:`Planner` is the kernel's reasoning step: given a goal and the
surrounding context, it decomposes the work into discrete :class:`Task`
objects that the Router can assign to agents.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from atlas.core.context import Context


@dataclass
class Task:
    """A single executable unit produced by the Planner.

    Attributes:
        id: Unique identifier for this task.
        description: Human-readable statement of what the task does.
        inputs: Named inputs the executing agent will need.
        dependencies: Ids of tasks that must complete before this one.
        status: Current status of the task (``pending`` by default).
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    description: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"


class Planner:
    """Converts a high-level goal into a sequence of executable tasks.

    Parameters:
        max_tasks: Upper bound on the number of tasks a single plan may
            produce. Guards against runaway decomposition.
    """

    def __init__(self, max_tasks: int = 16) -> None:
        self.max_tasks = max_tasks

    def plan(self, goal: str, context: Context) -> list[Task]:
        """Decompose ``goal`` into an ordered list of tasks.

        .. note::
            Placeholder implementation. It returns a single task echoing
            the goal so the pipeline can be exercised end-to-end. Real
            decomposition logic is added in later revisions.
        """
        return [
            Task(
                description=f"Address goal: {goal}",
                inputs={"goal": goal},
            )
        ]
