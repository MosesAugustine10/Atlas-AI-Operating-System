"""Tests for the Atlas Business Operating System.

Covers all 17 modules: customers, crm, sales, projects, calendar,
meetings, communications, finance, marketing, social, seo, analytics,
automation, decision, revenue, dashboard, orchestrator.
"""

from __future__ import annotations

from atlas.business import (
    AnalyticsManager,
    AutomationManager,
    BusinessOrchestrator,
    CalendarManager,
    CommunicationManager,
    CRMManager,
    CustomerManager,
    DashboardManager,
    DecisionManager,
    FinanceManager,
    MarketingManager,
    MeetingManager,
    ProjectManager,
    RevenueManager,
    SalesManager,
    SEOManager,
    SocialManager,
    __version__,
)
from atlas.business.models import (
    AutomationAction,
    AutomationTrigger,
    CampaignStatus,
    Channel,
    CustomerStatus,
    DealStage,
    DecisionStatus,
    KPICategory,
    MeetingStatus,
    PostStatus,
    ProjectStatus,
    SocialPlatform,
    TaskStatus,
    TransactionType,
)


class TestPackage:
    def test_version(self) -> None:
        assert __version__ == "1.0.0"


class TestEnums:
    def test_customer_status(self) -> None:
        assert len(list(CustomerStatus)) == 5

    def test_deal_stage(self) -> None:
        assert len(list(DealStage)) == 6

    def test_project_status(self) -> None:
        assert len(list(ProjectStatus)) == 5

    def test_channel(self) -> None:
        assert len(list(Channel)) == 6

    def test_transaction_type(self) -> None:
        assert len(list(TransactionType)) == 4

    def test_social_platform(self) -> None:
        assert len(list(SocialPlatform)) == 6

    def test_automation_trigger(self) -> None:
        assert len(list(AutomationTrigger)) == 7

    def test_automation_action(self) -> None:
        assert len(list(AutomationAction)) == 6

    def test_decision_status(self) -> None:
        assert len(list(DecisionStatus)) == 5

    def test_kpi_category(self) -> None:
        assert len(list(KPICategory)) == 6


class TestCustomerManager:
    def test_create(self) -> None:
        m = CustomerManager()
        c = m.create("Alice")
        assert c.name == "Alice"
        assert m.count() == 1

    def test_get(self) -> None:
        m = CustomerManager()
        c = m.create("Alice")
        assert m.get(c.id) is c

    def test_list(self) -> None:
        m = CustomerManager()
        m.create("A")
        m.create("B")
        assert len(m.list()) == 2

    def test_list_by_status(self) -> None:
        m = CustomerManager()
        m.create("A", status=CustomerStatus.LEAD.value)
        m.create("B", status=CustomerStatus.ACTIVE.value)
        assert len(m.list(status=CustomerStatus.LEAD.value)) == 1

    def test_update(self) -> None:
        m = CustomerManager()
        c = m.create("A")
        m.update(c.id, email="a@b.com")
        assert m.get(c.id).email == "a@b.com"

    def test_delete(self) -> None:
        m = CustomerManager()
        c = m.create("A")
        assert m.delete(c.id) is True

    def test_add_tag(self) -> None:
        m = CustomerManager()
        c = m.create("A")
        m.add_tag(c.id, "vip")
        assert "vip" in m.get(c.id).tags

    def test_search(self) -> None:
        m = CustomerManager()
        m.create("Alice", email="alice@test.com")
        m.create("Bob", email="bob@test.com")
        assert len(m.search("alice")) == 1

    def test_count_by_status(self) -> None:
        m = CustomerManager()
        m.create("A", status=CustomerStatus.LEAD.value)
        m.create("B", status=CustomerStatus.ACTIVE.value)
        counts = m.count_by_status()
        assert counts[CustomerStatus.LEAD.value] == 1


