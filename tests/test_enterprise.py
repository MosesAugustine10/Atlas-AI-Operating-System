"""Tests for the Atlas Enterprise Automation Platform."""

from __future__ import annotations

import pytest

from atlas.enterprise import (
    ApprovalEngine,
    AutomationEngine,
    ComplianceEngine,
    DepartmentManager,
    EnterpriseDashboard,
    EnterpriseOrchestrator,
    ForecastEngine,
    OptimizationEngine,
    ProcessEngine,
    RulesEngine,
    __version__,
)
from atlas.enterprise.models import (
    ActionType,
    AlertSeverity,
    ApprovalDecision,
    ApprovalType,
    AutomationCondition,
    AutomationTrigger,
    ConditionOperator,
    DepartmentType,
    ForecastType,
    LogicalOperator,
    OptimizationTarget,
    ProcessStatus,
    RiskLevel,
    TriggerType,
)


class TestPackage:
    def test_version(self) -> None:
        assert __version__ == "1.0.0"


class TestEnums:
    def test_automation_status(self) -> None:
        from atlas.enterprise.models import AutomationStatus

        assert len(list(AutomationStatus)) == 6

    def test_trigger_type(self) -> None:
        assert len(list(TriggerType)) == 9

    def test_condition_operator(self) -> None:
        assert len(list(ConditionOperator)) == 9

    def test_action_type(self) -> None:
        assert len(list(ActionType)) == 11

    def test_approval_type(self) -> None:
        assert len(list(ApprovalType)) == 4

    def test_department_type(self) -> None:
        assert len(list(DepartmentType)) == 12

    def test_risk_level(self) -> None:
        assert len(list(RiskLevel)) == 4

    def test_forecast_type(self) -> None:
        assert len(list(ForecastType)) == 7

    def test_optimization_target(self) -> None:
        assert len(list(OptimizationTarget)) == 8


class TestAutomationEngine:
    def test_create(self) -> None:
        e = AutomationEngine()
        a = e.create("Auto 1")
        assert a.name == "Auto 1"

    def test_get(self) -> None:
        e = AutomationEngine()
        a = e.create("A")
        assert e.get(a.id) is a

    def test_list(self) -> None:
        e = AutomationEngine()
        e.create("A")
        e.create("B")
        assert len(e.list()) == 2

    def test_enable_disable(self) -> None:
        e = AutomationEngine()
        a = e.create("A")
        e.disable(a.id)
        assert e.get(a.id).enabled is False
        e.enable(a.id)
        assert e.get(a.id).enabled is True

    def test_run_no_conditions(self) -> None:
        e = AutomationEngine()
        a = e.create("A", actions=[])
        run = e.run(a.id)
        assert run.status == "completed"

    def test_run_conditions_met(self) -> None:
        e = AutomationEngine()
        cond = AutomationCondition(
            id="c1", field="status", operator=ConditionOperator.EQ.value, value="urgent"
        )
        a = e.create("A", conditions=(cond,))
        run = e.run(a.id, context={"status": "urgent"})
        assert run.status == "completed"

    def test_run_conditions_not_met(self) -> None:
        e = AutomationEngine()
        cond = AutomationCondition(
            id="c1", field="status", operator=ConditionOperator.EQ.value, value="urgent"
        )
        a = e.create("A", conditions=(cond,))
        run = e.run(a.id, context={"status": "normal"})
        assert run.status == "completed"
        assert any("skipped" in r[0] for r in run.results)

    def test_fire_by_trigger(self) -> None:
        e = AutomationEngine()
        t = AutomationTrigger(id="t1", type=TriggerType.CUSTOMER_CREATED.value)
        e.create("A", trigger=t)
        e.create("B", trigger=t)
        e.create("C", trigger=AutomationTrigger(id="t2", type=TriggerType.MANUAL.value))
        runs = e.fire_by_trigger(TriggerType.CUSTOMER_CREATED.value)
        assert len(runs) == 2

    def test_statistics(self) -> None:
        e = AutomationEngine()
        a = e.create("A")
        e.run(a.id)
        stats = e.statistics()
        assert stats["total_runs"] == 1
        assert stats["successful_runs"] == 1

    def test_with_execute_fn(self) -> None:
        calls: list[str] = []
        e = AutomationEngine(
            execute_fn=lambda **kw: calls.append(str(kw.get("action", "")))
        )
        from atlas.enterprise.models import AutomationAction

        a = e.create(
            "A", actions=(AutomationAction(id="act1", type=ActionType.NOTIFY.value),)
        )
        e.run(a.id)
        assert len(calls) == 1

    def test_list_runs(self) -> None:
        e = AutomationEngine()
        a = e.create("A")
        e.run(a.id)
        e.run(a.id)
        assert len(e.list_runs()) == 2

    def test_and_conditions(self) -> None:
        e = AutomationEngine()
        c1 = AutomationCondition(
            id="c1",
            field="a",
            operator=ConditionOperator.EQ.value,
            value="1",
            logical=LogicalOperator.AND.value,
        )
        c2 = AutomationCondition(
            id="c2",
            field="b",
            operator=ConditionOperator.EQ.value,
            value="2",
            logical=LogicalOperator.AND.value,
        )
        a = e.create("A", conditions=(c1, c2))
        run = e.run(a.id, context={"a": "1", "b": "2"})
        assert run.status == "completed"

    def test_or_conditions(self) -> None:
        e = AutomationEngine()
        c1 = AutomationCondition(
            id="c1", field="a", operator=ConditionOperator.EQ.value, value="1"
        )
        c2 = AutomationCondition(
            id="c2",
            field="b",
            operator=ConditionOperator.EQ.value,
            value="2",
            logical=LogicalOperator.OR.value,
        )
        a = e.create("A", conditions=(c1, c2))
        run = e.run(a.id, context={"a": "1", "b": "x"})
        assert run.status == "completed"


