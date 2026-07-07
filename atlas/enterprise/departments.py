"""Department manager — built-in departments and employee profiles."""

from __future__ import annotations

import dataclasses

from atlas.enterprise.models import (
    Department,
    DepartmentMetrics,
    DepartmentType,
    EmployeeProfile,
    ResourcePool,
    _new_id,
)

_BUILTIN_DEPARTMENTS: list[tuple[str, str]] = [
    (DepartmentType.CEO.value, "CEO"),
    (DepartmentType.FINANCE.value, "Finance"),
    (DepartmentType.SALES.value, "Sales"),
    (DepartmentType.MARKETING.value, "Marketing"),
    (DepartmentType.ENGINEERING.value, "Engineering"),
    (DepartmentType.DESIGN.value, "Design"),
    (DepartmentType.MINING.value, "Mining"),
    (DepartmentType.RESEARCH.value, "Research"),
    (DepartmentType.OPERATIONS.value, "Operations"),
    (DepartmentType.LEGAL.value, "Legal"),
    (DepartmentType.HR.value, "HR"),
    (DepartmentType.SUPPORT.value, "Support"),
]


class DepartmentManager:
    """Manages departments, employees, and resource pools."""

    def __init__(self) -> None:
        self._departments: dict[str, Department] = {}
        self._employees: dict[str, EmployeeProfile] = {}
        self._resources: dict[str, ResourcePool] = {}

    def create(
        self,
        name: str,
        type: str = DepartmentType.OPERATIONS.value,
        head: str = "",
        budget: float = 0.0,
    ) -> Department:
        d = Department(
            id=_new_id("dept"), name=name, type=type, head=head, budget=budget
        )
        self._departments[d.id] = d
        return d

    def get(self, did: str) -> Department | None:
        return self._departments.get(did)

    def list(self, type: str | None = None) -> list[Department]:
        ds = list(self._departments.values())
        if type is not None:
            ds = [d for d in ds if d.type == type]
        return ds

    def add_employee(
        self, name: str, email: str = "", department_id: str = "", role: str = ""
    ) -> EmployeeProfile:
        e = EmployeeProfile(
            id=_new_id("emp"),
            name=name,
            email=email,
            department_id=department_id,
            role=role,
        )
        self._employees[e.id] = e
        if department_id:
            d = self._departments.get(department_id)
            if d:
                members = (*d.member_ids, e.id)
                updated = dataclasses.replace(d, member_ids=members)
                self._departments[department_id] = updated
        return e

    def get_employee(self, eid: str) -> EmployeeProfile | None:
        return self._employees.get(eid)

    def list_employees(
        self, department_id: str | None = None, active_only: bool = False
    ) -> list[EmployeeProfile]:
        es = list(self._employees.values())
        if department_id is not None:
            es = [e for e in es if e.department_id == department_id]
        if active_only:
            es = [e for e in es if e.active]
        return es

    def create_resource(
        self, name: str, department_id: str = "", capacity: int = 0, unit: str = "units"
    ) -> ResourcePool:
        r = ResourcePool(
            id=_new_id("res"),
            name=name,
            department_id=department_id,
            capacity=capacity,
            unit=unit,
        )
        self._resources[r.id] = r
        return r

    def get_resource(self, rid: str) -> ResourcePool | None:
        return self._resources.get(rid)

    def allocate(self, rid: str, amount: int = 1) -> ResourcePool | None:
        r = self._resources.get(rid)
        if r is None:
            return None
        updated = dataclasses.replace(
            r, allocated=min(r.capacity, r.allocated + amount)
        )
        self._resources[rid] = updated
        return updated

    def release(self, rid: str, amount: int = 1) -> ResourcePool | None:
        r = self._resources.get(rid)
        if r is None:
            return None
        updated = dataclasses.replace(r, allocated=max(0, r.allocated - amount))
        self._resources[rid] = updated
        return updated

    def metrics(self, did: str) -> DepartmentMetrics:
        d = self._departments.get(did)
        members = d.member_ids if d else ()
        return DepartmentMetrics(
            department_id=did,
            headcount=len(members),
            budget_used=0.0,
            budget_remaining=d.budget if d else 0.0,
        )

    def load_builtins(self) -> list[Department]:
        """Create all 12 built-in departments."""
        created: list[Department] = []
        for dtype, dname in _BUILTIN_DEPARTMENTS:
            if not any(d.type == dtype for d in self._departments.values()):
                d = self.create(name=dname, type=dtype)
                created.append(d)
        return created

    def count(self) -> int:
        return len(self._departments)

    def employee_count(self) -> int:
        return len(self._employees)


__all__ = ["DepartmentManager"]