class TestCRMManager:
    def test_log_interaction(self) -> None:
        crm = CRMManager()
        i = crm.log_interaction("c1", subject="Hello")
        assert i.subject == "Hello"
        assert crm.interaction_count() == 1

    def test_interactions_for(self) -> None:
        crm = CRMManager()
        crm.log_interaction("c1")
        crm.log_interaction("c1")
        crm.log_interaction("c2")
        assert len(crm.interactions_for("c1")) == 2

    def test_advance_stage(self) -> None:
        crm = CRMManager()
        c = crm.customers.create("A")
        new = crm.advance_stage(c.id)
        assert new == CustomerStatus.PROSPECT.value

    def test_churn(self) -> None:
        crm = CRMManager()
        c = crm.customers.create("A")
        result = crm.churn(c.id)
        assert result == CustomerStatus.CHURNED.value

    def test_count_by_channel(self) -> None:
        crm = CRMManager()
        crm.log_interaction("c1", channel=Channel.EMAIL.value)
        crm.log_interaction("c2", channel=Channel.PHONE.value)
        counts = crm.count_by_channel()
        assert counts[Channel.EMAIL.value] == 1


class TestSalesManager:
    def test_create(self) -> None:
        s = SalesManager()
        d = s.create("c1", "Deal 1", value=10000)
        assert d.value == 10000

    def test_advance(self) -> None:
        s = SalesManager()
        d = s.create("c1")
        s.advance(d.id)
        assert s.get(d.id).stage == DealStage.QUALIFIED.value

    def test_lose(self) -> None:
        s = SalesManager()
        d = s.create("c1")
        s.lose(d.id)
        assert s.get(d.id).stage == DealStage.CLOSED_LOST.value

    def test_pipeline_value(self) -> None:
        s = SalesManager()
        s.create("c1", value=10000)
        s.create("c2", value=20000, stage=DealStage.CLOSED_WON.value)
        assert s.pipeline_value() == 10000

    def test_won_value(self) -> None:
        s = SalesManager()
        s.create("c1", value=10000, stage=DealStage.CLOSED_WON.value)
        assert s.won_value() == 10000

    def test_win_rate(self) -> None:
        s = SalesManager()
        s.create("c1", stage=DealStage.CLOSED_WON.value)
        s.create("c2", stage=DealStage.CLOSED_LOST.value)
        assert s.win_rate() == 0.5

    def test_count_by_stage(self) -> None:
        s = SalesManager()
        s.create("c1")
        s.create("c2", stage=DealStage.QUALIFIED.value)
        counts = s.count_by_stage()
        assert counts[DealStage.LEAD.value] == 1


class TestProjectManager:
    def test_create(self) -> None:
        pm = ProjectManager()
        p = pm.create("Project A")
        assert p.name == "Project A"

    def test_create_task(self) -> None:
        pm = ProjectManager()
        p = pm.create("P")
        t = pm.create_task(p.id, "Task 1")
        assert t.title == "Task 1"

    def test_complete_task(self) -> None:
        pm = ProjectManager()
        p = pm.create("P")
        t = pm.create_task(p.id, "T")
        pm.complete_task(t.id)
        assert pm.get_task(t.id).status == TaskStatus.COMPLETED.value

    def test_pending_count(self) -> None:
        pm = ProjectManager()
        p = pm.create("P")
        pm.create_task(p.id, "T1")
        pm.create_task(p.id, "T2")
        assert pm.pending_task_count() == 2

    def test_list_by_status(self) -> None:
        pm = ProjectManager()
        p = (
            pm.create("A", status=ProjectStatus.ACTIVE.value)
            if False
            else pm.create("A")
        )
        pm.update(p.id, status=ProjectStatus.ACTIVE.value)
        pm.create("B")
        assert len(pm.list(status=ProjectStatus.ACTIVE.value)) == 1


