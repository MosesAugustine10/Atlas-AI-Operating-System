"""Coordination engine — shared workspace, handoffs, and dependencies.

The :class:`CoordinationEngine` manages the shared workspace that
workers use to exchange artifacts, track task dependencies, and
coordinate handoffs. It is the glue that lets multiple workers
collaborate on a single deliverable without stepping on each other.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Task,
    TaskArtifact,
    TaskStatus,
    _new_id,
    _utcnow,
)


class CoordinationEngine:
    """Manages the shared workspace and task dependencies."""

    def __init__(self) -> None:
        # workspace: task_id -> tuple of artifacts
        self._workspace: dict[str, tuple[TaskArtifact, ...]] = {}
        # dependencies: task_id -> tuple of task ids it depends on
        self._dependencies: dict[str, tuple[str, ...]] = {}
        # handoffs: list of (from_task, to_task, timestamp)
        self._handoffs: list[tuple[str, str, Any]] = []
        self.logger = get_logger("workforce.coordination")

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def publish_artifact(
        self,
        task_id: str,
        kind: str = "file",
        name: str = "",
        path: str = "",
        size_bytes: int = 0,
    ) -> TaskArtifact:
        """Publish an artifact to the shared workspace for ``task_id``."""
        artifact = TaskArtifact(
            id=_new_id("artifact"),
            kind=kind,
            name=name,
            path=path,
            size_bytes=size_bytes,
        )
        current = self._workspace.get(task_id, ())
        self._workspace[task_id] = (*current, artifact)
        self.logger.info("Published artifact %s for task %s", artifact.id, task_id)
        return artifact

    def artifacts_for(self, task_id: str) -> tuple[TaskArtifact, ...]:
        """Return all artifacts published for ``task_id``."""
        return self._workspace.get(task_id, ())

    def all_artifacts(self) -> dict[str, tuple[TaskArtifact, ...]]:
        """Return the entire workspace as ``{task_id: (artifacts...)}``."""
        return dict(self._workspace)

    def artifact_count(self) -> int:
        """Return the total number of artifacts in the workspace."""
        return sum(len(arts) for arts in self._workspace.values())

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def add_dependency(
        self,
        task_id: str,
        depends_on: str,
    ) -> None:
        """Record that ``task_id`` depends on ``depends_on``."""
        current = self._dependencies.get(task_id, ())
        if depends_on not in current:
            self._dependencies[task_id] = (*current, depends_on)

    def dependencies_of(self, task_id: str) -> tuple[str, ...]:
        """Return the task ids that ``task_id`` depends on."""
        return self._dependencies.get(task_id, ())

    def dependents_of(self, task_id: str) -> list[str]:
        """Return the task ids that depend on ``task_id``."""
        return [tid for tid, deps in self._dependencies.items() if task_id in deps]

    def is_blocked(self, task_id: str, completed: set[str] | None = None) -> bool:
        """Return ``True`` if ``task_id`` is blocked by incomplete dependencies.

        Parameters:
            task_id: The task to check.
            completed: The set of completed task ids. When omitted,
                ``is_blocked`` returns ``False`` (no completion info).
        """
        if completed is None:
            return False
        deps = self._dependencies.get(task_id, ())
        return any(dep not in completed for dep in deps)

    def unblock_tasks(
        self,
        tasks: list[Task],
        completed_task_ids: set[str],
    ) -> list[Task]:
        """Return the subset of ``tasks`` that are now unblocked."""
        unblocked: list[Task] = []
        for task in tasks:
            if task.status != TaskStatus.BLOCKED.value:
                continue
            if not self.is_blocked(task.id, completed_task_ids):
                unblocked.append(task)
        return unblocked

    # ------------------------------------------------------------------
    # Handoffs
    # ------------------------------------------------------------------

    def record_handoff(
        self,
        from_task_id: str,
        to_task_id: str,
    ) -> None:
        """Record that work was handed off from one task to another."""
        self._handoffs.append((from_task_id, to_task_id, _utcnow()))

    def handoffs(self) -> list[tuple[str, str, Any]]:
        """Return all recorded handoffs."""
        return list(self._handoffs)

    def handoff_count(self) -> int:
        """Return the total number of handoffs."""
        return len(self._handoffs)

    # ------------------------------------------------------------------
    # Shared state
    # ------------------------------------------------------------------

    def shared_state(self) -> dict[str, Any]:
        """Return a snapshot of the shared workspace state."""
        return {
            "tasks_with_artifacts": len(self._workspace),
            "total_artifacts": self.artifact_count(),
            "dependencies": sum(len(deps) for deps in self._dependencies.values()),
            "handoffs": len(self._handoffs),
        }

    def clear(self) -> None:
        """Clear all shared state."""
        self._workspace.clear()
        self._dependencies.clear()
        self._handoffs.clear()


__all__ = ["CoordinationEngine"]
