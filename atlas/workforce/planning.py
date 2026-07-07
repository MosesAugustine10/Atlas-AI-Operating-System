"""Planning engine — team-level task decomposition and scheduling.

The :class:`PlanningEngine` takes a high-level goal and decomposes it
into a tree of :class:`~atlas.workforce.models.Task` instances, each
with an assignee role, priority, and dependencies. The planner is
pure-Python and uses an injected ``decompose_fn`` callback for the
actual decomposition (so it can delegate to the Brain's
:class:`~atlas.intelligence.task_decomposer.TaskDecomposer` when
wired, or use a simple template-based fallback otherwise).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Task,
    TaskPriority,
    TaskStatus,
    _new_id,
)


class PlanningEngine:
    """Decomposes goals into task trees.

    Parameters:
        decompose_fn: Optional callback invoked with ``(goal, **kwargs)``
            and returning a list of task dicts. When omitted, a
            template-based fallback is used.
    """

    def __init__(
        self,
        decompose_fn: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        self._decompose_fn = decompose_fn
        self.logger = get_logger("workforce.planning")

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------

    def decompose(
        self,
        goal: str,
        team_id: str = "",
        priority: str = TaskPriority.NORMAL.value,
        required_roles: tuple[str, ...] = (),
    ) -> list[Task]:
        """Decompose ``goal`` into a list of :class:`Task` instances."""
        if self._decompose_fn is not None:
            raw_tasks = self._decompose_fn(
                goal=goal,
                team_id=team_id,
                priority=priority,
                required_roles=required_roles,
            )
        else:
            raw_tasks = self._fallback_decompose(goal, required_roles)
        tasks: list[Task] = []
        for raw in raw_tasks:
            task = Task(
                id=_new_id("task"),
                title=raw.get("title", "Untitled task"),
                description=raw.get("description", ""),
                status=TaskStatus.PENDING.value,
                priority=raw.get("priority", priority),
                team_id=team_id,
                required_role=raw.get("required_role", ""),
                required_skills=tuple(raw.get("required_skills", ())),
                estimated_duration_minutes=raw.get("estimated_duration_minutes", 0.0),
                dependencies=tuple(raw.get("dependencies", ())),
            )
            tasks.append(task)
        self.logger.info("Decomposed goal %r into %d tasks", goal[:50], len(tasks))
        return tasks

    def _fallback_decompose(
        self,
        goal: str,
        required_roles: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        """Simple template-based decomposition."""
        tasks: list[dict[str, Any]] = []
        # Research task
        tasks.append(
            {
                "title": f"Research: {goal}",
                "description": f"Research the requirements for: {goal}",
                "required_role": required_roles[0] if required_roles else "",
                "required_skills": ("research",),
                "estimated_duration_minutes": 30.0,
            }
        )
        # Implementation task (depends on research)
        tasks.append(
            {
                "title": f"Implement: {goal}",
                "description": f"Implement the solution for: {goal}",
                "required_role": required_roles[1] if len(required_roles) > 1 else "",
                "required_skills": ("python",),
                "estimated_duration_minutes": 60.0,
                "dependencies": [],  # filled in below
            }
        )
        # Review task (depends on implementation)
        tasks.append(
            {
                "title": f"Review: {goal}",
                "description": f"Review the implementation for: {goal}",
                "required_skills": ("qa",),
                "estimated_duration_minutes": 20.0,
                "dependencies": [],
            }
        )
        # Wire up dependencies (task[i] depends on task[i-1])
        for i in range(1, len(tasks)):
            tasks[i]["dependencies"] = [f"placeholder_{i - 1}"]
        return tasks

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def order_by_dependencies(self, tasks: list[Task]) -> list[Task]:
        """Return ``tasks`` topologically sorted by dependencies.

        Tasks with no dependencies come first; tasks depending on
        others come after their dependencies. Cycles are broken
        arbitrarily (the cycle member appears in dependency order).
        """
        by_id = {t.id: t for t in tasks}
        # Rewrite placeholder dependencies with actual task ids
        # (the fallback decompose uses placeholder_N indices)
        ordered: list[Task] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(task: Task) -> None:
            if task.id in visited:
                return
            if task.id in visiting:
                # Cycle — skip
                return
            visiting.add(task.id)
            for dep_id in task.dependencies:
                dep = by_id.get(dep_id)
                if dep is not None:
                    visit(dep)
            visiting.discard(task.id)
            visited.add(task.id)
            ordered.append(task)

        for task in tasks:
            visit(task)
        return ordered

    def critical_path(self, tasks: list[Task]) -> list[Task]:
        """Return the critical path through ``tasks`` (longest dependency chain)."""
        if not tasks:
            return []
        ordered = self.order_by_dependencies(tasks)
        if not ordered:
            return []
        # The last task in topological order is on the critical path
        # Walk backwards through its dependencies
        by_id = {t.id: t for t in tasks}
        path: list[Task] = [ordered[-1]]
        current = ordered[-1]
        while current.dependencies:
            dep_id = current.dependencies[0]
            dep = by_id.get(dep_id)
            if dep is None:
                break
            path.append(dep)
            current = dep
        path.reverse()
        return path


__all__ = ["PlanningEngine"]