class TestCalendarManager:
    def test_create(self) -> None:
        cm = CalendarManager()
        e = cm.create("Meeting")
        assert e.title == "Meeting"

    def test_upcoming(self) -> None:
        from datetime import UTC, datetime, timedelta

        cm = CalendarManager()
        future = datetime.now(UTC) + timedelta(hours=1)
        cm.create("A", start=future, end=future)
        assert len(cm.upcoming()) >= 1

    def test_in_range(self) -> None:
        from datetime import UTC, datetime, timedelta

        cm = CalendarManager()
        now = datetime.now(UTC)
        cm.create("A", start=now, end=now)
        assert len(cm.in_range(now - timedelta(hours=1), now + timedelta(hours=1))) >= 1

    def test_count(self) -> None:
        cm = CalendarManager()
        cm.create("A")
        assert cm.count() == 1


class TestMeetingManager:
    def test_create(self) -> None:
        mm = MeetingManager()
        m = mm.create("Sync")
        assert m.title == "Sync"

    def test_start(self) -> None:
        mm = MeetingManager()
        m = mm.create("M")
        mm.start_meeting(m.id)
        assert mm.get(m.id).status == MeetingStatus.IN_PROGRESS.value

    def test_complete(self) -> None:
        mm = MeetingManager()
        m = mm.create("M")
        mm.complete(m.id, notes="Done")
        assert mm.get(m.id).status == MeetingStatus.COMPLETED.value
        assert mm.get(m.id).notes == "Done"

    def test_cancel(self) -> None:
        mm = MeetingManager()
        m = mm.create("M")
        mm.cancel(m.id)
        assert mm.get(m.id).status == MeetingStatus.CANCELLED.value

    def test_upcoming(self) -> None:
        from datetime import UTC, datetime, timedelta

        mm = MeetingManager()
        future = datetime.now(UTC) + timedelta(hours=1)
        mm.create("M", start=future, end=future)
        assert len(mm.upcoming()) >= 1

    def test_count_by_status(self) -> None:
        mm = MeetingManager()
        mm.create("A")
        mm.create("B")
        counts = mm.count_by_status()
        assert counts[MeetingStatus.SCHEDULED.value] == 2


class TestCommunicationManager:
    def test_log(self) -> None:
        cm = CommunicationManager()
        c = cm.log(customer_id="c1", subject="Hello")
        assert c.subject == "Hello"

    def test_list_by_channel(self) -> None:
        cm = CommunicationManager()
        cm.log(channel=Channel.EMAIL.value)
        cm.log(channel=Channel.PHONE.value)
        assert len(cm.list(channel=Channel.EMAIL.value)) == 1

    def test_search(self) -> None:
        cm = CommunicationManager()
        cm.log(subject="Hello world")
        assert len(cm.search("hello")) == 1

    def test_for_customer(self) -> None:
        cm = CommunicationManager()
        cm.log(customer_id="c1")
        cm.log(customer_id="c2")
        assert len(cm.for_customer("c1")) == 1

    def test_count_by_channel(self) -> None:
        cm = CommunicationManager()
        cm.log(channel=Channel.EMAIL.value)
        cm.log(channel=Channel.EMAIL.value)
        counts = cm.count_by_channel()
        assert counts[Channel.EMAIL.value] == 2


class TestFinanceManager:
    def test_add_transaction(self) -> None:
        fm = FinanceManager()
        fm.add_transaction(TransactionType.INCOME.value, 10000)
        assert fm.total_income() == 10000

    def test_net_profit(self) -> None:
        fm = FinanceManager()
        fm.add_transaction(TransactionType.INCOME.value, 10000)
        fm.add_transaction(TransactionType.EXPENSE.value, 3000)
        assert fm.net_profit() == 7000

    def test_create_invoice(self) -> None:
        fm = FinanceManager()
        inv = fm.create_invoice("c1", amount=5000)
        assert inv.amount == 5000

    def test_pay_invoice(self) -> None:
        fm = FinanceManager()
        inv = fm.create_invoice("c1", amount=5000)
        fm.pay_invoice(inv.id)
        assert fm.get_invoice(inv.id).status == "paid"
        assert fm.total_income() == 5000

    def test_overdue(self) -> None:
        from datetime import UTC, datetime, timedelta

        fm = FinanceManager()
        past = datetime.now(UTC) - timedelta(days=10)
        fm.create_invoice("c1", amount=1000, due_date=past)
        assert len(fm.overdue_invoices()) == 1


