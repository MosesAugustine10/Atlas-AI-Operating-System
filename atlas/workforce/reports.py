"""Report generator — workforce-wide reports and summaries.

The :class:`ReportGenerator` produces :class:`WorkforceReport`
snapshots from the current state of the workforce (workers, teams,
tasks, metrics, escalations, conflicts).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Task,
    TaskStatus,
    Team,
    TeamMetrics,
    WorkerMetrics,
    WorkerState,
    WorkerStatus,
    WorkforceReport,
    _new_id,
    _utcnow,
)


class ReportGenerator:
    """Generates :class:`WorkforceReport` snapshots."""

    def __init__(self) -> None:
        self.logger = get_logger("workforce.reports")

    def generate(
        self,
        workers: list[WorkerState],
        teams: list[Team],
        tasks: list[Task],
        worker_metrics: dict[str, WorkerMetrics] | None = None,
        team_metrics: dict[str, TeamMetrics] | None = None,
        total_delegations: int = 0,
        total_escalations: int = 0,
        total_conflicts: int = 0,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> WorkforceReport:
        """Generate a :class:`WorkforceReport` from the current state."""
        active_workers = [
            w
            for w in workers
            if w.status in (WorkerStatus.IDLE.value, WorkerStatus.BUSY.value)
        ]
        active_teams = [t for t in teams if t.disbanded_at is None]
        completed = [
            t
            for t in tasks
            if t.status in (TaskStatus.COMPLETED.value, TaskStatus.APPROVED.value)
        ]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED.value]
        in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS.value]
        quality_scores = [t.quality_score for t in completed if t.quality_score >= 0.0]
        artifacts = sum(len(t.artifacts) for t in completed)
        wm = tuple(worker_metrics.values() if worker_metrics else ())
        tm = tuple(team_metrics.values() if team_metrics else ())
        return WorkforceReport(
            id=_new_id("report"),
            generated_at=_utcnow(),
            total_workers=len(workers),
            active_workers=len(active_workers),
            total_teams=len(teams),
            active_teams=len(active_teams),
            total_tasks=len(tasks),
            completed_tasks=len(completed),
            failed_tasks=len(failed),
            in_progress_tasks=len(in_progress),
            average_quality=(
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            ),
            total_artifacts=artifacts,
            total_delegations=total_delegations,
            total_escalations=total_escalations,
            total_conflicts=total_conflicts,
            worker_metrics=wm,
            team_metrics=tm,
            period_start=period_start,
            period_end=period_end,
        )

    def summary(self, report: WorkforceReport) -> dict[str, Any]:
        """Return a flat dict summary of ``report`` for quick display."""
        return {
            "total_workers": report.total_workers,
            "active_workers": report.active_workers,
            "total_teams": report.total_teams,
            "active_teams": report.active_teams,
            "total_tasks": report.total_tasks,
            "completed_tasks": report.completed_tasks,
            "failed_tasks": report.failed_tasks,
            "in_progress_tasks": report.in_progress_tasks,
            "average_quality": round(report.average_quality, 3),
            "total_artifacts": report.total_artifacts,
            "completion_rate": (
                round(report.completed_tasks / report.total_tasks, 3)
                if report.total_tasks
                else 0.0
            ),
            "total_delegations": report.total_delegations,
            "total_escalations": report.total_escalations,
            "total_conflicts": report.total_conflicts,
        }

    def top_workers(
        self,
        report: WorkforceReport,
        limit: int = 5,
    ) -> list[WorkerMetrics]:
        """Return the ``limit`` top-performing workers from ``report``."""
        workers = sorted(
            report.worker_metrics,
            key=lambda m: m.tasks_completed,
            reverse=True,
        )
        return workers[:limit]


__all__ = ["ReportGenerator"]