class TestRulesEngine:
    def test_create(self) -> None:
        r = RulesEngine()
        rule = r.create("Rule 1")
        assert rule.name == "Rule 1"

    def test_evaluate_match(self) -> None:
        r = RulesEngine()
        cond = AutomationCondition(
            id="c1", field="status", operator=ConditionOperator.EQ.value, value="urgent"
        )
        r.create("R", conditions=(cond,))
        matched = r.evaluate({"status": "urgent"})
        assert len(matched) == 1

    def test_evaluate_no_match(self) -> None:
        r = RulesEngine()
        cond = AutomationCondition(
            id="c1", field="status", operator=ConditionOperator.EQ.value, value="urgent"
        )
        r.create("R", conditions=(cond,))
        matched = r.evaluate({"status": "normal"})
        assert len(matched) == 0

    def test_priority_ordering(self) -> None:
        r = RulesEngine()
        r.create("Low", priority=1)
        r.create("High", priority=10)
        matched = r.evaluate({})
        assert matched[0].name == "High"

    def test_overrides(self) -> None:
        r = RulesEngine()
        # High-priority rule overrides the low-priority one
        low = r.create("Low", priority=1)
        high = r.create("High", priority=10, override_ids=(low.id,))
        matched = r.evaluate({})
        assert len(matched) == 1
        assert matched[0].name == "High"

    def test_gt_operator(self) -> None:
        r = RulesEngine()
        cond = AutomationCondition(
            id="c1", field="amount", operator=ConditionOperator.GT.value, value="100"
        )
        r.create("R", conditions=(cond,))
        assert len(r.evaluate({"amount": "200"})) == 1
        assert len(r.evaluate({"amount": "50"})) == 0

    def test_contains_operator(self) -> None:
        r = RulesEngine()
        cond = AutomationCondition(
            id="c1",
            field="text",
            operator=ConditionOperator.CONTAINS.value,
            value="hello",
        )
        r.create("R", conditions=(cond,))
        assert len(r.evaluate({"text": "say hello world"})) == 1

    def test_count(self) -> None:
        r = RulesEngine()
        r.create("A")
        assert r.count() == 1