class TestMarketingManager:
    def test_create(self) -> None:
        mm = MarketingManager()
        c = mm.create("Campaign A")
        assert c.name == "Campaign A"

    def test_activate(self) -> None:
        mm = MarketingManager()
        c = mm.create("A")
        mm.activate(c.id)
        assert mm.get(c.id).status == CampaignStatus.ACTIVE.value

    def test_add_spend(self) -> None:
        mm = MarketingManager()
        c = mm.create("A", budget=1000)
        mm.add_spend(c.id, 200)
        assert mm.get(c.id).spent == 200

    def test_active_campaigns(self) -> None:
        mm = MarketingManager()
        c = mm.create("A")
        mm.activate(c.id)
        assert len(mm.active_campaigns()) == 1

    def test_total_budget(self) -> None:
        mm = MarketingManager()
        mm.create("A", budget=1000)
        mm.create("B", budget=2000)
        assert mm.total_budget() == 3000


class TestSocialManager:
    def test_create(self) -> None:
        sm = SocialManager()
        p = sm.create(content="Hello world")
        assert p.content == "Hello world"

    def test_schedule(self) -> None:
        from datetime import UTC, datetime

        sm = SocialManager()
        p = sm.create("test")
        when = datetime.now(UTC)
        sm.schedule(p.id, when)
        assert sm.get(p.id).status == PostStatus.SCHEDULED.value

    def test_publish(self) -> None:
        sm = SocialManager()
        p = sm.create("test")
        sm.publish(p.id)
        assert sm.get(p.id).status == PostStatus.PUBLISHED.value

    def test_published_count(self) -> None:
        sm = SocialManager()
        p = sm.create("test")
        sm.publish(p.id)
        assert sm.published_count() == 1

    def test_count_by_platform(self) -> None:
        sm = SocialManager()
        sm.create(platform=SocialPlatform.TWITTER.value)
        sm.create(platform=SocialPlatform.LINKEDIN.value)
        counts = sm.count_by_platform()
        assert counts[SocialPlatform.TWITTER.value] == 1


class TestSEOManager:
    def test_analyze(self) -> None:
        s = SEOManager()
        r = s.analyze("https://example.com")
        assert r.url == "https://example.com"
        assert 0 <= r.score <= 100

    def test_average_score(self) -> None:
        s = SEOManager()
        s.analyze("https://a.com")
        s.analyze("https://b.com")
        assert s.average_score() > 0

    def test_best_score(self) -> None:
        s = SEOManager()
        s.analyze("https://a.com")
        s.analyze("https://b.com")
        assert s.best_score() > 0

    def test_count(self) -> None:
        s = SEOManager()
        s.analyze("https://a.com")
        assert s.count() == 1

    def test_with_custom_fn(self) -> None:
        def custom(**kw: object) -> object:
            from atlas.business.models import SEOResult, _new_id

            return SEOResult(id=_new_id("seo"), url=str(kw.get("url", "")), score=95.0)

        s = SEOManager(analyze_fn=custom)
        r = s.analyze("https://test.com")
        assert r.score == 95.0


