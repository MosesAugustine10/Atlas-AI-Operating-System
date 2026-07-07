"""Atlas Business Operating System (BOS) data models.

Frozen dataclasses and enums for the entire BOS layer. This module
is a *leaf* in the dependency graph — no imports from any Atlas
subsystem.
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


def _new_id(prefix: str = "biz") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


# ===========================================================================
# Enums
# ===========================================================================


class CustomerStatus(enum.StrEnum):
    LEAD = "lead"
    PROSPECT = "prospect"
    ACTIVE = "active"
    CHURNED = "churned"
    BLOCKED = "blocked"


class LeadSource(enum.StrEnum):
    WEBSITE = "website"
    REFERRAL = "referral"
    SOCIAL = "social"
    COLD_OUTREACH = "cold_outreach"
    EVENT = "event"
    OTHER = "other"


class DealStage(enum.StrEnum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class ProjectStatus(enum.StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MeetingStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Channel(enum.StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    SMS = "sms"
    CHAT = "chat"
    SOCIAL = "social"
    IN_PERSON = "in_person"


class CommunicationDirection(enum.StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TransactionType(enum.StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    REFUND = "refund"
    TRANSFER = "transfer"


class CampaignStatus(enum.StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class SocialPlatform(enum.StrEnum):
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class PostStatus(enum.StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class AutomationTrigger(enum.StrEnum):
    CUSTOMER_CREATED = "customer_created"
    DEAL_STAGE_CHANGED = "deal_stage_changed"
    TASK_COMPLETED = "task_completed"
    INVOICE_OVERDUE = "invoice_overdue"
    CAMPAIGN_COMPLETED = "campaign_completed"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class AutomationAction(enum.StrEnum):
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    UPDATE_DEAL = "update_deal"
    NOTIFY = "notify"
    CALL_WEBHOOK = "call_webhook"
    RUN_WORKFLOW = "run_workflow"


class DecisionStatus(enum.StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    REVERTED = "reverted"


class KPICategory(enum.StrEnum):
    REVENUE = "revenue"
    SALES = "sales"
    MARKETING = "marketing"
    CUSTOMER = "customer"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"


# ===========================================================================
# Core models
# ===========================================================================


@dataclass(frozen=True)
class Customer:
    id: str
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    status: str = CustomerStatus.LEAD.value
    source: str = LeadSource.OTHER.value
    tags: tuple[str, ...] = ()
    notes: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Interaction:
    id: str
    customer_id: str
    channel: str = Channel.EMAIL.value
    direction: str = CommunicationDirection.OUTBOUND.value
    subject: str = ""
    body: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Deal:
    id: str
    customer_id: str
    title: str = ""
    value: float = 0.0
    stage: str = DealStage.LEAD.value
    probability: float = 0.0
    expected_close: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Project:
    id: str
    name: str = ""
    description: str = ""
    status: str = ProjectStatus.PLANNED.value
    customer_id: str = ""
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget: float = 0.0
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Task:
    id: str
    project_id: str = ""
    title: str = ""
    description: str = ""
    status: str = TaskStatus.PENDING.value
    priority: str = TaskPriority.NORMAL.value
    assignee: str = ""
    due_date: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str = ""
    description: str = ""
    start: datetime = field(default_factory=_utcnow)
    end: datetime = field(default_factory=_utcnow)
    location: str = ""
    attendees: tuple[str, ...] = ()
    project_id: str = ""
    customer_id: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Meeting:
    id: str
    title: str = ""
    customer_id: str = ""
    project_id: str = ""
    status: str = MeetingStatus.SCHEDULED.value
    start: datetime = field(default_factory=_utcnow)
    end: datetime = field(default_factory=_utcnow)
    location: str = ""
    attendees: tuple[str, ...] = ()
    agenda: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Communication:
    id: str
    customer_id: str = ""
    channel: str = Channel.EMAIL.value
    direction: str = CommunicationDirection.OUTBOUND.value
    subject: str = ""
    body: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Transaction:
    id: str
    type: str = TransactionType.INCOME.value
    amount: float = 0.0
    currency: str = "USD"
    description: str = ""
    customer_id: str = ""
    project_id: str = ""
    date: datetime = field(default_factory=_utcnow)
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Invoice:
    id: str
    customer_id: str
    project_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    status: str = "draft"
    issue_date: datetime = field(default_factory=_utcnow)
    due_date: datetime = field(default_factory=_utcnow)
    paid_date: datetime | None = None
    line_items: tuple[tuple[str, float], ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str = ""
    description: str = ""
    status: str = CampaignStatus.DRAFT.value
    budget: float = 0.0
    spent: float = 0.0
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SocialPost:
    id: str
    platform: str = SocialPlatform.TWITTER.value
    content: str = ""
    status: str = PostStatus.DRAFT.value
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    campaign_id: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SEOResult:
    id: str
    url: str = ""
    score: float = 0.0
    title: str = ""
    meta_description: str = ""
    headings: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class KPI:
    id: str
    name: str = ""
    category: str = KPICategory.OPERATIONAL.value
    value: float = 0.0
    target: float = 0.0
    unit: str = ""
    period: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def achievement_rate(self) -> float:
        if self.target == 0:
            return 0.0
        return min(1.0, self.value / self.target)


@dataclass(frozen=True)
class AutomationRule:
    id: str
    name: str = ""
    trigger: str = AutomationTrigger.MANUAL.value
    conditions: tuple[tuple[str, str], ...] = ()
    action: str = AutomationAction.NOTIFY.value
    action_params: tuple[tuple[str, str], ...] = ()
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    last_fired: datetime | None = None
    fire_count: int = 0
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Decision:
    id: str
    title: str = ""
    description: str = ""
    status: str = DecisionStatus.PROPOSED.value
    reasoning: str = ""
    alternatives: tuple[str, ...] = ()
    impact: str = ""
    decided_by: str = ""
    decided_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RevenueSnapshot:
    id: str
    period: str = ""
    total_revenue: float = 0.0
    total_expenses: float = 0.0
    net_profit: float = 0.0
    deals_won: int = 0
    deals_lost: int = 0
    new_customers: int = 0
    churned_customers: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class BusinessDashboard:
    id: str
    generated_at: datetime = field(default_factory=_utcnow)
    total_customers: int = 0
    active_customers: int = 0
    total_deals: int = 0
    open_deals_value: float = 0.0
    won_deals_value: float = 0.0
    active_projects: int = 0
    upcoming_meetings: int = 0
    total_revenue: float = 0.0
    total_expenses: float = 0.0
    net_profit: float = 0.0
    active_campaigns: int = 0
    scheduled_posts: int = 0
    pending_tasks: int = 0
    kpis: tuple[KPI, ...] = ()
    recent_decisions: tuple[Decision, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


# Callback type aliases
ThinkFn = Callable[..., Any]
GenerateFn = Callable[..., Any]
NotifyFn = Callable[..., Any]


__all__ = [
    "AutomationAction",
    "AutomationRule",
    "AutomationTrigger",
    "BusinessDashboard",
    "CalendarEvent",
    "Campaign",
    "CampaignStatus",
    "Channel",
    "Communication",
    "CommunicationDirection",
    "Customer",
    "CustomerStatus",
    "Deal",
    "DealStage",
    "Decision",
    "DecisionStatus",
    "GenerateFn",
    "Interaction",
    "Invoice",
    "KPICategory",
    "KPI",
    "LeadSource",
    "Meeting",
    "MeetingStatus",
    "NotifyFn",
    "PostStatus",
    "Project",
    "ProjectStatus",
    "RevenueSnapshot",
    "SEOResult",
    "SocialPlatform",
    "SocialPost",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "ThinkFn",
    "Transaction",
    "TransactionType",
    "_new_id",
    "_utcnow",
]
