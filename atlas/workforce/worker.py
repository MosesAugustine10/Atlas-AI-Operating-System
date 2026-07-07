"""Worker — an autonomous AI employee.

A :class:`Worker` wraps a :class:`~atlas.workforce.models.WorkerState`
and exposes lifecycle methods (start, stop, pause, resume), task
execution (via a dependency-injected ``think_fn`` callback), personal
memory, and skill lookups.

Workers NEVER import Brain, Execution, Providers, or any other Atlas
subsystem directly. They receive a ``think_fn`` callable (typically
bound to ``Brain.think``) and call it to do actual work. This keeps
the workforce package decoupled from every concrete subsystem.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Task,
    WorkerKind,
    WorkerSkill,
    WorkerState,
    WorkerStatus,
    _new_id,
    _utcnow,
)
from atlas.workforce.roles import (
    can_approve,
    can_delegate,
    can_lead_team,
    can_review,
    chain_of_command_rank,
    default_skills,
    display_name,
    is_agent,
    is_executive,
    is_specialist,
)


class WorkerError(RuntimeError):
    """Raised when a worker operation fails."""


class Worker:
    """An autonomous AI employee.

    Parameters:
        name: Human-readable display name.
        role: :class:`WorkerRole` identifier.
        kind: :class:`WorkerKind` (permanent or temporary).
        think_fn: Optional callback invoked by :meth:`execute_task` with
            ``(goal_description, **kwargs)`` and returning any result.
            When omitted, the worker returns a placeholder dict.
        skills: Optional tuple of :class:`WorkerSkill` instances. When
            omitted, the role's default skills are used.
        worker_id: Optional explicit id (auto-generated when omitted).
    """

    def __init__(
        self,
        name: str,
        role: str,
        kind: str = WorkerKind.PERMANENT.value,
        think_fn: Callable[..., Any] | None = None,
        skills: tuple[WorkerSkill, ...] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._state = WorkerState(
            id=worker_id or _new_id("worker"),
            name=name,
            role=role,
            kind=kind,
            skills=skills if skills is not None else default_skills(role),
        )
        self._think_fn = think_fn
        self.logger = get_logger(f"workforce.worker.{role}")

    # ------------------------------------------------------------------
    # State access
    # ------------------------------------------------------------------

    @property
    def state(self) -> WorkerState:
        """Return the current immutable :class:`WorkerState`."""
        return self._state

    @property
    def id(self) -> str:
        """Return the worker's unique id."""
        return self._state.id

    @property
    def name(self) -> str:
        """Return the worker's display name."""
        return self._state.name

    @property
    def role(self) -> str:
        """Return the worker's role identifier."""
        return self._state.role

    @property
    def status(self) -> str:
        """Return the worker's current :class:`WorkerStatus`."""
        return self._state.status

    @property
    def is_idle(self) -> bool:
        """Return ``True`` if the worker is idle and can accept tasks."""
        return self._state.status == WorkerStatus.IDLE.value

    @property
    def is_busy(self) -> bool:
        """Return ``True`` if the worker is currently executing a task."""
        return self._state.status == WorkerStatus.BUSY.value

    @property
    def is_online(self) -> bool:
        """Return ``True`` if the worker is online (idle or busy)."""
        return self._state.status in (WorkerStatus.IDLE.value, WorkerStatus.BUSY.value)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> WorkerState:
        """Start the worker — transitions from OFFLINE to IDLE."""
        if self._state.status not in (
            WorkerStatus.OFFLINE.value,
            WorkerStatus.STOPPED.value,
            WorkerStatus.ERROR.value,
        ):
            return self._state  # already started
        return self._update(status=WorkerStatus.IDLE.value, last_active_at=_utcnow())

    def stop(self) -> WorkerState:
        """Stop the worker — transitions to STOPPED."""
        return self._update(status=WorkerStatus.STOPPED.value)

    def pause(self) -> WorkerState:
        """Pause the worker — transitions to PAUSED."""
        if self._state.status != WorkerStatus.IDLE.value:
            return self._state
        return self._update(status=WorkerStatus.PAUSED.value)

    def resume(self) -> WorkerState:
        """Resume a paused worker — transitions back to IDLE."""
        if self._state.status != WorkerStatus.PAUSED.value:
            return self._state
        return self._update(status=WorkerStatus.IDLE.value)

    def mark_error(self) -> WorkerState:
        """Mark the worker as being in an error state."""
        return self._update(status=WorkerStatus.ERROR.value)

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def skills(self) -> tuple[WorkerSkill, ...]:
        """Return the worker's skills."""
        return self._state.skills

    def skill_level(self, skill_name: str) -> float:
        """Return the worker's level for ``skill_name`` (0.0 if absent)."""
        for skill in self._state.skills:
            if skill.name == skill_name:
                return skill.level
        return 0.0

    def has_skill(self, skill_name: str, min_level: float = 0.0) -> bool:
        """Return ``True`` if the worker has ``skill_name`` at ≥ ``min_level``.

        When ``min_level`` is 0.0 (the default), the worker must still
        possess the skill (level > 0.0) — a missing skill returns
        ``False`` even though its level defaults to 0.0.
        """
        level = self.skill_level(skill_name)
        if level <= 0.0:
            return False
        return level >= min_level

    def meets_requirements(
        self,
        required_role: str = "",
        required_skills: tuple[str, ...] = (),
    ) -> bool:
        """Return ``True`` if the worker meets the task requirements."""
        if required_role and self._state.role != required_role:
            return False
        for skill_name in required_skills:
            if not self.has_skill(skill_name, min_level=0.3):
                return False
        return True

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def remember(self, key: str, value: str) -> WorkerState:
        """Store ``value`` under ``key`` in the worker's personal memory."""
        return self._update(memory=self._state.memory.with_entry(key, value))

    def recall(self, key: str) -> str | None:
        """Return the value for ``key`` from the worker's personal memory."""
        return self._state.memory.get(key)

    def forget(self, key: str) -> WorkerState:
        """Remove ``key`` from the worker's personal memory."""
        return self._update(memory=self._state.memory.forget(key))

    def memory_size(self) -> int:
        """Return the number of entries in the worker's memory."""
        return len(self._state.memory)

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def assign_task(self, task: Task) -> WorkerState:
        """Assign ``task`` to this worker. Transitions to BUSY."""
        if not self.is_idle and not self.is_online:
            raise WorkerError(
                f"worker {self.id} is {self._state.status}, cannot accept task"
            )
        return self._update(
            status=WorkerStatus.BUSY.value,
            current_task_id=task.id,
            last_active_at=_utcnow(),
        )

    def execute_task(self, task: Task) -> Any:
        """Execute ``task`` by calling the injected ``think_fn``.

        Returns whatever ``think_fn`` returns. If no ``think_fn`` is
        configured, returns a placeholder dict describing the task.
        """
        self.logger.info("Executing task %s: %s", task.id, task.title)
        if self._think_fn is None:
            return {
                "status": "offline",
                "worker": self.id,
                "task": task.id,
                "note": "no think_fn configured",
            }
        goal = task.description or task.title
        try:
            result = self._think_fn(goal_description=goal, task=task, worker=self)
        except Exception as exc:  # noqa: BLE001 — surface any error
            self.logger.warning("Task %s failed: %s", task.id, exc)
            self._update(
                tasks_failed=self._state.tasks_failed + 1,
                status=WorkerStatus.IDLE.value,
                current_task_id="",
            )
            raise
        return result

    def complete_task(self, task: Task, quality_score: float = 0.8) -> WorkerState:
        """Mark the current task as completed. Transitions back to IDLE."""
        if self._state.current_task_id != task.id:
            raise WorkerError(f"worker {self.id} is not working on task {task.id}")
        return self._update(
            status=WorkerStatus.IDLE.value,
            current_task_id="",
            tasks_completed=self._state.tasks_completed + 1,
            last_active_at=_utcnow(),
        )

    def fail_task(self, task: Task) -> WorkerState:
        """Mark the current task as failed. Transitions back to IDLE."""
        return self._update(
            status=WorkerStatus.IDLE.value,
            current_task_id="",
            tasks_failed=self._state.tasks_failed + 1,
            last_active_at=_utcnow(),
        )

    def current_task_id(self) -> str:
        """Return the id of the task currently being executed (or "")."""
        return self._state.current_task_id

    # ------------------------------------------------------------------
    # Role checks (delegate to roles.py)
    # ------------------------------------------------------------------

    def can_review(self) -> bool:
        """Return ``True`` if this worker can review work."""
        return can_review(self._state.role)

    def can_approve(self) -> bool:
        """Return ``True`` if this worker can grant approvals."""
        return can_approve(self._state.role)

    def can_delegate(self) -> bool:
        """Return ``True`` if this worker can delegate tasks."""
        return can_delegate(self._state.role)

    def can_lead_team(self) -> bool:
        """Return ``True`` if this worker can lead a team."""
        return can_lead_team(self._state.role)

    def is_executive(self) -> bool:
        """Return ``True`` if this worker is an executive."""
        return is_executive(self._state.role)

    def is_agent(self) -> bool:
        """Return ``True`` if this worker is an automated agent."""
        return is_agent(self._state.role)

    def is_specialist(self) -> bool:
        """Return ``True`` if this worker is a specialist."""
        return is_specialist(self._state.role)

    def chain_of_command_rank(self) -> int:
        """Return this worker's rank in the chain of command."""
        return chain_of_command_rank(self._state.role)

    def display_name(self) -> str:
        """Return the human-readable role display name."""
        return display_name(self._state.role)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _update(self, **changes: Any) -> WorkerState:
        """Return a new :class:`WorkerState` with ``changes`` applied."""
        self._state = dataclasses.replace(self._state, **changes)
        return self._state

    def __repr__(self) -> str:
        return (
            f"<Worker id={self.id[:12]} name={self.name!r} "
            f"role={self.role} status={self._state.status}>"
        )


__all__ = ["Worker", "WorkerError"]