class TestAnalyticsManager:
    def test_record(self) -> None:
        am = AnalyticsManager()
        k = am.record(
            "Revenue", value=10000, target=15000, category=KPICategory.REVENUE.value
        )
        assert k.value == 10000

    def test_achievement_rate(self) -> None:
        am = AnalyticsManager()
        k = am.record("Revenue", value=7500, target=10000)
        assert k.achievement_rate == 0.75

    def test_top_kpis(self) -> None:
        am = AnalyticsManager()
        am.record("A", value=90, target=100)
        am.record("B", value=50, target=100)
        top = am.top_kpis(limit=1)
        assert top[0].name == "A"

    def test_underperforming(self) -> None:
        am = AnalyticsManager()
        am.record("Good", value=90, target=100)
        am.record("Bad", value=10, target=100)
        assert len(am.underperforming()) == 1

    def test_count_by_category(self) -> None:
        am = AnalyticsManager()
        am.record("A", category=KPICategory.REVENUE.value)
        am.record("B", category=KPICategory.SALES.value)
        counts = am.count_by_category()
        assert counts[KPICategory.REVENUE.value] == 1

    def test_average_achievement(self) -> None:
        am = AnalyticsManager()
        am.record("A", value=80, target=100)
        am.record("B", value=60, target=100)
        assert abs(am.average_achievement() - 0.7) < 0.01


class TestAutomationManager:
    def test_create(self) -> None:
        am = AutomationManager()
        r = am.create("Rule 1")
        assert r.name == "Rule 1"

    def test_fire(self) -> None:
        am = AutomationManager()
        r = am.create("R", action=AutomationAction.NOTIFY.value)
        result = am.fire(r.id)
        assert result["fired"] is True

    def test_fire_disabled(self) -> None:
        am = AutomationManager()
        r = am.create("R")
        am.disable(r.id)
        result = am.fire(r.id)
        assert result["fired"] is False

    def test_fire_with_conditions(self) -> None:
        am = AutomationManager()
        r = am.create("R", conditions=(("status", "urgent"),))
        result = am.fire(r.id, context={"status": "normal"})
        assert result["fired"] is False
        result = am.fire(r.id, context={"status": "urgent"})
        assert result["fired"] is True

    def test_fire_by_trigger(self) -> None:
        am = AutomationManager()
        am.create("R1", trigger=AutomationTrigger.CUSTOMER_CREATED.value)
        am.create("R2", trigger=AutomationTrigger.CUSTOMER_CREATED.value)
        am.create("R3", trigger=AutomationTrigger.MANUAL.value)
        results = am.fire_by_trigger(AutomationTrigger.CUSTOMER_CREATED.value)
        assert len(results) == 2

    def test_execution_log(self) -> None:
        am = AutomationManager()
        r = am.create("R")
        am.fire(r.id)
        assert len(am.execution_log()) == 1

    def test_enabled_count(self) -> None:
        am = AutomationManager()
        am.create("A")
        am.create("B")
        am.disable("B")  # This won't work — need the id
        # Fix: get id first
        r2 = am.create("C")
        am.disable(r2.id)
        assert am.enabled_count() == 2

    def test_with_execute_fn(self) -> None:
        calls: list[str] = []
        am = AutomationManager(
            execute_fn=lambda **kw: calls.append(str(kw.get("action", "")))
        )
        r = am.create("R")
        am.fire(r.id)
        assert len(calls) == 1


class TestDecisionManager:
    def test_propose(self) -> None:
        dm = DecisionManager()
        d = dm.propose("Hire", reasoning="Need more capacity")
        assert d.status == DecisionStatus.PROPOSED.value

    def test_approve(self) -> None:
        dm = DecisionManager()
        d = dm.propose("A")
        dm.approve(d.id, decided_by="CEO")
        assert dm.get(d.id).status == DecisionStatus.APPROVED.value

    def test_reject(self) -> None:
        dm = DecisionManager()
        d = dm.propose("A")
        dm.reject(d.id)
        assert dm.get(d.id).status == DecisionStatus.REJECTED.value

    def test_execute(self) -> None:
        dm = DecisionManager()
        d = dm.propose("A")
        dm.approve(d.id)
        dm.execute(d.id)
        assert dm.get(d.id).status == DecisionStatus.EXECUTED.value

    def test_execute_without_approval(self) -> None:
        dm = DecisionManager()
        d = dm.propose("A")
        result = dm.execute(d.id)
        assert result is None

    def test_revert(self) -> None:
        dm = DecisionManager()
        d = dm.propose("A")
        dm.approve(d.id)
        dm.execute(d.id)
        dm.revert(d.id)
        assert dm.get(d.id).status == DecisionStatus.REVERTED.value

    def test_pending(self) -> None:
        dm = DecisionManager()
        dm.propose("A")
        dm.propose("B")
        assert len(dm.pending()) == 2

    def test_count_by_status(self) -> None:
        dm = DecisionManager()
        d = dm.propose("A")
        dm.approve(d.id)
        counts = dm.count_by_status()
        assert counts[DecisionStatus.APPROVED.value] == 1


