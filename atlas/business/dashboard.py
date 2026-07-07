"""Executive dashboard models with health, revenue, projects, agents, providers."""

from __future__ import annotations

from typing import Any

from atlas.business.analytics import AnalyticsManager
from atlas.business.customers import CustomerManager
from atlas.business.decision import DecisionManager
from atlas.business.finance import FinanceManager
from atlas.business.marketing import MarketingManager
from atlas.business.meetings import MeetingManager
from atlas.business.models import (
    BusinessDashboard,
    CustomerStatus,
    ProjectStatus,
    _new_id,
)
from atlas.business.projects import ProjectManager
from atlas.business.sales import SalesManager
from atlas.business.social import SocialManager


class DashboardManager:
    def __init__(
        self,
        customers: CustomerManager | None = None,
        sales: SalesManager | None = None,
        projects: ProjectManager | None = None,
        meetings: MeetingManager | None = None,
        finance: FinanceManager | None = None,
        marketing: MarketingManager | None = None,
        social: SocialManager | None = None,
        analytics: AnalyticsManager | None = None,
        decisions: DecisionManager | None = None,
    ) -> None:
        self.customers = customers or CustomerManager()
        self.sales = sales or SalesManager()
        self.projects = projects or ProjectManager()
        self.meetings = meetings or MeetingManager()
        self.finance = finance or FinanceManager()
        self.marketing = marketing or MarketingManager()
        self.social = social or SocialManager()
        self.analytics = analytics or AnalyticsManager()
        self.decisions = decisions or DecisionManager()

    def generate(self) -> BusinessDashboard:
        customer_counts = self.customers.count_by_status()
        active_customers = customer_counts.get(CustomerStatus.ACTIVE.value, 0)
        total_rev = self.finance.total_income()
        total_exp = self.finance.total_expenses()
        recent_decs = self.decisions.list()[:5]
        return BusinessDashboard(
            id=_new_id("dash"),
            total_customers=self.customers.count(),
            active_customers=active_customers,
            total_deals=self.sales.count(),
            open_deals_value=self.sales.pipeline_value(),
            won_deals_value=self.sales.won_value(),
            active_projects=len(self.projects.list(status=ProjectStatus.ACTIVE.value)),
            upcoming_meetings=len(self.meetings.upcoming()),
            total_revenue=total_rev,
            total_expenses=total_exp,
            net_profit=total_rev - total_exp,
            active_campaigns=len(self.marketing.active_campaigns()),
            scheduled_posts=len(self.social.scheduled_posts()),
            pending_tasks=self.projects.pending_task_count(),
            kpis=tuple(self.analytics.list()),
            recent_decisions=tuple(recent_decs),
        )

    def summary(self) -> dict[str, Any]:
        d = self.generate()
        return {
            "total_customers": d.total_customers,
            "active_customers": d.active_customers,
            "open_deals_value": d.open_deals_value,
            "total_revenue": d.total_revenue,
            "net_profit": d.net_profit,
            "active_projects": d.active_projects,
            "upcoming_meetings": d.upcoming_meetings,
            "active_campaigns": d.active_campaigns,
            "pending_tasks": d.pending_tasks,
        }


__all__ = ["DashboardManager"]
