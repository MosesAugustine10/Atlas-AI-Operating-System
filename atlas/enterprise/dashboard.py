"""Enterprise dashboard — executive summaries and KPIs."""

from __future__ import annotations

from typing import Any

from atlas.enterprise.approval import ApprovalEngine
from atlas.enterprise.automation import AutomationEngine
from atlas.enterprise.compliance import ComplianceEngine
from atlas.enterprise.departments import DepartmentManager
from atlas.enterprise.forecast import ForecastEngine
from atlas.enterprise.models import (
    BusinessAlert,
    CompanySnapshot,
    GrowthMetric,
    _new_id,
)
from atlas.enterprise.optimization import OptimizationEngine
from atlas.enterprise.processes import ProcessEngine


class EnterpriseDashboard:
    """Generates executive dashboard data from all enterprise subsystems."""

    def __init__(
        self,
        automation: AutomationEngine | None = None,
        approval: ApprovalEngine | None = None,
        compliance: ComplianceEngine | None = None,
        departments: DepartmentManager | None = None,
        forecast: ForecastEngine | None = None,
        optimization: OptimizationEngine | None = None,
        processes: ProcessEngine | None = None,
    ) -> None:
        self.automation = automation or AutomationEngine()
        self.approval = approval or ApprovalEngine()
        self.compliance = compliance or ComplianceEngine()
        self.departments = departments or DepartmentManager()
        self.forecast = forecast or ForecastEngine()
        self.optimization = optimization or OptimizationEngine()
        self.processes = processes or ProcessEngine()
        self._alerts: dict[str, BusinessAlert] = []
        self._growth: dict[str, GrowthMetric] = {}

    def snapshot(self) -> CompanySnapshot:
        comp_report = self.compliance.generate_report()
        return CompanySnapshot(
            id=_new_id("snap"),
            total_revenue=0.0,
            total_expenses=0.0,
            net_profit=0.0,
            active_automations=len(self.automation.list(enabled_only=True)),
            active_processes=len(self.processes.list_processes(status="active")),
            department_count=self.departments.count(),
            employee_count=self.departments.employee_count(),
            pending_approvals=len(self.approval.pending()),
            open_risks=self.compliance.open_risk_count(),
            compliance_status=comp_report.status,
        )

    def add_alert(
        self, severity: str, title: str, message: str, source: str = ""
    ) -> BusinessAlert:
        a = BusinessAlert(
            id=_new_id("alert"),
            severity=severity,
            title=title,
            message=message,
            source=source,
        )
        self._alerts.append(a)
        return a

    def alerts(self, unacknowledged_only: bool = False) -> list[BusinessAlert]:
        if unacknowledged_only:
            return [a for a in self._alerts if not a.acknowledged]
        return list(self._alerts)

    def acknowledge_alert(self, index: int) -> BusinessAlert | None:
        if 0 <= index < len(self._alerts):
            a = self._alerts[index]
            import dataclasses

            updated = dataclasses.replace(a, acknowledged=True)
            self._alerts[index] = updated
            return updated
        return None

    def record_growth(
        self, name: str, current: float, previous: float, period: str = ""
    ) -> GrowthMetric:
        rate = (
            ((current - previous) / max(abs(previous), 1.0)) * 100
            if previous != 0
            else 0.0
        )
        g = GrowthMetric(
            id=_new_id("growth"),
            name=name,
            current=current,
            previous=previous,
            growth_rate=round(rate, 2),
            period=period,
        )
        self._growth[g.id] = g
        return g

    def growth_metrics(self) -> list[GrowthMetric]:
        return list(self._growth.values())

    def summary(self) -> dict[str, Any]:
        snap = self.snapshot()
        return {
            "active_automations": snap.active_automations,
            "active_processes": snap.active_processes,
            "departments": snap.department_count,
            "employees": snap.employee_count,
            "pending_approvals": snap.pending_approvals,
            "open_risks": snap.open_risks,
            "compliance": snap.compliance_status,
            "alerts": len(self.alerts()),
            "growth_metrics": len(self._growth),
        }


__all__ = ["EnterpriseDashboard"]
