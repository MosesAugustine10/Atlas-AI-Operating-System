"""Goal manager — tracks multiple concurrent goals with lifecycle control.

The :class:`GoalManager` owns every active and historical goal. It
supports multiple concurrent goals, each with its own priority, status,
and dependencies. Goals can be paused, resumed, cancelled, and have
their priority updated at any time.

The manager is in-memory and append-only: every state change produces
a new immutable :class:`~atlas.intelligence.models.Goal` snapshot via
:func:`dataclasses.replace`, and the old snapshot is retained in history.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.models import (
    TERMINAL_STATUSES,
    Goal,
    GoalPriority,
    GoalScope,
    GoalStatus,
)


class GoalManagerError(RuntimeError):
    """Raised when a goal operation cannot be performed."""


class GoalManager:
    """Owns every goal and supports multiple concurrent goals.

    Parameters:
        max_active: Maximum number of concurrently active goals.
            Defaults to 10.
    """

    def __init__(self, max_active: int = 10) -> None:
        if max_active < 1:
            raise ValueError("max_active must be >= 1")
        self.max_active = max_active
        self._goals: dict[str, Goal] = {}
        self._history: list[Goal] = []
        self.logger = get_logger("intelligence.goals")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        description: str,
        scope: GoalScope = GoalScope.SHORT_TERM,
        priority: GoalPriority = GoalPriority.NORMAL,
        parent_id: str | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        """Create a new goal and register it.

        Raises:
            GoalManagerError: If ``parent_id`` is supplied but not
                registered.
        """
        if not description or not description.strip():
            raise ValueError("description must be non-empty")
        if parent_id is not None and parent_id not in self._goals:
            raise GoalManagerError(f"parent goal not found: {parent_id!r}")
        goal = Goal(
            description=description,
            scope=scope,
            priority=priority,
            parent_id=parent_id,
            dependencies=list(dependencies or []),
            metadata=dict(metadata or {}),
        )
        self._goals[goal.id] = goal
        self._history.append(goal)
        self.logger.info("Created goal %s: %s", goal.id, description[:60])
        return goal

    def get(self, goal_id: str) -> Goal:
        """Return the current snapshot of ``goal_id``.

        Raises:
            GoalManagerError: If ``goal_id`` is not registered.
        """
        goal = self._goals.get(goal_id)
        if goal is None:
            raise GoalManagerError(f"goal not found: {goal_id!r}")
        return goal

    def get_optional(self, goal_id: str) -> Goal | None:
        """Return the goal or ``None``."""
        return self._goals.get(goal_id)

    def contains(self, goal_id: str) -> bool:
        """Return ``True`` if ``goal_id`` is registered."""
        return goal_id in self._goals

    def list(
        self,
        status: GoalStatus | None = None,
        scope: GoalScope | None = None,
    ) -> list[Goal]:
        """Return every goal, optionally filtered by status / scope."""
        goals = list(self._goals.values())
        if status is not None:
            goals = [g for g in goals if g.status is status]
        if scope is not None:
            goals = [g for g in goals if g.scope is scope]
        return sorted(goals, key=lambda g: (-g.priority, g.created_at))

    def active_goals(self) -> list[Goal]:
        """Return every goal that is currently active."""
        return self.list(status=GoalStatus.ACTIVE)

    def pending_goals(self) -> list[Goal]:
        """Return every goal that is pending."""
        return self.list(status=GoalStatus.PENDING)

    def terminal_goals(self) -> list[Goal]:
        """Return every goal in a terminal state."""
        return [g for g in self._goals.values() if g.is_terminal]

    def subgoals(self, parent_id: str) -> list[Goal]:
        """Return every direct sub-goal of ``parent_id``."""
        return [g for g in self._goals.values() if g.parent_id == parent_id]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, goal_id: str) -> Goal:
        """Mark a goal as active.

        Raises:
            GoalManagerError: If the goal is terminal or the max-active
                limit has been reached.
        """
        goal = self.get(goal_id)
        if goal.is_terminal:
            raise GoalManagerError(
                f"cannot start terminal goal {goal_id!r} (status={goal.status.value})"
            )
        if goal.status is GoalStatus.ACTIVE:
            return goal
        active_count = len(self.active_goals())
        if active_count >= self.max_active:
            raise GoalManagerError(f"max_active limit reached ({self.max_active})")
        return self._update(goal_id, status=GoalStatus.ACTIVE)

    def pause(self, goal_id: str) -> Goal:
        """Pause an active goal."""
        goal = self.get(goal_id)
        if goal.is_terminal:
            raise GoalManagerError(f"cannot pause terminal goal {goal_id!r}")
        if goal.status is not GoalStatus.ACTIVE:
            raise GoalManagerError(f"cannot pause goal in {goal.status.value} state")
        return self._update(goal_id, status=GoalStatus.PAUSED)

    def resume(self, goal_id: str) -> Goal:
        """Resume a paused goal."""
        goal = self.get(goal_id)
        if goal.is_terminal:
            raise GoalManagerError(f"cannot resume terminal goal {goal_id!r}")
        if goal.status is not GoalStatus.PAUSED:
            raise GoalManagerError(f"cannot resume goal in {goal.status.value} state")
        return self._update(goal_id, status=GoalStatus.ACTIVE)

    def cancel(self, goal_id: str, reason: str = "cancelled") -> Goal:
        """Cancel a goal."""
        goal = self.get(goal_id)
        if goal.is_terminal:
            raise GoalManagerError(f"cannot cancel terminal goal {goal_id!r}")
        return self._update(
            goal_id,
            status=GoalStatus.CANCELLED,
            metadata={"cancel_reason": reason},
        )

    def complete(self, goal_id: str, result: Any = None) -> Goal:
        """Mark a goal as completed."""
        goal = self.get(goal_id)
        if goal.is_terminal:
            raise GoalManagerError(f"cannot complete terminal goal {goal_id!r}")
        meta = dict(goal.metadata)
        if result is not None:
            meta["result"] = result
        return self._update(
            goal_id,
            status=GoalStatus.COMPLETED,
            metadata=meta,
        )

    def fail(self, goal_id: str, error: str = "") -> Goal:
        """Mark a goal as failed."""
        goal = self.get(goal_id)
        if goal.is_terminal:
            raise GoalManagerError(f"cannot fail terminal goal {goal_id!r}")
        meta = dict(goal.metadata)
        if error:
            meta["error"] = error
        return self._update(
            goal_id,
            status=GoalStatus.FAILED,
            metadata=meta,
        )

    def set_priority(self, goal_id: str, priority: GoalPriority) -> Goal:
        """Update a goal's priority."""
        return self._update(goal_id, priority=priority)

    # ------------------------------------------------------------------
    # Dependency helpers
    # ------------------------------------------------------------------

    def are_dependencies_met(self, goal_id: str) -> bool:
        """Return ``True`` if every dependency of ``goal_id`` is completed."""
        goal = self.get(goal_id)
        for dep_id in goal.dependencies:
            dep = self._goals.get(dep_id)
            if dep is None or dep.status is not GoalStatus.COMPLETED:
                return False
        return True

    def blocked_goals(self) -> list[Goal]:
        """Return every non-terminal goal whose dependencies are not met."""
        return [
            g
            for g in self._goals.values()
            if not g.is_terminal and not self.are_dependencies_met(g.id)
        ]

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self, goal_id: str) -> list[Goal]:
        """Return every recorded snapshot for ``goal_id``."""
        return [g for g in self._history if g.id == goal_id]

    def all_history(self) -> list[Goal]:
        """Return every recorded snapshot."""
        return list(self._history)

    def clear(self) -> None:
        """Drop every goal and all history."""
        self._goals.clear()
        self._history.clear()

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._goals)

    def __iter__(self) -> Iterator[Goal]:
        return iter(self.list())

    def __contains__(self, goal_id: object) -> bool:
        return isinstance(goal_id, str) and goal_id in self._goals

    def __repr__(self) -> str:
        active = len(self.active_goals())
        return (
            f"<GoalManager total={len(self._goals)} "
            f"active={active} history={len(self._history)}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update(self, goal_id: str, **changes: Any) -> Goal:
        """Apply ``changes`` to ``goal_id`` and record the new snapshot."""
        goal = self.get(goal_id)
        from datetime import UTC, datetime

        updated = dataclasses.replace(
            goal,
            updated_at=datetime.now(UTC),
            **changes,
        )
        if updated.status in TERMINAL_STATUSES and "completed_at" not in changes:
            updated = dataclasses.replace(updated, completed_at=datetime.now(UTC))
        self._goals[goal_id] = updated
        self._history.append(updated)
        self.logger.debug("Updated goal %s: %s", goal_id, changes)
        return updated


__all__ = ["GoalManager", "GoalManagerError"]