class TestRevenueManager:
    def test_snapshot(self) -> None:
        rm = RevenueManager()
        rm.finance.add_transaction(TransactionType.INCOME.value, 10000)
        snap = rm.snapshot("Q1")
        assert snap.total_revenue == 10000
        assert snap.net_profit == 10000

    def test_latest(self) -> None:
        rm = RevenueManager()
        rm.snapshot("Q1")
        rm.snapshot("Q2")
        assert rm.latest() is not None

    def test_count(self) -> None:
        rm = RevenueManager()
        rm.snapshot("Q1")
        assert rm.count() == 1


class TestDashboardManager:
    def test_generate(self) -> None:
        dm = DashboardManager()
        dm.customers.create("A")
        dm.finance.add_transaction(TransactionType.INCOME.value, 5000)
        dash = dm.generate()
        assert dash.total_customers == 1
        assert dash.total_revenue == 5000

    def test_summary(self) -> None:
        dm = DashboardManager()
        dm.customers.create("A", status=CustomerStatus.ACTIVE.value)
        s = dm.summary()
        assert s["total_customers"] == 1
        assert s["active_customers"] == 1


class TestOrchestrator:
    def test_construct(self) -> None:
        bo = BusinessOrchestrator()
        assert bo is not None

    def test_all_managers_present(self) -> None:
        bo = BusinessOrchestrator()
        assert bo.customers is not None
        assert bo.crm is not None
        assert bo.sales is not None
        assert bo.projects is not None
        assert bo.calendar is not None
        assert bo.meetings is not None
        assert bo.communications is not None
        assert bo.finance is not None
        assert bo.marketing is not None
        assert bo.social is not None
        assert bo.seo is not None
        assert bo.analytics is not None
        assert bo.automation is not None
        assert bo.decisions is not None
        assert bo.revenue is not None
        assert bo.dashboard is not None

    def test_status(self) -> None:
        bo = BusinessOrchestrator()
        s = bo.status()
        assert "customers" in s
        assert "deals" in s
        assert "projects" in s

    def test_full_scenario(self) -> None:
        bo = BusinessOrchestrator()
        c = bo.customers.create("Alice", email="alice@test.com")
        bo.crm.log_interaction(c.id, subject="First contact")
        deal = bo.sales.create(c.id, "Deal 1", value=10000)
        bo.sales.advance(deal.id)
        p = bo.projects.create("Project A", customer_id=c.id)
        bo.projects.create_task(p.id, "Setup")
        bo.finance.add_transaction(TransactionType.INCOME.value, 5000, customer_id=c.id)
        snap = bo.revenue.snapshot("Q1")
        dash = bo.dashboard.generate()
        assert dash.total_customers == 1
        assert dash.total_revenue == 5000
        assert snap.total_revenue == 5000


class TestNoSubsystemImports:
    def test_business_does_not_import_subsystems(self) -> None:
        import os
        import re

        import atlas.business

        root = os.path.dirname(atlas.business.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|providers|mcp|memory|knowledge|workflows|tools|integration|agents|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline|workforce|collaboration|creator_pipeline|evaluation)\b"
        )
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path) as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert (
            not offenders
        ), "atlas.business imports other Atlas subsystems:\n" + "\n".join(offenders)