class TestApprovalEngine:
    def test_request(self) -> None:
        a = ApprovalEngine()
        req = a.request("Buy servers")
        assert req.title == "Buy servers"
        assert req.decision == ApprovalDecision.PENDING.value

    def test_approve(self) -> None:
        a = ApprovalEngine()
        req = a.request("R")
        result = a.approve(req.id, approver="CEO")
        assert result.decision == ApprovalDecision.APPROVED.value
        assert a.get(req.id).decision == ApprovalDecision.APPROVED.value

    def test_reject(self) -> None:
        a = ApprovalEngine()
        req = a.request("R")
        a.reject(req.id)
        assert a.get(req.id).decision == ApprovalDecision.REJECTED.value

    def test_escalate(self) -> None:
        a = ApprovalEngine()
        req = a.request("R")
        esc = a.escalate(req.id, from_level="manager", to_level="ceo")
        assert esc.to_level == "ceo"
        assert a.get(req.id).decision == ApprovalDecision.ESCALATED.value

    def test_auto_approve(self) -> None:
        a = ApprovalEngine()
        req = a.request("R", type=ApprovalType.AUTOMATIC.value)
        result = a.auto_approve(req.id)
        assert result is not None
        assert result.decision == ApprovalDecision.APPROVED.value

    def test_auto_approve_already_decided(self) -> None:
        a = ApprovalEngine()
        req = a.request("R")
        a.approve(req.id)
        assert a.auto_approve(req.id) is None

    def test_pending(self) -> None:
        a = ApprovalEngine()
        a.request("A")
        a.request("B")
        a.approve(a.list()[0].id)
        assert len(a.pending()) == 1

    def test_count_by_decision(self) -> None:
        a = ApprovalEngine()
        r1 = a.request("A")
        r2 = a.request("B")
        a.approve(r1.id)
        a.reject(r2.id)
        counts = a.count_by_decision()
        assert counts[ApprovalDecision.APPROVED.value] == 1
        assert counts[ApprovalDecision.REJECTED.value] == 1

    def test_check_timeouts(self) -> None:
        a = ApprovalEngine()
        req = a.request("R", timeout_minutes=0)
        expired = a.check_timeouts()
        assert len(expired) == 1
        assert a.get(req.id).decision == ApprovalDecision.EXPIRED.value

    def test_escalation_count(self) -> None:
        a = ApprovalEngine()
        req = a.request("R")
        a.escalate(req.id)
        assert a.escalation_count() == 1


class TestProcessEngine:
    def test_create_process(self) -> None:
        pe = ProcessEngine()
        p = pe.create_process("Sales", stages=("lead", "qualified", "closed"))
        assert p.name == "Sales"
        assert len(p.stages) == 3

    def test_activate(self) -> None:
        pe = ProcessEngine()
        p = pe.create_process("P")
        pe.activate_process(p.id)
        assert pe.get_process(p.id).status == ProcessStatus.ACTIVE.value

    def test_create_pipeline(self) -> None:
        pe = ProcessEngine()
        p = pe.create_process("P", stages=("A", "B", "C"))
        pipe = pe.create_pipeline(p.id)
        assert len(pipe.stages) == 3

    def test_advance_stage(self) -> None:
        pe = ProcessEngine()
        p = pe.create_process("P", stages=("A", "B"))
        pipe = pe.create_pipeline(p.id)
        pe.advance_stage(pipe.id)
        assert pe.pipeline_progress(pipe.id) > 0

    def test_pipeline_progress(self) -> None:
        pe = ProcessEngine()
        p = pe.create_process("P", stages=("A", "B", "C"))
        pipe = pe.create_pipeline(p.id)
        pe.advance_stage(pipe.id)
        pe.advance_stage(pipe.id)
        assert pe.pipeline_progress(pipe.id) == pytest.approx(2 / 3, abs=0.01)

    def test_count(self) -> None:
        pe = ProcessEngine()
        pe.create_process("A")
        assert pe.count() == 1


class TestForecastEngine:
    def test_create(self) -> None:
        f = ForecastEngine()
        fc = f.create(type=ForecastType.REVENUE.value)
        assert fc.type == ForecastType.REVENUE.value

    def test_run_linear(self) -> None:
        f = ForecastEngine()
        fc = f.create(horizon_days=30)
        result = f.run(fc.id, historical_data=[100, 110, 120, 130])
        assert result.predicted_value > 0
        assert 0 < result.confidence <= 1.0

    def test_run_no_data(self) -> None:
        f = ForecastEngine()
        fc = f.create()
        result = f.run(fc.id)
        assert result.predicted_value == 0.0

    def test_run_single_point(self) -> None:
        f = ForecastEngine()
        fc = f.create()
        result = f.run(fc.id, historical_data=[100])
        assert result.predicted_value == 100

    def test_list_forecasts(self) -> None:
        f = ForecastEngine()
        f.create(type=ForecastType.REVENUE.value)
        f.create(type=ForecastType.COST.value)
        assert len(f.list_forecasts()) == 2
        assert len(f.list_forecasts(type=ForecastType.REVENUE.value)) == 1

    def test_with_custom_fn(self) -> None:
        from atlas.enterprise.models import ForecastResult, _new_id

        def custom(**kw: object) -> ForecastResult:
            return ForecastResult(
                id=_new_id("fr"), predicted_value=999.0, confidence=0.95
            )

        f = ForecastEngine(forecast_fn=custom)
        fc = f.create()
        result = f.run(fc.id)
        assert result.predicted_value == 999.0

    def test_count(self) -> None:
        f = ForecastEngine()
        f.create()
        assert f.count() == 1


