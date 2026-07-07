"""Project and task management."""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.business.models import (
    Project,
    Task,
    TaskPriority,
    TaskStatus,
    _new_id,
    _utcnow,
)


class ProjectManager:
    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}
        self._tasks: dict[str, Task] = {}

    def create(
        self,
        name: str,
        description: str = "",
        customer_id: str = "",
        budget: float = 0.0,
        start_date: Any | None = None,
        end_date: Any | None = None,
    ) -> Project:
        p = Project(
            id=_new_id("proj"),
            name=name,
            description=description,
            customer_id=customer_id,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
        )
        self._projects[p.id] = p
        return p

    def get(self, pid: str) -> Project | None:
        return self._projects.get(pid)

    def list(
        self, status: str | None = None, customer_id: str | None = None
    ) -> list[Project]:
        ps = list(self._projects.values())
        if status is not None:
            ps = [p for p in ps if p.status == status]
        if customer_id is not None:
            ps = [p for p in ps if p.customer_id == customer_id]
        return ps

    def update(self, pid: str, **changes: Any) -> Project:
        p = self._require(pid)
        updated = dataclasses.replace(p, **changes, updated_at=_utcnow())
        self._projects[pid] = updated
        return updated

    def delete(self, pid: str) -> bool:
        return self._projects.pop(pid, None) is not None

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        priority: str = TaskPriority.NORMAL.value,
        assignee: str = "",
        due_date: Any | None = None,
    ) -> Task:
        t = Task(
            id=_new_id("task"),
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            assignee=assignee,
            due_date=due_date,
        )
        self._tasks[t.id] = t
        return t

    def get_task(self, tid: str) -> Task | None:
        return self._tasks.get(tid)

    def list_tasks(
        self, project_id: str | None = None, status: str | None = None
    ) -> list[Task]:
        ts = list(self._tasks.values())
        if project_id is not None:
            ts = [t for t in ts if t.project_id == project_id]
        if status is not None:
            ts = [t for t in ts if t.status == status]
        return ts

    def complete_task(self, tid: str) -> Task | None:
        t = self._tasks.get(tid)
        if t is None:
            return None
        updated = dataclasses.replace(
            t, status=TaskStatus.COMPLETED.value, completed_at=_utcnow()
        )
        self._tasks[tid] = updated
        return updated

    def task_count(self) -> int:
        return len(self._tasks)

    def pending_task_count(self) -> int:
        return sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.PENDING.value
        )

    def _require(self, pid: str) -> Project:
        p = self._projects.get(pid)
        if p is None:
            raise KeyError(f"project {pid} not found")
        return p


__all__ = ["ProjectManager"]
