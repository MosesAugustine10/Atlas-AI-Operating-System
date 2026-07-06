"""Enterprise orchestrator — top-level facade coordinating all enterprise subsystems."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.enterprise.approval import ApprovalEngine
from atlas.enterprise.automation import AutomationEngine
from atlas.enterprise.compliance import ComplianceEngine
from atlas.enterprise.dashboard import EnterpriseDashboard
from atlas.enterprise.departments import DepartmentManager
from atlas.enterprise.forecast import ForecastEngine
from atlas.enterprise.optimization import OptimizationEngine
from atlas.enterprise.processes import ProcessEngine
from atlas.enterprise.rules import RulesEngine


class EnterpriseOrchestrator:
    """Top-level facade for the Atlas Enterprise Automation Platform.

    All parameters are optional — sensible defaults are created.
    Injected callbacks wire the platform to real Atlas subsystems.
    """

    def __init__(
        self,
        think_fn: Callable[..., Any] | None = None,
        execute_fn: Callable[..., Any] | None = None,
        forecast_fn: Callable[..., Any] | None = None,
        optimize_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.automation = AutomationEngine(execute_fn=execute_fn)
        self.processes = ProcessEngine()
        self.rules = RulesEngine()
        self.approval = ApprovalEngine()
        self.forecast = ForecastEngine(forecast_fn=forecast_fn)
        self.optimization = OptimizationEngine(optimize_fn=optimize_fn)
        self.compliance = ComplianceEngine()
        self.departments = DepartmentManager()
        self.dashboard = EnterpriseDashboard(
            automation=self.automation,
            approval=self.approval,
            compliance=self.compliance,
            departments=self.departments,
            forecast=self.forecast,
            optimization=self.optimization,
            processes=self.processes,
        )
        self._think_fn = think_fn
        self._execute_fn = execute_fn

    def initialize(self) -> None:
        """Initialize built-in departments."""
        self.departments.load_builtins()

    def status(self) -> dict[str, Any]:
        return {
            "automations": len(self.automation.list()),
            "processes": self.processes.count(),
            "rules": self.rules.count(),
            "approvals": self.approval.count(),
            "forecasts": self.forecast.count(),
            "optimizations": self.optimization.count(),
            "policies": self.compliance.policy_count(),
            "audits": self.compliance.audit_count(),
            "risks": self.compliance.open_risk_count(),
            "departments": self.departments.count(),
            "employees": self.departments.employee_count(),
        }


__all__ = ["EnterpriseOrchestrator"]