class TestOptimizationEngine:
    def test_create_task(self) -> None:
        o = OptimizationEngine()
        t = o.create_task(
            target=OptimizationTarget.COSTS.value, current_value=1000, target_value=800
        )
        assert t.target == OptimizationTarget.COSTS.value

    def test_optimize(self) -> None:
        o = OptimizationEngine()
        t = o.create_task(current_value=1000, target_value=800)
        result = o.optimize(t.id)
        assert result.optimized_value != 1000
        assert result.improvement > 0

    def test_top_improvements(self) -> None:
        o = OptimizationEngine()
        t1 = o.create_task(current_value=1000, target_value=500)
        t2 = o.create_task(current_value=100, target_value=90)
        o.optimize(t1.id)
        o.optimize(t2.id)
        top = o.top_improvements(limit=1)
        assert len(top) == 1

    def test_list_tasks(self) -> None:
        o = OptimizationEngine()
        o.create_task(target=OptimizationTarget.COSTS.value)
        o.create_task(target=OptimizationTarget.REVENUE.value)
        assert len(o.list_tasks()) == 2
        assert len(o.list_tasks(target=OptimizationTarget.COSTS.value)) == 1

    def test_count(self) -> None:
        o = OptimizationEngine()
        o.create_task()
        assert o.count() == 1


class TestComplianceEngine:
    def test_add_policy(self) -> None:
        c = ComplianceEngine()
        p = c.add_policy("Data Protection")
        assert p.name == "Data Protection"

    def test_audit(self) -> None:
        c = ComplianceEngine()
        r = c.audit("login", actor="alice")
        assert r.action == "login"

    def test_assess_risk(self) -> None:
        c = ComplianceEngine()
        r = c.assess_risk("Security breach", level=RiskLevel.HIGH.value)
        assert r.level == RiskLevel.HIGH.value

    def test_resolve_risk(self) -> None:
        c = ComplianceEngine()
        r = c.assess_risk("R")
        c.resolve_risk(r.id)
        assert c.get_risk(r.id).resolved_at is not None

    def test_generate_report_clean(self) -> None:
        c = ComplianceEngine()
        report = c.generate_report()
        assert report.status == "compliant"

    def test_generate_report_with_violation(self) -> None:
        c = ComplianceEngine()
        c.assess_risk("Critical", level=RiskLevel.CRITICAL.value)
        report = c.generate_report()
        assert report.status == "violation"
        assert report.violations == 1

    def test_open_risk_count(self) -> None:
        c = ComplianceEngine()
        c.assess_risk("A")
        c.assess_risk("B")
        r = c.assess_risk("C")
        c.resolve_risk(r.id)
        assert c.open_risk_count() == 2

    def test_list_audits(self) -> None:
        c = ComplianceEngine()
        c.audit("action1", actor="alice")
        c.audit("action2", actor="bob")
        assert len(c.list_audits()) == 2
        assert len(c.list_audits(actor="alice")) == 1

    def test_policy_count(self) -> None:
        c = ComplianceEngine()
        c.add_policy("A")
        assert c.policy_count() == 1

    def test_audit_count(self) -> None:
        c = ComplianceEngine()
        c.audit("x")
        assert c.audit_count() == 1


class TestDepartmentManager:
    def test_create(self) -> None:
        dm = DepartmentManager()
        d = dm.create("Engineering", type=DepartmentType.ENGINEERING.value)
        assert d.name == "Engineering"

    def test_load_builtins(self) -> None:
        dm = DepartmentManager()
        created = dm.load_builtins()
        assert len(created) == 12

    def test_add_employee(self) -> None:
        dm = DepartmentManager()
        d = dm.create("Eng")
        e = dm.add_employee("Alice", department_id=d.id)
        assert e.name == "Alice"
        assert e.id in dm.get(d.id).member_ids

    def test_list_employees(self) -> None:
        dm = DepartmentManager()
        d = dm.create("Eng")
        dm.add_employee("A", department_id=d.id)
        dm.add_employee("B", department_id=d.id)
        assert len(dm.list_employees(department_id=d.id)) == 2

    def test_create_resource(self) -> None:
        dm = DepartmentManager()
        r = dm.create_resource("Servers", capacity=10)
        assert r.capacity == 10

    def test_allocate(self) -> None:
        dm = DepartmentManager()
        r = dm.create_resource("Servers", capacity=10)
        dm.allocate(r.id, 3)
        assert dm.get_resource(r.id).allocated == 3

    def test_allocate_over_capacity(self) -> None:
        dm = DepartmentManager()
        r = dm.create_resource("Servers", capacity=5)
        dm.allocate(r.id, 10)
        assert dm.get_resource(r.id).allocated == 5

    def test_release(self) -> None:
        dm = DepartmentManager()
        r = dm.create_resource("Servers", capacity=10)
        dm.allocate(r.id, 5)
        dm.release(r.id, 2)
        assert dm.get_resource(r.id).allocated == 3

    def test_metrics(self) -> None:
        dm = DepartmentManager()
        d = dm.create("Eng", budget=100000)
        dm.add_employee("A", department_id=d.id)
        m = dm.metrics(d.id)
        assert m.headcount == 1
        assert m.budget_remaining == 100000

    def test_count(self) -> None:
        dm = DepartmentManager()
        dm.create("A")
        assert dm.count() == 1

    def test_employee_count(self) -> None:
        dm = DepartmentManager()
        dm.add_employee("A")
        assert dm.employee_count() == 1


