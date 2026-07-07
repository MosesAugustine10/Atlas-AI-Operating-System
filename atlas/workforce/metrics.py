"""Metrics collector — per-worker and team productivity metrics.

The :class:`MetricsCollector` observes workforce activity (task
completions, failures, delegations, reviews, etc.) and computes
:class:`~atlas.workforce.models.WorkerMetrics` and
:class:`~atlas.workforce.models.TeamMetrics` snapshots.
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Task,
    TaskStatus,
    Team,
    TeamMetrics,
    WorkerMetrics,
    WorkerState,
    _utcnow,
)


class MetricsCollector:
    """Collects and computes workforce productivity metrics."""

    def __init__(self) -> None:
        self._task_history: list[Task] = []
        self.logger = get_logger("workforce.metrics")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_task(self, task: Task) -> None:
        """Record a task (or its updated state) in the metrics history."""
        # Replace any existing record with the same id
        self._task_history = [t for t in self._task_history if t.id != task.id]
        self._task_history.append(task)

    def record_tasks(self, tasks: list[Task]) -> None:
        """Record multiple tasks."""
        for task in tasks:
            self.record_task(task)

    # ------------------------------------------------------------------
    # Worker metrics
    # ------------------------------------------------------------------

    def worker_metrics(
        self,
        worker_id: str,
        workers: list[WorkerState] | None = None,
    ) -> WorkerMetrics:
        """Compute :class:`WorkerMetrics` for ``worker_id``."""
        assigned = [t for t in self._task_history if t.assignee_id == worker_id]
        completed = [
            t
            for t in assigned
            if t.status in (TaskStatus.COMPLETED.value, TaskStatus.APPROVED.value)
        ]
        failed = [t for t in assigned if t.status == TaskStatus.FAILED.value]
        rejected = [t for t in assigned if t.status == TaskStatus.REJECTED.value]
        quality_scores = [t.quality_score for t in completed if t.quality_score >= 0.0]
        durations = [
            t.actual_duration_minutes
            for t in completed
            if t.actual_duration_minutes > 0
        ]
        artifacts = sum(len(t.artifacts) for t in completed)
        return WorkerMetrics(
            worker_id=worker_id,
            tasks_assigned=len(assigned),
            tasks_completed=len(completed),
            tasks_failed=len(failed),
            tasks_rejected=len(rejected),
            average_quality=(
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            ),
            average_duration_minutes=(
                sum(durations) / len(durations) if durations else 0.0
            ),
            total_artifacts=artifacts,
            last_updated=_utcnow(),
        )

    def all_worker_metrics(
        self,
        workers: list[WorkerState],
    ) -> dict[str, WorkerMetrics]:
        """Compute :class:`WorkerMetrics` for every worker in ``workers``."""
        return {w.id: self.worker_metrics(w.id) for w in workers}

    # ------------------------------------------------------------------
    # Team metrics
    # ------------------------------------------------------------------

    def team_metrics(self, team: Team) -> TeamMetrics:
        """Compute :class:`TeamMetrics` for ``team``."""
        team_tasks = [t for t in self._task_history if t.team_id == team.id]
        completed = [
            t
            for t in team_tasks
            if t.status in (TaskStatus.COMPLETED.value, TaskStatus.APPROVED.value)
        ]
        failed = [t for t in team_tasks if t.status == TaskStatus.FAILED.value]
        quality_scores = [t.quality_score for t in completed if t.quality_score >= 0.0]
        artifacts = sum(len(t.artifacts) for t in completed)
        return TeamMetrics(
            team_id=team.id,
            worker_count=len(team.member_ids),
            tasks_total=len(team_tasks),
            tasks_completed=len(completed),
            tasks_failed=len(failed),
            average_quality=(
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            ),
            total_artifacts=artifacts,
            last_updated=_utcnow(),
        )

    def all_team_metrics(self, teams: list[Team]) -> dict[str, TeamMetrics]:
        """Compute :class:`TeamMetrics` for every team in ``teams``."""
        return {t.id: self.team_metrics(t) for t in teams}

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def top_performers(
        self,
        workers: list[WorkerState],
        limit: int = 5,
    ) -> list[WorkerMetrics]:
        """Return the ``limit`` workers with the most completed tasks."""
        metrics = list(self.all_worker_metrics(workers).values())
        metrics.sort(key=lambda m: m.tasks_completed, reverse=True)
        return metrics[:limit]

    def bottom_performers(
        self,
        workers: list[WorkerState],
        limit: int = 5,
    ) -> list[WorkerMetrics]:
        """Return the ``limit`` workers with the highest failure rates."""
        metrics = list(self.all_worker_metrics(workers).values())
        metrics.sort(key=lambda m: m.failure_rate(), reverse=True)
        return metrics[:limit]

    def workforce_completion_rate(self) -> float:
        """Return the overall task completion rate (0.0 to 1.0)."""
        if not self._task_history:
            return 0.0
        completed = sum(
            1
            for t in self._task_history
            if t.status in (TaskStatus.COMPLETED.value, TaskStatus.APPROVED.value)
        )
        return completed / len(self._task_history)

    def workforce_average_quality(self) -> float:
        """Return the overall average quality score across completed tasks."""
        quality_scores = [
            t.quality_score
            for t in self._task_history
            if t.status in (TaskStatus.COMPLETED.value, TaskStatus.APPROVED.value)
            and t.quality_score >= 0.0
        ]
        if not quality_scores:
            return 0.0
        return sum(quality_scores) / len(quality_scores)

    def task_count(self) -> int:
        """Return the total number of recorded tasks."""
        return len(self._task_history)

    def clear(self) -> None:
        """Clear all recorded tasks."""
        self._task_history.clear()


__all__ = ["MetricsCollector"]
