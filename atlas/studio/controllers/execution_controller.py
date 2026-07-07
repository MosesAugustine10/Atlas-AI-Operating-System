"""Execution controller — wraps the Brain/GoalManager for the Studio UI.

The :class:`ExecutionController` adapts an Atlas execution engine (the
"brain") into a :class:`~atlas.studio.models.ExecutionTimeline` and a
history of past timelines, for the Executions page. All access is
defensive: a ``None`` brain yields an idle timeline and an empty
history.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.studio.models.studio_models import (
    ExecutionStep,
    ExecutionTimeline,
)


class ExecutionController:
    """ViewModel for the Executions page.

    Parameters:
        brain: Optional execution engine / goal manager. Expected
            duck-typed surface (any subset):

            * ``current_goal()`` -> goal-like object with ``id``,
              ``description``, ``status``, ``steps`` and timestamps.
            * ``history()`` / ``history(limit)`` -> list of goal-likes.
            * ``start(goal)`` -> started goal-like.
            * ``cancel(goal_id)`` -> bool.
        history_size: Maximum number of past timelines to retain.
    """

    def __init__(self, brain: Any = None, history_size: int = 50) -> None:
        self._brain = brain
        self._history_size = history_size
        self._history: list[ExecutionTimeline] = []
        self._current: ExecutionTimeline | None = None
        self.refresh()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def timeline(self) -> ExecutionTimeline:
        """Return the timeline for the currently running goal.

        If no goal is running, returns an idle placeholder timeline.
        """
        if self._current is not None:
            return self._current
        return ExecutionTimeline(goal_id="", description="", status="idle")

    def current_goal(self) -> ExecutionTimeline | None:
        """Return the current timeline, or ``None`` if nothing is running."""
        return self._current

    def history(self, limit: int = 20) -> list[ExecutionTimeline]:
        """Return up to ``limit`` most recent past timelines (newest first)."""
        if limit <= 0:
            return []
        return list(self._history[:limit])

    def refresh(self) -> ExecutionTimeline:
        """Re-read the current goal from the brain and refresh the cache."""
        self._current = self._read_current()
        return self.timeline()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start(self, goal: str) -> ExecutionTimeline:
        """Start ``goal`` on the wrapped brain and track it.

        Returns the timeline for the started goal. If no brain is wired
        in, a synthetic running timeline is returned for UI feedback.
        """
        if self._brain is None:
            timeline = ExecutionTimeline(
                goal_id="",
                description=goal,
                status="running",
                started_at=datetime.now(UTC),
            )
            self._current = timeline
            return timeline
        started = self._call_start(goal)
        timeline = self._to_timeline(started, status="running")
        self._current = timeline
        return timeline

    def cancel(self, goal_id: str) -> bool:
        """Cancel ``goal_id`` on the wrapped brain.

        Moves the current timeline into history with a ``cancelled``
        status and returns whether the brain accepted the cancellation.
        """
        accepted = self._call_cancel(goal_id)
        if self._current is not None and (
            self._current.goal_id == goal_id or not goal_id
        ):
            self._archive(self._current, status="cancelled")
            self._current = None
        return accepted

    def __len__(self) -> int:
        return len(self._history)

    def __repr__(self) -> str:
        running = self._current is not None
        return (
            f"<ExecutionController running={running} " f"history={len(self._history)}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_current(self) -> ExecutionTimeline | None:
        """Pull the current goal from the brain, if any."""
        if self._brain is None:
            return None
        getter = getattr(self._brain, "current_goal", None)
        if not callable(getter):
            return None
        try:
            goal = getter()
        except Exception:  # noqa: BLE001
            return None
        if goal is None:
            return None
        return self._to_timeline(goal)

    def _call_start(self, goal: str) -> Any:
        """Invoke the brain's start method (``start`` or ``run``)."""
        for method_name in ("start", "run", "submit", "execute"):
            method = getattr(self._brain, method_name, None)
            if callable(method):
                try:
                    return method(goal)
                except Exception:  # noqa: BLE001
                    continue
        return None

    def _call_cancel(self, goal_id: str) -> bool:
        """Invoke the brain's cancel method."""
        for method_name in ("cancel", "stop", "abort"):
            method = getattr(self._brain, method_name, None)
            if callable(method):
                try:
                    result = method(goal_id)
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(result, bool):
                    return result
                return result is not None
        return False

    def _to_timeline(self, goal: Any, status: str | None = None) -> ExecutionTimeline:
        """Convert a goal-like object into an :class:`ExecutionTimeline`."""
        goal_id = str(getattr(goal, "id", "") or getattr(goal, "goal_id", "") or "")
        description = str(getattr(goal, "description", "") or "")
        steps = self._extract_steps(goal)
        current_step = _as_int(getattr(goal, "current_step", 0), 0)
        derived_status = status or str(getattr(goal, "status", "") or "running")
        started_at = getattr(goal, "started_at", None)
        completed_at = getattr(goal, "completed_at", None)
        return ExecutionTimeline(
            goal_id=goal_id,
            description=description,
            steps=steps,
            current_step=current_step,
            status=derived_status,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _extract_steps(goal: Any) -> list[ExecutionStep]:
        """Pull a list of :class:`ExecutionStep` from a goal-like."""
        raw = getattr(goal, "steps", None)
        if raw is None:
            raw = getattr(goal, "tasks", None)
        if not raw:
            return []
        steps: list[ExecutionStep] = []
        for item in raw:
            name = str(
                getattr(item, "name", "") or getattr(item, "capability", "") or "step"
            )
            step_status = str(getattr(item, "status", "pending") or "pending")
            started = getattr(item, "started_at", None)
            completed = getattr(item, "completed_at", None)
            duration = _as_float(
                getattr(item, "duration", 0.0) or getattr(item, "duration_seconds", 0.0)
            )
            detail = str(
                getattr(item, "detail", "") or getattr(item, "error", "") or ""
            )
            steps.append(
                ExecutionStep(
                    name=name,
                    status=step_status,
                    started_at=started,
                    completed_at=completed,
                    duration=duration,
                    detail=detail,
                )
            )
        return steps

    def _archive(self, timeline: ExecutionTimeline, status: str) -> None:
        """Move a finished timeline into history with the given status."""
        from dataclasses import replace as _dc_replace

        finished = _dc_replace(timeline, status=status, completed_at=datetime.now(UTC))
        self._history.insert(0, finished)
        if len(self._history) > self._history_size:
            self._history = self._history[: self._history_size]


def _as_int(value: Any, default: int) -> int:
    """Coerce ``value`` to ``int``; return ``default`` on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float:
    """Coerce ``value`` to ``float``; return ``0.0`` on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["ExecutionController"]