class TestEnterpriseDashboard:
    def test_snapshot(self) -> None:
        d = EnterpriseDashboard()
        snap = d.snapshot()
        assert snap.department_count == 0

    def test_add_alert(self) -> None:
        d = EnterpriseDashboard()
        d.add_alert(AlertSeverity.WARNING.value, "High CPU", "CPU at 90%")
        assert len(d.alerts()) == 1

    def test_acknowledge_alert(self) -> None:
        d = EnterpriseDashboard()
        d.add_alert(AlertSeverity.INFO.value, "Test", "msg")
        d.acknowledge_alert(0)
        assert d.alerts()[0].acknowledged is True

    def test_record_growth(self) -> None:
        d = EnterpriseDashboard()
        g = d.record_growth("Revenue", current=110, previous=100)
        assert g.growth_rate == 10.0

    def test_growth_metrics(self) -> None:
        d = EnterpriseDashboard()
        d.record_growth("A", 110, 100)
        d.record_growth("B", 200, 150)
        assert len(d.growth_metrics()) == 2

    def test_summary(self) -> None:
        d = EnterpriseDashboard()
        s = d.summary()
        assert "departments" in s
        assert "alerts" in s


class TestOrchestrator:
    def test_construct(self) -> None:
        eo = EnterpriseOrchestrator()
        assert eo is not None

    def test_all_engines_present(self) -> None:
        eo = EnterpriseOrchestrator()
        assert eo.automation is not None
        assert eo.processes is not None
        assert eo.rules is not None
        assert eo.approval is not None
        assert eo.forecast is not None
        assert eo.optimization is not None
        assert eo.compliance is not None
        assert eo.departments is not None
        assert eo.dashboard is not None

    def test_initialize(self) -> None:
        eo = EnterpriseOrchestrator()
        eo.initialize()
        assert eo.departments.count() == 12

    def test_status(self) -> None:
        eo = EnterpriseOrchestrator()
        eo.initialize()
        s = eo.status()
        assert s["departments"] == 12

    def test_full_scenario(self) -> None:
        eo = EnterpriseOrchestrator()
        eo.initialize()
        # Create automation
        t = AutomationTrigger(id="t1", type=TriggerType.CUSTOMER_CREATED.value)
        a = eo.automation.create("Welcome Email", trigger=t)
        # Create process
        p = eo.processes.create_process("Sales", stages=("lead", "qualified", "won"))
        eo.processes.activate_process(p.id)
        # Create approval
        req = eo.approval.request("Hire dev", type=ApprovalType.MANAGER.value)
        eo.approval.approve(req.id, approver="CTO")
        # Forecast
        fc = eo.forecast.create(type=ForecastType.REVENUE.value)
        eo.forecast.run(fc.id, historical_data=[100, 120, 140])
        # Compliance
        eo.compliance.add_policy("Data Protection")
        eo.compliance.audit("config_change", actor="admin")
        # Dashboard
        snap = eo.dashboard.snapshot()
        assert snap.department_count == 12


class TestNoSubsystemImports:
    def test_enterprise_does_not_import_subsystems(self) -> None:
        import os
        import re

        import atlas.enterprise

        root = os.path.dirname(atlas.enterprise.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|providers|mcp|memory|knowledge|workflows|tools|integration|agents|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline|workforce|collaboration|creator_pipeline|evaluation|business|autonomy)\b"
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
        ), "atlas.enterprise imports other Atlas subsystems:\n" + "\n".join(offenders)
