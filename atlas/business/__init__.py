"""Atlas Business Operating System (BOS).

Transforms Atlas into a complete Business Operating System with
customer/CRM, sales, projects, calendar, meetings, communications,
finance, marketing, social, SEO, analytics, automation, decision
engine, revenue tracking, and executive dashboard.

All subsystems use dependency injection. No Atlas subsystem is
imported directly — callbacks are injected.
"""

from __future__ import annotations

__version__ = "1.0.0"

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
from atlas.business.models import *  # noqa: F401, F403
from atlas.business.orchestrator import BusinessOrchestrator
from atlas.business.projects import ProjectManager
from atlas.business.revenue import RevenueManager
from atlas.business.sales import SalesManager
from atlas.business.seo import SEOManager
from atlas.business.social import SocialManager

__all__ = [
    "__version__",
    "AnalyticsManager",
    "AutomationManager",
    "BusinessOrchestrator",
    "CRMManager",
    "CalendarManager",
    "CommunicationManager",
    "CustomerManager",
    "DashboardManager",
    "DecisionManager",
    "FinanceManager",
    "MarketingManager",
    "MeetingManager",
    "ProjectManager",
    "RevenueManager",
    "SEOManager",
    "SalesManager",
    "SocialManager",
]
