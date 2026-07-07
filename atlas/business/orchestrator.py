"""Business Operating System orchestrator — top-level facade."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.business.analytics import AnalyticsManager
from atlas.business.automation import AutomationManager
from atlas.business.calendar import CalendarManager
from atlas.business.communications import CommunicationManager
from atlas.business.crm import CRMManager
from atlas.business.customers import CustomerManager
from atlas.business.dashboard import DashboardManager
from atlas.business.decision import DecisionManager
from atlas.business.finance import FinanceManager
from atlas.business.marketing import MarketingManager
from atlas.business.meetings import MeetingManager
from atlas.business.projects import ProjectManager
from atlas.business.revenue import RevenueManager
from atlas.business.sales import SalesManager
from atlas.business.seo import SEOManager
from atlas.business.social import SocialManager


class BusinessOrchestrator:
    """Top-level facade for the Atlas Business Operating System.

    All parameters are optional — sensible defaults are created.
    Injected callbacks wire BOS to real Atlas subsystems.
    """

    def __init__(
        self,
        think_fn: Callable[..., Any] | None = None,
        generate_fn: Callable[..., Any] | None = None,
        notify_fn: Callable[..., Any] | None = None,
        analyze_fn: Callable[..., Any] | None = None,
        automate_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.customers = CustomerManager()
        self.crm = CRMManager(customers=self.customers)
        self.sales = SalesManager()
        self.projects = ProjectManager()
        self.calendar = CalendarManager()
        self.meetings = MeetingManager()
        self.communications = CommunicationManager()
        self.finance = FinanceManager()
        self.marketing = MarketingManager()
        self.social = SocialManager()
        self.seo = SEOManager(analyze_fn=analyze_fn)
        self.analytics = AnalyticsManager()
        self.automation = AutomationManager(execute_fn=automate_fn)
        self.decisions = DecisionManager()
        self.revenue = RevenueManager(
            finance=self.finance, sales=self.sales, customers=self.customers
        )
        self.dashboard = DashboardManager(
            customers=self.customers,
            sales=self.sales,
            projects=self.projects,
            meetings=self.meetings,
            finance=self.finance,
            marketing=self.marketing,
            social=self.social,
            analytics=self.analytics,
            decisions=self.decisions,
        )
        self._think_fn = think_fn
        self._generate_fn = generate_fn
        self._notify_fn = notify_fn

    def status(self) -> dict[str, Any]:
        return {
            "customers": self.customers.count(),
            "deals": self.sales.count(),
            "projects": len(self.projects.list()),
            "meetings": self.meetings.count(),
            "transactions": self.finance.transaction_count(),
            "campaigns": self.marketing.count(),
            "posts": self.social.count(),
            "kpis": self.analytics.count(),
            "rules": self.automation.count(),
            "decisions": self.decisions.count(),
            "revenue_snapshots": self.revenue.count(),
        }


__all__ = ["BusinessOrchestrator"]
