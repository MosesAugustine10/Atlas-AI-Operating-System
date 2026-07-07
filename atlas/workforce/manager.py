"""Workforce manager — owns all workers and teams.

The :class:`WorkforceManager` is the top-level facade for the
workforce. It owns every :class:`~atlas.workforce.worker.Worker`
instance and every :class:`~atlas.workforce.team.TeamManager`, and
exposes operations for hiring, firing, team creation, and
workforce-wide queries.

The manager never imports Brain or any subsystem directly — workers
receive their ``think_fn`` callback at construction time, keeping
the package decoupled.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    WorkerKind,
    WorkerRole,
    WorkerState,
    WorkerStatus,
)
from atlas.workforce.team import TeamManager
from atlas.workforce.worker import Worker, WorkerError


class WorkforceManager:
    """Owns every worker and team in the workforce.

    Parameters:
        think_fn: Optional callback passed to every new worker's
            ``think_fn``. When omitted, workers run in offline mode
            (returning placeholder results).
    """

    def __init__(
        self,
        think_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._workers: dict[str, Worker] = {}
        self._teams: dict[str, TeamManager] = {}
        self._think_fn = think_fn
        self.logger = get_logger("workforce.manager")

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def hire(
        self,
        name: str,
        role: str,
        kind: str = WorkerKind.PERMANENT.value,
        skills: Any = None,
        think_fn: Callable[..., Any] | None = None,
    ) -> Worker:
        """Hire a new worker and return it.

        The worker starts in OFFLINE status — call :meth:`Worker.start`
        to bring it online.
        """
        worker = Worker(
            name=name,
            role=role,
            kind=kind,
            think_fn=think_fn or self._think_fn,
            skills=skills,
        )
        self._workers[worker.id] = worker
        self.logger.info("Hired worker %s (%s, %s)", worker.id, name, role)
        return worker

    def fire(self, worker_id: str) -> bool:
        """Fire a worker. Returns ``True`` if the worker was removed."""
        worker = self._workers.get(worker_id)
        if worker is None:
            return False
        worker.stop()
        removed = self._workers.pop(worker_id, None) is not None
        # Remove from all teams
        for team in self._teams.values():
            team.remove_member(worker_id)
        if removed:
            self.logger.info("Fired worker %s", worker_id)
        return removed

    def get_worker(self, worker_id: str) -> Worker | None:
        """Return the worker with ``worker_id`` or ``None``."""
        return self._workers.get(worker_id)

    def list_workers(
        self,
        role: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ) -> list[Worker]:
        """List workers with optional filters."""
        workers = list(self._workers.values())
        if role is not None:
            workers = [w for w in workers if w.role == role]
        if status is not None:
            workers = [w for w in workers if w.status == status]
        if kind is not None:
            workers = [w for w in workers if w.state.kind == kind]
        return workers

    def worker_count(self) -> int:
        """Return the total number of workers."""
        return len(self._workers)

    def online_workers(self) -> list[Worker]:
        """Return all online workers (idle or busy)."""
        return [
            w
            for w in self._workers.values()
            if w.status in (WorkerStatus.IDLE.value, WorkerStatus.BUSY.value)
        ]

    def idle_workers(self) -> list[Worker]:
        """Return all idle workers."""
        return [w for w in self._workers.values() if w.is_idle]

    # ------------------------------------------------------------------
    # Convenience: hire by role
    # ------------------------------------------------------------------

    def hire_executive(self, name: str, role: str = WorkerRole.CEO.value) -> Worker:
        """Hire an executive (CEO or CTO)."""
        if role not in (WorkerRole.CEO.value, WorkerRole.CTO.value):
            raise WorkerError(f"role {role} is not an executive role")
        return self.hire(name=name, role=role)

    def hire_engineer(
        self, name: str, role: str = WorkerRole.SOFTWARE_ENGINEER.value
    ) -> Worker:
        """Hire an engineer."""
        return self.hire(name=name, role=role)

    def hire_agent(
        self, name: str, role: str = WorkerRole.BROWSER_AGENT.value
    ) -> Worker:
        """Hire an automated agent."""
        return self.hire(name=name, role=role, kind=WorkerKind.TEMPORARY.value)

    def hire_temporary(
        self,
        name: str,
        role: str,
        think_fn: Callable[..., Any] | None = None,
    ) -> Worker:
        """Hire a temporary worker."""
        return self.hire(
            name=name, role=role, kind=WorkerKind.TEMPORARY.value, think_fn=think_fn
        )

    # ------------------------------------------------------------------
    # Team lifecycle
    # ------------------------------------------------------------------

    def create_team(
        self,
        name: str,
        goal: str = "",
        lead_id: str = "",
        member_ids: tuple[str, ...] = (),
        kind: str = WorkerKind.PERMANENT.value,
    ) -> TeamManager:
        """Create a new team and return its :class:`TeamManager`."""
        # Validate that all members exist
        for mid in member_ids:
            if mid not in self._workers:
                raise WorkerError(f"worker {mid} is not in the workforce")
        if lead_id and lead_id not in self._workers:
            raise WorkerError(f"lead {lead_id} is not in the workforce")
        team_mgr = TeamManager.create(
            name=name,
            goal=goal,
            lead_id=lead_id,
            member_ids=member_ids,
            kind=kind,
        )
        self._teams[team_mgr.id] = team_mgr
        self.logger.info("Created team %s (%s)", team_mgr.id, name)
        return team_mgr

    def get_team(self, team_id: str) -> TeamManager | None:
        """Return the team manager for ``team_id`` or ``None``."""
        return self._teams.get(team_id)

    def list_teams(self, active_only: bool = False) -> list[TeamManager]:
        """List teams, optionally filtered to active-only."""
        teams = list(self._teams.values())
        if active_only:
            teams = [t for t in teams if t.is_active]
        return teams

    def disband_team(self, team_id: str) -> bool:
        """Disband a team. Returns ``True`` if the team was disbanded."""
        team = self._teams.get(team_id)
        if team is None:
            return False
        team.disband()
        return True

    def team_count(self) -> int:
        """Return the total number of teams."""
        return len(self._teams)

    def active_team_count(self) -> int:
        """Return the number of active teams."""
        return sum(1 for t in self._teams.values() if t.is_active)

    # ------------------------------------------------------------------
    # Workforce state
    # ------------------------------------------------------------------

    def worker_states(self) -> list[WorkerState]:
        """Return the current :class:`WorkerState` for every worker."""
        return [w.state for w in self._workers.values()]

    def status(self) -> dict[str, Any]:
        """Return a summary of the workforce state."""
        return {
            "total_workers": self.worker_count(),
            "online_workers": len(self.online_workers()),
            "idle_workers": len(self.idle_workers()),
            "total_teams": self.team_count(),
            "active_teams": self.active_team_count(),
        }

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def start_all(self) -> None:
        """Start every offline worker."""
        for worker in self._workers.values():
            worker.start()

    def stop_all(self) -> None:
        """Stop every worker."""
        for worker in self._workers.values():
            worker.stop()

    def disband_all_teams(self) -> None:
        """Disband every team."""
        for team in self._teams.values():
            team.disband()


__all__ = ["WorkforceManager"]
