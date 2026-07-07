"""Atlas Enterprise Automation Platform data models.

Frozen dataclasses and enums for the entire enterprise layer. This
module is a *leaf* in the dependency graph — no imports from any
Atlas subsystem.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str = "ent") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


# ===========================================================================
# Enums
# ===========================================================================


class AutomationStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ScheduleType(enum.StrEnum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"
    EVENT = "event"


class TriggerType(enum.StrEnum):
    CUSTOMER_CREATED = "customer_created"
    DEAL_STAGE_CHANGED = "deal_stage_changed"
    TASK_COMPLETED = "task_completed"
    INVOICE_PAID = "invoice_paid"
    CAMPAIGN_COMPLETED = "campaign_completed"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    THRESHOLD = "threshold"
    WEBHOOK = "webhook"


class ConditionOperator(enum.StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    IN = "in"
    NOT_IN = "not_in"


class LogicalOperator(enum.StrEnum):
    AND = "and"
    OR = "or"
    NOT = "not"


class ActionType(enum.StrEnum):
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    UPDATE_DEAL = "update_deal"
    NOTIFY = "notify"
    CALL_WEBHOOK = "call_webhook"
    RUN_WORKFLOW = "run_workflow"
    CREATE_INVOICE = "create_invoice"
    SCHEDULE_MEETING = "schedule_meeting"
    UPDATE_CUSTOMER = "update_customer"
    RUN_FORECAST = "run_forecast"
    RUN_OPTIMIZATION = "run_optimization"


class ApprovalType(enum.StrEnum):
    MANAGER = "manager"
    CEO = "ceo"
    AUTOMATIC = "automatic"
    MULTI_STAGE = "multi_stage"


class ApprovalDecision(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class DepartmentType(enum.StrEnum):
    CEO = "ceo"
    FINANCE = "finance"
    SALES = "sales"
    MARKETING = "marketing"
    ENGINEERING = "engineering"
    DESIGN = "design"
    MINING = "mining"
    RESEARCH = "research"
    OPERATIONS = "operations"
    LEGAL = "legal"
    HR = "hr"
    SUPPORT = "support"


class ProcessStatus(enum.StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStatus(enum.StrEnum):
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    WARNING = "warning"
    PENDING_REVIEW = "pending_review"


class AlertSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ForecastType(enum.StrEnum):
    REVENUE = "revenue"
    CUSTOMERS = "customers"
    GROWTH = "growth"
    COST = "cost"
    MARKETING = "marketing"
    SALES = "sales"
    PIPELINE = "pipeline"


class OptimizationTarget(enum.StrEnum):
    SCHEDULING = "scheduling"
    COSTS = "costs"
    REVENUE = "revenue"
    MARKETING = "marketing"
    SALES = "sales"
    PROVIDERS = "providers"
    WORKFLOWS = "workflows"
    RESOURCE_ALLOCATION = "resource_allocation"


# ===========================================================================
# Automation models
# ===========================================================================


@dataclass(frozen=True)
class AutomationTrigger:
    id: str
    type: str = TriggerType.MANUAL.value
    params: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AutomationCondition:
    id: str
    field: str = ""
    operator: str = ConditionOperator.EQ.value
    value: str = ""
    logical: str = LogicalOperator.AND.value


@dataclass(frozen=True)
class AutomationAction:
    id: str
    type: str = ActionType.NOTIFY.value
    params: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Automation:
    id: str
    name: str = ""
    description: str = ""
    trigger: AutomationTrigger | None = None
    conditions: tuple[AutomationCondition, ...] = ()
    actions: tuple[AutomationAction, ...] = ()
    enabled: bool = True
    priority: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    last_run: datetime | None = None
    run_count: int = 0
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AutomationRun:
    id: str
    automation_id: str
    status: str = AutomationStatus.PENDING.value
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    trigger_data: tuple[tuple[str, str], ...] = ()
    results: tuple[tuple[str, str], ...] = ()
    error: str = ""


@dataclass(frozen=True)
class AutomationSchedule:
    id: str
    automation_id: str
    type: str = ScheduleType.DAILY.value
    interval: int = 1
    next_run: datetime | None = None
    last_run: datetime | None = None
    enabled: bool = True


@dataclass(frozen=True)
class AutomationStatistics:
    total_automations: int = 0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    average_duration_seconds: float = 0.0
    last_run: datetime | None = None
    most_fired: str = ""


# ===========================================================================
# Business rules
# ===========================================================================


@dataclass(frozen=True)
class BusinessRule:
    id: str
    name: str = ""
    description: str = ""
    conditions: tuple[AutomationCondition, ...] = ()
    actions: tuple[AutomationAction, ...] = ()
    priority: int = 0
    enabled: bool = True
    override_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Approval models
# ===========================================================================


@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    title: str = ""
    description: str = ""
    type: str = ApprovalType.MANAGER.value
    requester: str = ""
    approver: str = ""
    decision: str = ApprovalDecision.PENDING.value
    created_at: datetime = field(default_factory=_utcnow)
    decided_at: datetime | None = None
    timeout_minutes: int = 1440
    reason: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ApprovalResult:
    id: str
    request_id: str
    decision: str = ApprovalDecision.APPROVED.value
    approver: str = ""
    reason: str = ""
    decided_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class Escalation:
    id: str
    request_id: str
    from_level: str = ""
    to_level: str = ""
    reason: str = ""
    escalated_at: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Department models
# ===========================================================================


@dataclass(frozen=True)
class Department:
    id: str
    name: str = ""
    type: str = DepartmentType.OPERATIONS.value
    head: str = ""
    member_ids: tuple[str, ...] = ()
    budget: float = 0.0
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DepartmentMetrics:
    department_id: str
    task_count: int = 0
    completed_tasks: int = 0
    budget_used: float = 0.0
    budget_remaining: float = 0.0
    headcount: int = 0
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class EmployeeProfile:
    id: str
    name: str = ""
    email: str = ""
    department_id: str = ""
    role: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResourcePool:
    id: str
    name: str = ""
    department_id: str = ""
    capacity: int = 0
    allocated: int = 0
    unit: str = "units"
    created_at: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Compliance models
# ===========================================================================


@dataclass(frozen=True)
class CompanyPolicy:
    id: str
    name: str = ""
    description: str = ""
    category: str = "general"
    rules: tuple[str, ...] = ()
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class RiskAssessment:
    id: str
    title: str = ""
    description: str = ""
    level: str = RiskLevel.LOW.value
    mitigation: str = ""
    identified_at: datetime = field(default_factory=_utcnow)
    resolved_at: datetime | None = None


@dataclass(frozen=True)
class ComplianceReport:
    id: str
    status: str = ComplianceStatus.COMPLIANT.value
    violations: int = 0
    warnings: int = 0
    checked_policies: int = 0
    generated_at: datetime = field(default_factory=_utcnow)
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AuditRecord:
    id: str
    action: str = ""
    actor: str = ""
    target: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    details: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Business process models
# ===========================================================================


@dataclass(frozen=True)
class BusinessProcess:
    id: str
    name: str = ""
    description: str = ""
    stages: tuple[str, ...] = ()
    status: str = ProcessStatus.DRAFT.value
    department_id: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Pipeline:
    id: str
    name: str = ""
    process_id: str = ""
    stages: tuple[PipelineStage, ...] = ()
    status: str = ProcessStatus.DRAFT.value
    created_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None


@dataclass(frozen=True)
class PipelineStage:
    id: str
    pipeline_id: str = ""
    name: str = ""
    order: int = 0
    status: str = ProcessStatus.DRAFT.value
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ExecutionWindow:
    id: str
    start: datetime = field(default_factory=_utcnow)
    end: datetime = field(default_factory=_utcnow)
    max_concurrent: int = 1
    timezone: str = "UTC"


# ===========================================================================
# Forecast models
# ===========================================================================


@dataclass(frozen=True)
class Forecast:
    id: str
    type: str = ForecastType.REVENUE.value
    period: str = ""
    horizon_days: int = 30
    method: str = "linear"
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ForecastResult:
    id: str
    forecast_id: str = ""
    predicted_value: float = 0.0
    confidence: float = 0.0
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    data_points: tuple[tuple[str, float], ...] = ()
    created_at: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Optimization models
# ===========================================================================


@dataclass(frozen=True)
class OptimizationTask:
    id: str
    target: str = OptimizationTarget.COSTS.value
    description: str = ""
    current_value: float = 0.0
    target_value: float = 0.0
    status: str = "pending"
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OptimizationResult:
    id: str
    task_id: str = ""
    optimized_value: float = 0.0
    improvement: float = 0.0
    recommendation: str = ""
    created_at: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Dashboard / alert models
# ===========================================================================


@dataclass(frozen=True)
class CompanySnapshot:
    id: str
    generated_at: datetime = field(default_factory=_utcnow)
    total_revenue: float = 0.0
    total_expenses: float = 0.0
    net_profit: float = 0.0
    active_automations: int = 0
    active_processes: int = 0
    department_count: int = 0
    employee_count: int = 0
    pending_approvals: int = 0
    open_risks: int = 0
    compliance_status: str = ComplianceStatus.COMPLIANT.value
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class GrowthMetric:
    id: str
    name: str = ""
    current: float = 0.0
    previous: float = 0.0
    growth_rate: float = 0.0
    period: str = ""
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class BusinessAlert:
    id: str
    severity: str = AlertSeverity.INFO.value
    title: str = ""
    message: str = ""
    source: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    acknowledged: bool = False


@dataclass(frozen=True)
class NotificationRule:
    id: str
    event: str = ""
    recipients: tuple[str, ...] = ()
    channel: str = "email"
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class RecoveryPlan:
    id: str
    alert_id: str = ""
    steps: tuple[str, ...] = ()
    automated: bool = False
    created_at: datetime = field(default_factory=_utcnow)


# Callbacks
ThinkFn = Callable[..., Any]
GenerateFn = Callable[..., Any]
ExecuteFn = Callable[..., Any]


__all__ = [
    "ActionType",
    "AlertSeverity",
    "ApprovalDecision",
    "ApprovalRequest",
    "ApprovalResult",
    "ApprovalType",
    "AuditRecord",
    "Automation",
    "AutomationAction",
    "AutomationCondition",
    "AutomationRun",
    "AutomationSchedule",
    "AutomationStatistics",
    "AutomationStatus",
    "AutomationTrigger",
    "BusinessAlert",
    "BusinessProcess",
    "BusinessRule",
    "CompanyPolicy",
    "CompanySnapshot",
    "ComplianceReport",
    "ComplianceStatus",
    "ConditionOperator",
    "Department",
    "DepartmentMetrics",
    "DepartmentType",
    "EmployeeProfile",
    "Escalation",
    "ExecuteFn",
    "ExecutionWindow",
    "Forecast",
    "ForecastResult",
    "ForecastType",
    "GenerateFn",
    "GrowthMetric",
    "LogicalOperator",
    "NotificationRule",
    "OptimizationResult",
    "OptimizationTarget",
    "OptimizationTask",
    "Pipeline",
    "PipelineStage",
    "ProcessStatus",
    "RecoveryPlan",
    "ResourcePool",
    "RiskAssessment",
    "RiskLevel",
    "ScheduleType",
    "ThinkFn",
    "TriggerType",
    "_new_id",
    "_utcnow",
]
