"""Atlas Enterprise Automation Platform.

Sits ABOVE all existing Atlas subsystems. Runs an entire company
automatically through automation, processes, rules, approvals,
forecasts, optimization, compliance, and department management.

All subsystems use dependency injection. No Atlas subsystem is
imported directly — callbacks are injected.
"""

from __future__ import annotations

__version__ = "1.0.0"

from atlas.enterprise.approval import ApprovalEngine
from atlas.enterprise.automation import AutomationEngine
from atlas.enterprise.compliance import ComplianceEngine
from atlas.enterprise.dashboard import EnterpriseDashboard
from atlas.enterprise.departments import DepartmentManager
from atlas.enterprise.forecast import ForecastEngine
from atlas.enterprise.models import *  # noqa: F401, F403
from atlas.enterprise.optimization import OptimizationEngine
from atlas.enterprise.orchestrator import EnterpriseOrchestrator
from atlas.enterprise.processes import ProcessEngine
from atlas.enterprise.rules import RulesEngine

__all__ = [
    "__version__",
    "ApprovalEngine",
    "AutomationEngine",
    "ComplianceEngine",
    "DepartmentManager",
    "EnterpriseDashboard",
    "EnterpriseOrchestrator",
    "ForecastEngine",
    "OptimizationEngine",
    "ProcessEngine",
    "RulesEngine",
]
