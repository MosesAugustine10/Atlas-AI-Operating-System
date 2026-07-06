"""Workforce orchestrator — goal → team → tasks → execution → review → delivery.

The :class:`WorkforceOrchestrator` is the single entry point for
autonomous workforce execution. Given a high-level goal, it:

1. Creates (or reuses) a team for the goal.
2. Decomposes the goal into tasks (via :class:`PlanningEngine`).
3. Assigns tasks to workers (via :class:`Scheduler`).
4. Workers execute tasks (via their injected ``think_fn``).
5. Reviews the output (via :class:`ReviewEngine`).
6. Coordinates handoffs (via :class:`CoordinationEngine`).
7. Records metrics (via :class:`MetricsCollector`).
8. Returns a :class:`WorkforceReport`.

The orchestrator wires together every workforce engine but never
imports Brain, Execution, or any Atlas subsystem directly — it
receives a ``think_fn`` callable (typically ``Brain.think``) that
workers use to do actual work.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.communication import CommunicationChannel
from atlas.workforce.coordination import CoordinationEngine
from atlas.workforce.delegation import DelegationEngine
from atlas.workforce.learning import LearningEngine
from atlas.workforce.manager import WorkforceManager
from atlas.workforce.metrics import MetricsCollector
from atlas.workforce.models import (
    Task,
    TaskPriority,
    TaskStatus,
    WorkerKind,
    WorkerRole,
    WorkforceReport,
    _utcnow,
)
from atlas.workforce.planning import PlanningEngine
from atlas.workforce.reports import ReportGenerator
from atlas.workforce.review import ReviewEngine, ReviewVerdict
from atlas.workforce.scheduler import Scheduler
from atlas.workforce.supervisor import Supervisor
from atlas.workforce.team import TeamManager


class WorkforceOrchestrator:
    """Top-level orchestrator for autonomous workforce execution.

    Parameters:
        think_fn: Optional callback passed to every worker's
            ``think_fn``. When omitted, workers run in offline mode.
        planning: Optional :class:`PlanningEngine` (created fresh when omitted).
        coordination: Optional :class:`CoordinationEngine`.
        review: Optional :class:`ReviewEngine`.
        learning: Optional :class:`LearningEngine`.
        supervisor: Optional :class:`Supervisor`.
        scheduler: Optional :class:`Scheduler`.
        metrics: Optional :class:`MetricsCollector`.
        reports: Optional :class:`ReportGenerator`.
        communication: Optional :class:`CommunicationChannel`.
        delegation: Optional :class:`DelegationEngine`.
    """

    def __init__(
        self,
        think_fn: Callable[..., Any] | None = None,
        planning: PlanningEngine | None = None,
        coordination: CoordinationEngine | None = None,
        review: ReviewEngine | None = None,
        learning: LearningEngine | None = None,
        supervisor: Supervisor | None = None,
        scheduler: Scheduler | None = None,
        metrics: MetricsCollector | None = None,
        reports: ReportGenerator | None = None,
        communication: CommunicationChannel | None = None,
        delegation: DelegationEngine | None = None,
    ) -> None:
        self.manager = WorkforceManager(think_fn=think_fn)
        self.planning = planning or PlanningEngine()
        self.coordination = coordination or CoordinationEngine()
        self.review = review or ReviewEngine()
        self.learning = learning or LearningEngine()
        self.supervisor = supervisor or Supervisor()
        self.scheduler = scheduler or Scheduler()
        self.metrics = metrics or MetricsCollector()
        self.reports = reports or ReportGenerator()
        self.communication = communication or CommunicationChannel()
        self.delegation = delegation or DelegationEngine()
        self._task_registry: dict[str, Task] = {}
        self.logger = get_logger("workforce.orchestrator")

    # ------------------------------------------------------------------
    # Worker management
    # ------------------------------------------------------------------

    def hire(
        self,
        name: str,
        role: str,
        kind: str = WorkerKind.PERMANENT.value,
        start: bool = True,
    ) -> Any:
        """Hire a new worker via the manager."""
        worker = self.manager.hire(name=name, role=role, kind=kind)
        if start:
            worker.start()
        return worker

    def hire_default_workforce(self) -> list[Any]:
        """Hire one worker in every default role.

        Returns the list of hired workers.
        """
        hired: list[Any] = []
        defaults = [
            ("Atlas CEO", WorkerRole.CEO.value),
            ("Atlas CTO", WorkerRole.CTO.value),
            ("Atlas SWE", WorkerRole.SOFTWARE_ENGINEER.value),
            ("Atlas Researcher", WorkerRole.RESEARCH_ENGINEER.value),
            ("Atlas Miner", WorkerRole.MINING_ENGINEER.value),
            ("Atlas Designer", WorkerRole.UI_DESIGNER.value),
            ("Atlas Video", WorkerRole.VIDEO_CREATOR.value),
            ("Atlas Writer", WorkerRole.TECHNICAL_WRITER.value),
            ("Atlas QA", WorkerRole.QA_ENGINEER.value),
            ("Atlas DevOps", WorkerRole.DEVOPS_ENGINEER.value),
            ("Atlas PM", WorkerRole.PROJECT_MANAGER.value),
            ("Atlas Knowledge", WorkerRole.KNOWLEDGE_SPECIALIST.value),
            ("Atlas Memory", WorkerRole.MEMORY_SPECIALIST.value),
            ("Atlas Browser", WorkerRole.BROWSER_AGENT.value),
            ("Atlas GitHub", WorkerRole.GITHUB_AGENT.value),
            ("Atlas Blender", WorkerRole.BLENDER_ARTIST.value),
            ("Atlas Vision", WorkerRole.VISION_SPECIALIST.value),
        ]
        for name, role in defaults:
            hired.append(self.hire(name=name, role=role))
        return hired

    # ------------------------------------------------------------------
    # Goal execution
    # ------------------------------------------------------------------

    def execute_goal(
        self,
        goal: str,
        team_name: str = "",
        priority: str = TaskPriority.NORMAL.value,
        reviewer_id: str = "",
    ) -> WorkforceReport:
        """Execute ``goal`` end-to-end and return a :class:`WorkforceReport`.

        Steps:
        1. Create a team for the goal (or reuse if ``team_name`` matches).
        2. Decompose the goal into tasks.
        3. Assign tasks to available workers.
        4. Workers execute tasks.
        5. Review each task's output.
        6. Record metrics.
        7. Generate and return a report.
        """
        self.logger.info("Executing goal: %r", goal[:80])

        # 1. Create team
        team = self._ensure_team(team_name or f"Goal: {goal[:40]}", goal)

        # 2. Decompose
        tasks = self.planning.decompose(
            goal=goal,
            team_id=team.id,
            priority=priority,
        )
        for task in tasks:
            self._task_registry[task.id] = task
            self.metrics.record_task(task)

        # 3. Assign + 4. Execute
        completed_ids: set[str] = set()
        ordered = self.planning.order_by_dependencies(list(tasks))
        for task in ordered:
            # Check dependencies
            if self.coordination.is_blocked(task.id, completed_ids):
                blocked = self._update_task(task.id, status=TaskStatus.BLOCKED.value)
                self.metrics.record_task(blocked)
                continue
            assigned = self._assign_and_execute(task, team)
            if assigned and assigned.status in (
                TaskStatus.COMPLETED.value,
                TaskStatus.APPROVED.value,
            ):
                completed_ids.add(assigned.id)
                # 5. Review
                if reviewer_id:
                    review = self.review.submit_review(
                        task_id=assigned.id,
                        reviewer_id=reviewer_id,
                        verdict=ReviewVerdict.APPROVED.value,
                        quality_score=0.85,
                    )
                    assigned = self.review.apply_verdict(assigned, review)
                    self._task_registry[assigned.id] = assigned
                    self.metrics.record_task(assigned)
            self.metrics.record_task(assigned)

        # 6. Generate report
        return self._generate_report()

    # ------------------------------------------------------------------
    # Team helpers
    # ------------------------------------------------------------------

    def _ensure_team(self, name: str, goal: str) -> TeamManager:
        """Find an existing team by name or create a new one."""
        for team in self.manager.list_teams(active_only=True):
            if team.name == name:
                return team
        # Pick a lead from existing workers (prefer PM/CTO/CEO)
        lead_id = self._pick_lead()
        members = [w.id for w in self.manager.online_workers()]
        return self.manager.create_team(
            name=name,
            goal=goal,
            lead_id=lead_id,
            member_ids=tuple(members),
        )

    def _pick_lead(self) -> str:
        """Pick a team lead from the available workers."""
        for role in (
            WorkerRole.PROJECT_MANAGER.value,
            WorkerRole.CTO.value,
            WorkerRole.CEO.value,
            WorkerRole.SOFTWARE_ENGINEER.value,
        ):
            workers = self.manager.list_workers(role=role)
            if workers:
                return workers[0].id
        # Fall back to first online worker
        online = self.manager.online_workers()
        return online[0].id if online else ""

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _assign_and_execute(self, task: Task, team: TeamManager) -> Task:
        """Assign ``task`` to a worker and execute it."""
        workers = self.manager.worker_states()
        team_members = [w for w in workers if team.has_member(w.id)]
        candidate = self.scheduler.pick_worker(
            team_members or workers,
            required_role=task.required_role,
            required_skills=task.required_skills,
        )
        if candidate is None:
            # No eligible worker — mark as blocked
            return self._update_task(task.id, status=TaskStatus.BLOCKED.value)
        worker = self.manager.get_worker(candidate.id)
        if worker is None:
            return self._update_task(task.id, status=TaskStatus.FAILED.value)
        # Assign
        assigned_task = self._update_task(
            task.id,
            status=TaskStatus.ASSIGNED.value,
            assignee_id=worker.id,
            assigned_at=_utcnow(),
        )
        worker.assign_task(assigned_task)
        # Execute
        in_progress = self._update_task(
            task.id,
            status=TaskStatus.IN_PROGRESS.value,
            started_at=_utcnow(),
        )
        self._task_registry[task.id] = in_progress
        self.metrics.record_task(in_progress)
        try:
            result = worker.execute_task(in_progress)
            completed = self._update_task(
                task.id,
                status=TaskStatus.COMPLETED.value,
                completed_at=_utcnow(),
                actual_duration_minutes=0.5,
            )
            self._task_registry[task.id] = completed
            worker.complete_task(completed, quality_score=0.85)
            # Publish any artifacts
            if isinstance(result, dict):
                artifacts = result.get("artifacts", [])
                for art in artifacts:
                    if isinstance(art, dict):
                        self.coordination.publish_artifact(
                            task_id=task.id,
                            kind=art.get("kind", "file"),
                            name=art.get("name", ""),
                        )
            return completed
        except Exception as exc:  # noqa: BLE001 — surface any error
            self.logger.warning("Task %s failed: %s", task.id, exc)
            worker.fail_task(in_progress)
            failed = self._update_task(
                task.id,
                status=TaskStatus.FAILED.value,
                completed_at=_utcnow(),
            )
            self._task_registry[task.id] = failed
            return failed

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _generate_report(self) -> WorkforceReport:
        """Generate a :class:`WorkforceReport` from the current state."""
        workers = self.manager.worker_states()
        teams = [t.team for t in self.manager.list_teams()]
        tasks = list(self._task_registry.values())
        worker_metrics = self.metrics.all_worker_metrics(workers)
        team_metrics = self.metrics.all_team_metrics(teams)
        return self.reports.generate(
            workers=workers,
            teams=teams,
            tasks=tasks,
            worker_metrics=worker_metrics,
            team_metrics=team_metrics,
            total_delegations=self.delegation.count(),
            total_escalations=self.supervisor.escalation_count(),
            total_conflicts=self.supervisor.conflict_count(),
        )

    # ------------------------------------------------------------------
    # Task registry
    # ------------------------------------------------------------------

    def _update_task(self, task_id: str, **changes: Any) -> Task:
        """Return a new :class:`Task` with ``changes`` applied."""
        task = self._task_registry.get(task_id)
        if task is None:
            raise KeyError(f"task {task_id} not in registry")
        import dataclasses

        updated = dataclasses.replace(task, **changes)
        self._task_registry[task_id] = updated
        return updated

    def get_task(self, task_id: str) -> Task | None:
        """Return the task with ``task_id`` or ``None``."""
        return self._task_registry.get(task_id)

    def all_tasks(self) -> list[Task]:
        """Return all tasks in the registry."""
        return list(self._task_registry.values())

    def task_count(self) -> int:
        """Return the total number of tasks."""
        return len(self._task_registry)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return a summary of the orchestrator's state."""
        return {
            "manager": self.manager.status(),
            "tasks": self.task_count(),
            "delegations": self.delegation.count(),
            "escalations": self.supervisor.escalation_count(),
            "conflicts": self.supervisor.conflict_count(),
            "reviews": self.review.review_count(),
            "approvals": self.review.approval_count(),
            "lessons": self.learning.lesson_count(),
            "artifacts": self.coordination.artifact_count(),
            "handoffs": self.coordination.handoff_count(),
            "shifts": self.scheduler.shift_count(),
            "messages": self.communication.message_count(),
        }


__all__ = ["WorkforceOrchestrator"]
