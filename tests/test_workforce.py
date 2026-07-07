"""Tests for the Atlas Autonomous Workforce (Phase 4).

Covers every module: models, roles, worker, team, manager, orchestrator,
communication, delegation, planning, coordination, review, learning,
supervisor, scheduler, metrics, reports. All tests are deterministic
and headless — they run without Brain or any Atlas subsystem, using
injected ``think_fn`` callbacks.
"""

from __future__ import annotations

import pytest

from atlas.workforce import (
    Approval,
    CommunicationChannel,
    Conflict,
    ConflictKind,
    ConflictResolution,
    CoordinationEngine,
    Delegation,
    DelegationEngine,
    DelegationError,
    Escalation,
    EscalationLevel,
    LearningEngine,
    Message,
    MessageKind,
    MetricsCollector,
    PlanningEngine,
    ReportGenerator,
    Review,
    ReviewEngine,
    ReviewVerdict,
    Scheduler,
    Shift,
    ShiftStatus,
    Supervisor,
    Task,
    TaskArtifact,
    TaskPriority,
    TaskStatus,
    Team,
    TeamError,
    TeamManager,
    Worker,
    WorkerError,
    WorkerKind,
    WorkerMemory,
    WorkerMetrics,
    WorkerRole,
    WorkerSkill,
    WorkerState,
    WorkerStatus,
    WorkforceManager,
    WorkforceOrchestrator,
    WorkforceReport,
    __version__,
    all_roles,
    can_approve,
    can_delegate,
    can_lead_team,
    can_review,
    chain_of_command_rank,
    default_skills,
    display_name,
    has_brain,
    is_agent,
    is_executive,
    is_specialist,
    priority_rank,
)

# ===========================================================================
# Package
# ===========================================================================


class TestPackage:
    def test_version(self) -> None:
        assert __version__ == "1.0.0"

    def test_has_brain(self) -> None:
        assert isinstance(has_brain(), bool)

    def test_exports(self) -> None:
        from atlas.workforce import __all__

        assert "WorkforceOrchestrator" in __all__
        assert "Worker" in __all__
        assert "WorkforceManager" in __all__
        assert "Task" in __all__
        assert "WorkerRole" in __all__


# ===========================================================================
# Enums
# ===========================================================================


class TestEnums:
    def test_worker_role_count(self) -> None:
        assert len(list(WorkerRole)) == 17

    def test_worker_status_count(self) -> None:
        assert len(list(WorkerStatus)) == 6

    def test_task_status_count(self) -> None:
        assert len(list(TaskStatus)) == 10

    def test_task_priority_count(self) -> None:
        assert len(list(TaskPriority)) == 5

    def test_message_kind_count(self) -> None:
        assert len(list(MessageKind)) == 10

    def test_escalation_level_count(self) -> None:
        assert len(list(EscalationLevel)) == 4

    def test_conflict_kind_count(self) -> None:
        assert len(list(ConflictKind)) == 5

    def test_conflict_resolution_count(self) -> None:
        assert len(list(ConflictResolution)) == 5

    def test_review_verdict_count(self) -> None:
        assert len(list(ReviewVerdict)) == 4

    def test_worker_kind_count(self) -> None:
        assert len(list(WorkerKind)) == 2

    def test_shift_status_count(self) -> None:
        assert len(list(ShiftStatus)) == 4

    def test_priority_rank_ordering(self) -> None:
        assert priority_rank(TaskPriority.CRITICAL.value) < priority_rank(
            TaskPriority.URGENT.value
        )
        assert priority_rank(TaskPriority.URGENT.value) < priority_rank(
            TaskPriority.HIGH.value
        )

    def test_priority_rank_unknown(self) -> None:
        assert priority_rank("bogus") == 99


# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    def test_worker_skill(self) -> None:
        s = WorkerSkill(name="python", level=0.9)
        assert s.name == "python"
        assert s.level == 0.9

    def test_worker_memory_with_entry(self) -> None:
        m = WorkerMemory()
        m2 = m.with_entry("key", "value")
        assert m2.get("key") == "value"
        assert m.get("key") is None  # original unchanged

    def test_worker_memory_overwrite(self) -> None:
        m = WorkerMemory().with_entry("k", "v1")
        m2 = m.with_entry("k", "v2")
        assert m2.get("k") == "v2"
        assert len(m2) == 1

    def test_worker_memory_forget(self) -> None:
        m = WorkerMemory().with_entry("k", "v")
        m2 = m.forget("k")
        assert m2.get("k") is None
        assert m.get("k") == "v"  # original unchanged

    def test_worker_memory_capacity(self) -> None:
        m = WorkerMemory(capacity=3)
        for i in range(5):
            m = m.with_entry(f"k{i}", f"v{i}")
        assert len(m) == 3  # trimmed to capacity
        # Oldest entries dropped
        assert m.get("k0") is None
        assert m.get("k4") == "v4"

    def test_worker_state_default(self) -> None:
        s = WorkerState(id="w1", name="Alice", role=WorkerRole.CEO.value)
        assert s.status == WorkerStatus.OFFLINE.value
        assert s.kind == WorkerKind.PERMANENT.value
        assert s.tasks_completed == 0

    def test_worker_state_frozen(self) -> None:
        s = WorkerState(id="w1", name="Alice", role=WorkerRole.CEO.value)
        with pytest.raises(Exception):
            s.status = WorkerStatus.IDLE.value  # type: ignore[misc]

    def test_task_default(self) -> None:
        t = Task(id="t1", title="Test")
        assert t.status == TaskStatus.PENDING.value
        assert t.priority == TaskPriority.NORMAL.value

    def test_task_artifact(self) -> None:
        a = TaskArtifact(id="a1", name="output.txt")
        assert a.kind == "file"
        assert a.size_bytes == 0

    def test_message_default(self) -> None:
        m = Message(id="m1", sender_id="w1")
        assert m.kind == MessageKind.INFO.value
        assert m.read is False

    def test_delegation_default(self) -> None:
        d = Delegation(
            id="d1",
            from_worker_id="w1",
            to_worker_id="w2",
            task_id="t1",
        )
        assert d.accepted is False
        assert d.accepted_at is None

    def test_approval_default(self) -> None:
        a = Approval(id="a1", requester_id="w1")
        assert a.granted is None  # pending

    def test_escalation_default(self) -> None:
        e = Escalation(id="e1", from_worker_id="w1")
        assert e.level == EscalationLevel.LOW.value
        assert e.resolved is False

    def test_conflict_default(self) -> None:
        c = Conflict(id="c1")
        assert c.kind == ConflictKind.RESOURCE.value
        assert c.resolved is False

    def test_review_default(self) -> None:
        r = Review(id="r1", task_id="t1", reviewer_id="w1")
        assert r.verdict == ReviewVerdict.APPROVED.value
        assert r.quality_score == 0.8

    def test_shift_default(self) -> None:
        s = Shift(id="s1", worker_id="w1")
        assert s.status == ShiftStatus.SCHEDULED.value

    def test_team_default(self) -> None:
        t = Team(id="t1", name="Team A")
        assert t.member_ids == ()
        assert t.disbanded_at is None

    def test_worker_metrics_completion_rate(self) -> None:
        m = WorkerMetrics(worker_id="w1", tasks_assigned=10, tasks_completed=8)
        assert m.completion_rate() == 0.8

    def test_worker_metrics_failure_rate(self) -> None:
        m = WorkerMetrics(worker_id="w1", tasks_assigned=10, tasks_failed=2)
        assert m.failure_rate() == 0.2

    def test_worker_metrics_zero_division(self) -> None:
        m = WorkerMetrics(worker_id="w1")
        assert m.completion_rate() == 0.0
        assert m.failure_rate() == 0.0

    def test_workforce_report(self) -> None:
        r = WorkforceReport(id="r1")
        assert r.total_workers == 0
        assert r.worker_metrics == ()


# ===========================================================================
# Roles
# ===========================================================================


class TestRoles:
    def test_all_roles_count(self) -> None:
        assert len(all_roles()) == 17

    def test_chain_of_command_ceo_lowest(self) -> None:
        assert chain_of_command_rank(WorkerRole.CEO.value) == 0

    def test_chain_of_command_cto_second(self) -> None:
        assert chain_of_command_rank(WorkerRole.CTO.value) == 1

    def test_chain_of_command_unknown(self) -> None:
        assert chain_of_command_rank("bogus") == 99

    def test_default_skills_ceo(self) -> None:
        skills = default_skills(WorkerRole.CEO.value)
        assert len(skills) > 0
        assert any(s.name == "strategy" for s in skills)

    def test_default_skills_software_engineer(self) -> None:
        skills = default_skills(WorkerRole.SOFTWARE_ENGINEER.value)
        assert any(s.name == "python" for s in skills)

    def test_default_skills_unknown(self) -> None:
        assert default_skills("bogus") == ()

    def test_can_review_executive(self) -> None:
        assert can_review(WorkerRole.CEO.value) is True
        assert can_review(WorkerRole.CTO.value) is True

    def test_can_review_qa(self) -> None:
        assert can_review(WorkerRole.QA_ENGINEER.value) is True

    def test_can_review_engineer(self) -> None:
        assert can_review(WorkerRole.SOFTWARE_ENGINEER.value) is False

    def test_can_approve_executive(self) -> None:
        assert can_approve(WorkerRole.CEO.value) is True

    def test_can_approve_pm(self) -> None:
        assert can_approve(WorkerRole.PROJECT_MANAGER.value) is True

    def test_can_delegate_pm(self) -> None:
        assert can_delegate(WorkerRole.PROJECT_MANAGER.value) is True

    def test_can_lead_team_executive(self) -> None:
        assert can_lead_team(WorkerRole.CEO.value) is True

    def test_is_executive(self) -> None:
        assert is_executive(WorkerRole.CEO.value) is True
        assert is_executive(WorkerRole.CTO.value) is True
        assert is_executive(WorkerRole.SOFTWARE_ENGINEER.value) is False

    def test_is_agent(self) -> None:
        assert is_agent(WorkerRole.BROWSER_AGENT.value) is True
        assert is_agent(WorkerRole.GITHUB_AGENT.value) is True
        assert is_agent(WorkerRole.BLENDER_ARTIST.value) is True
        assert is_agent(WorkerRole.CEO.value) is False

    def test_is_specialist(self) -> None:
        assert is_specialist(WorkerRole.KNOWLEDGE_SPECIALIST.value) is True
        assert is_specialist(WorkerRole.MEMORY_SPECIALIST.value) is True
        assert is_specialist(WorkerRole.VISION_SPECIALIST.value) is True
        assert is_specialist(WorkerRole.CEO.value) is False

    def test_display_name(self) -> None:
        assert display_name(WorkerRole.CEO.value) == "Chief Executive Officer"
        assert display_name(WorkerRole.CTO.value) == "Chief Technology Officer"

    def test_display_name_unknown(self) -> None:
        assert display_name("bogus") == "Bogus"


# ===========================================================================
# Worker
# ===========================================================================


class TestWorker:
    def test_construct(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        assert w.name == "Alice"
        assert w.role == WorkerRole.CEO.value
        assert w.status == WorkerStatus.OFFLINE.value

    def test_start(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        assert w.status == WorkerStatus.IDLE.value
        assert w.is_idle

    def test_stop(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        w.stop()
        assert w.status == WorkerStatus.STOPPED.value

    def test_pause_resume(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        w.pause()
        assert w.status == WorkerStatus.PAUSED.value
        w.resume()
        assert w.status == WorkerStatus.IDLE.value

    def test_default_skills_from_role(self) -> None:
        w = Worker(name="Bob", role=WorkerRole.SOFTWARE_ENGINEER.value)
        assert w.has_skill("python")

    def test_custom_skills(self) -> None:
        w = Worker(
            name="Bob",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            skills=(WorkerSkill(name="rust", level=0.9),),
        )
        assert w.has_skill("rust")
        assert not w.has_skill("python")  # rust-only worker has no python

    def test_skill_level(self) -> None:
        w = Worker(name="Bob", role=WorkerRole.SOFTWARE_ENGINEER.value)
        level = w.skill_level("python")
        assert 0.0 < level <= 1.0

    def test_skill_level_unknown(self) -> None:
        w = Worker(name="Bob", role=WorkerRole.SOFTWARE_ENGINEER.value)
        assert w.skill_level("bogus") == 0.0

    def test_has_skill_min_level(self) -> None:
        w = Worker(
            name="Bob",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            skills=(WorkerSkill(name="python", level=0.5),),
        )
        assert w.has_skill("python", min_level=0.3)
        assert not w.has_skill("python", min_level=0.9)

    def test_meets_requirements_role(self) -> None:
        w = Worker(name="Bob", role=WorkerRole.SOFTWARE_ENGINEER.value)
        assert w.meets_requirements(required_role=WorkerRole.SOFTWARE_ENGINEER.value)
        assert not w.meets_requirements(required_role=WorkerRole.CEO.value)

    def test_meets_requirements_skills(self) -> None:
        w = Worker(
            name="Bob",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            skills=(WorkerSkill(name="python", level=0.5),),
        )
        assert w.meets_requirements(required_skills=("python",))
        assert not w.meets_requirements(required_skills=("rust",))

    def test_memory(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.remember("last_error", "connection timeout")
        assert w.recall("last_error") == "connection timeout"
        assert w.memory_size() == 1

    def test_memory_forget(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.remember("k", "v")
        w.forget("k")
        assert w.recall("k") is None
        assert w.memory_size() == 0

    def test_assign_task(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        task = Task(id="t1", title="Test")
        w.assign_task(task)
        assert w.status == WorkerStatus.BUSY.value
        assert w.current_task_id() == "t1"

    def test_assign_task_offline_raises(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        task = Task(id="t1", title="Test")
        with pytest.raises(WorkerError):
            w.assign_task(task)

    def test_execute_task_no_fn(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        task = Task(id="t1", title="Test", description="Do something")
        result = w.execute_task(task)
        assert isinstance(result, dict)
        assert result["status"] == "offline"

    def test_execute_task_with_fn(self) -> None:
        calls: list[str] = []

        def fake_think(**kwargs: object) -> str:
            calls.append(str(kwargs.get("goal_description", "")))
            return "done"

        w = Worker(name="Alice", role=WorkerRole.CEO.value, think_fn=fake_think)
        w.start()
        task = Task(id="t1", title="Test", description="Do something")
        result = w.execute_task(task)
        assert result == "done"
        assert len(calls) == 1

    def test_complete_task(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        task = Task(id="t1", title="Test")
        w.assign_task(task)
        w.complete_task(task)
        assert w.status == WorkerStatus.IDLE.value
        assert w.state.tasks_completed == 1

    def test_complete_wrong_task_raises(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        task = Task(id="t1", title="Test")
        w.assign_task(task)
        other = Task(id="t2", title="Other")
        with pytest.raises(WorkerError):
            w.complete_task(other)

    def test_fail_task(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.start()
        task = Task(id="t1", title="Test")
        w.assign_task(task)
        w.fail_task(task)
        assert w.status == WorkerStatus.IDLE.value
        assert w.state.tasks_failed == 1

    def test_role_checks(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        assert w.can_review()
        assert w.can_approve()
        assert w.can_delegate()
        assert w.can_lead_team()
        assert w.is_executive()

    def test_role_checks_engineer(self) -> None:
        w = Worker(name="Bob", role=WorkerRole.SOFTWARE_ENGINEER.value)
        assert not w.can_review()
        assert not w.can_approve()
        assert w.can_delegate()

    def test_mark_error(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        w.mark_error()
        assert w.status == WorkerStatus.ERROR.value

    def test_is_online(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        assert not w.is_online
        w.start()
        assert w.is_online

    def test_display_name(self) -> None:
        w = Worker(name="Alice", role=WorkerRole.CEO.value)
        assert w.display_name() == "Chief Executive Officer"


# ===========================================================================
# Communication
# ===========================================================================


class TestCommunication:
    def test_send(self) -> None:
        c = CommunicationChannel()
        msg = c.send(sender_id="w1", recipient_id="w2", subject="Hi", body="Hello")
        assert msg.sender_id == "w1"
        assert msg.recipient_id == "w2"

    def test_get(self) -> None:
        c = CommunicationChannel()
        msg = c.send(sender_id="w1", recipient_id="w2", subject="Hi")
        assert c.get(msg.id) is msg

    def test_inbox(self) -> None:
        c = CommunicationChannel()
        c.send(sender_id="w1", recipient_id="w2", subject="A")
        c.send(sender_id="w1", recipient_id="w2", subject="B")
        assert len(c.inbox("w2")) == 2

    def test_inbox_unread_only(self) -> None:
        c = CommunicationChannel()
        m = c.send(sender_id="w1", recipient_id="w2", subject="A")
        c.send(sender_id="w1", recipient_id="w2", subject="B")
        c.mark_read(m.id)
        assert len(c.inbox("w2", unread_only=True)) == 1

    def test_broadcast(self) -> None:
        c = CommunicationChannel()
        msg = c.broadcast(sender_id="w1", team_id="t1", subject="Hi", body="All")
        assert msg.kind == MessageKind.BROADCAST.value
        assert msg.recipient_id == ""

    def test_broadcasts_for(self) -> None:
        c = CommunicationChannel()
        c.broadcast(sender_id="w1", team_id="t1", subject="A", body="x")
        c.broadcast(sender_id="w1", team_id="t2", subject="B", body="x")
        assert len(c.broadcasts_for("w2", team_ids=("t1",))) == 1

    def test_sent_by(self) -> None:
        c = CommunicationChannel()
        c.send(sender_id="w1", recipient_id="w2", subject="A")
        assert len(c.sent_by("w1")) == 1

    def test_request(self) -> None:
        c = CommunicationChannel()
        msg = c.request("w1", "w2", "Need info", "Please share")
        assert msg.kind == MessageKind.REQUEST.value

    def test_respond(self) -> None:
        c = CommunicationChannel()
        original = c.send(sender_id="w1", recipient_id="w2", subject="Q")
        reply = c.respond("w2", "w1", original.id, "Re: Q", "Answer")
        assert reply.reply_to == original.id
        assert reply.kind == MessageKind.RESPONSE.value

    def test_handoff(self) -> None:
        c = CommunicationChannel()
        msg = c.handoff("w1", "w2", "t1", notes="Over to you")
        assert msg.kind == MessageKind.HANDOFF.value
        assert msg.task_id == "t1"

    def test_thread(self) -> None:
        c = CommunicationChannel()
        m1 = c.send("w1", "w2", subject="Root")
        m2 = c.respond("w2", "w1", m1.id, "Re", "Reply 1")
        m3 = c.respond("w1", "w2", m2.id, "Re", "Reply 2")
        thread = c.thread(m1.id)
        assert len(thread) == 3

    def test_mark_read(self) -> None:
        c = CommunicationChannel()
        msg = c.send("w1", "w2", subject="Hi")
        c.mark_read(msg.id)
        assert c.get(msg.id).read is True

    def test_mark_all_read(self) -> None:
        c = CommunicationChannel()
        c.send("w1", "w2", subject="A")
        c.send("w1", "w2", subject="B")
        count = c.mark_all_read("w2")
        assert count == 2

    def test_unread_count(self) -> None:
        c = CommunicationChannel()
        c.send("w1", "w2", subject="A")
        c.send("w1", "w2", subject="B")
        assert c.unread_count("w2") == 2

    def test_message_count(self) -> None:
        c = CommunicationChannel()
        c.send("w1", "w2", subject="A")
        assert c.message_count() == 1

    def test_count_by_kind(self) -> None:
        c = CommunicationChannel()
        c.send("w1", "w2", kind=MessageKind.INFO.value, subject="A")
        c.send("w1", "w2", kind=MessageKind.REQUEST.value, subject="B")
        counts = c.count_by_kind()
        assert counts[MessageKind.INFO.value] == 1
        assert counts[MessageKind.REQUEST.value] == 1

    def test_all_messages(self) -> None:
        c = CommunicationChannel()
        c.send("w1", "w2", subject="A")
        c.send("w1", "w2", subject="B")
        assert len(c.all_messages()) == 2

    def test_clear(self) -> None:
        c = CommunicationChannel()
        c.send("w1", "w2", subject="A")
        assert c.clear() == 1
        assert c.message_count() == 0

    def test_delete(self) -> None:
        c = CommunicationChannel()
        msg = c.send("w1", "w2", subject="A")
        assert c.delete(msg.id) is True
        assert c.delete(msg.id) is False

    def test_delivery_callback(self) -> None:
        delivered: list[str] = []
        c = CommunicationChannel(delivery_fn=lambda m: delivered.append(m.id))
        msg = c.send("w1", "w2", subject="Hi")
        assert delivered == [msg.id]


# ===========================================================================
# Delegation
# ===========================================================================


class TestDelegation:
    def test_delegate(self) -> None:
        e = DelegationEngine()
        d = e.delegate(
            from_worker_id="w1",
            to_worker_id="w2",
            task_id="t1",
            from_role=WorkerRole.CEO.value,
            to_role=WorkerRole.SOFTWARE_ENGINEER.value,
        )
        assert d.from_worker_id == "w1"

    def test_delegate_self_raises(self) -> None:
        e = DelegationEngine()
        with pytest.raises(DelegationError):
            e.delegate("w1", "w1", "t1")

    def test_delegate_upward_raises(self) -> None:
        e = DelegationEngine()
        with pytest.raises(DelegationError):
            e.delegate(
                from_worker_id="w1",
                to_worker_id="w2",
                task_id="t1",
                from_role=WorkerRole.SOFTWARE_ENGINEER.value,
                to_role=WorkerRole.CEO.value,
            )

    def test_delegate_sideways_ok(self) -> None:
        e = DelegationEngine()
        d = e.delegate(
            from_worker_id="w1",
            to_worker_id="w2",
            task_id="t1",
            from_role=WorkerRole.SOFTWARE_ENGINEER.value,
            to_role=WorkerRole.RESEARCH_ENGINEER.value,
        )
        assert d is not None

    def test_accept(self) -> None:
        e = DelegationEngine()
        d = e.delegate("w1", "w2", "t1")
        accepted = e.accept(d.id)
        assert accepted.accepted is True
        assert accepted.accepted_at is not None

    def test_reject(self) -> None:
        e = DelegationEngine()
        d = e.delegate("w1", "w2", "t1")
        rejected = e.reject(d.id)
        assert rejected.accepted is False
        assert rejected.accepted_at is not None

    def test_by_delegator(self) -> None:
        e = DelegationEngine()
        e.delegate("w1", "w2", "t1")
        e.delegate("w1", "w3", "t2")
        assert len(e.by_delegator("w1")) == 2

    def test_by_delegatee(self) -> None:
        e = DelegationEngine()
        e.delegate("w1", "w2", "t1")
        e.delegate("w3", "w2", "t2")
        assert len(e.by_delegatee("w2")) == 2

    def test_for_task(self) -> None:
        e = DelegationEngine()
        e.delegate("w1", "w2", "t1")
        e.delegate("w1", "w2", "t2")
        assert len(e.for_task("t1")) == 1

    def test_pending(self) -> None:
        e = DelegationEngine()
        d = e.delegate("w1", "w2", "t1")
        assert len(e.pending()) == 1
        e.accept(d.id)
        assert len(e.pending()) == 0

    def test_accepted(self) -> None:
        e = DelegationEngine()
        d = e.delegate("w1", "w2", "t1")
        e.accept(d.id)
        assert len(e.accepted()) == 1

    def test_rejected(self) -> None:
        e = DelegationEngine()
        d = e.delegate("w1", "w2", "t1")
        e.reject(d.id)
        assert len(e.rejected()) == 1

    def test_count(self) -> None:
        e = DelegationEngine()
        e.delegate("w1", "w2", "t1")
        e.delegate("w1", "w3", "t2")
        assert e.count() == 2

    def test_count_for(self) -> None:
        e = DelegationEngine()
        e.delegate("w1", "w2", "t1")
        e.delegate("w3", "w2", "t2")
        made, received = e.count_for("w2")
        assert made == 0
        assert received == 2

    def test_acceptance_rate(self) -> None:
        e = DelegationEngine()
        d1 = e.delegate("w1", "w2", "t1")
        d2 = e.delegate("w1", "w3", "t2")
        e.accept(d1.id)
        e.reject(d2.id)
        assert e.acceptance_rate() == 0.5

    def test_acceptance_rate_no_decisions(self) -> None:
        e = DelegationEngine()
        assert e.acceptance_rate() == 0.0


# ===========================================================================
# Planning
# ===========================================================================


class TestPlanning:
    def test_decompose_default(self) -> None:
        p = PlanningEngine()
        tasks = p.decompose("Build an app")
        assert len(tasks) == 3  # research, implement, review

    def test_decompose_with_fn(self) -> None:
        def fake_decompose(**kwargs: object) -> list[dict[str, object]]:
            return [{"title": "Custom task", "description": "Custom"}]

        p = PlanningEngine(decompose_fn=fake_decompose)
        tasks = p.decompose("Goal")
        assert len(tasks) == 1
        assert tasks[0].title == "Custom task"

    def test_decompose_assigns_team_id(self) -> None:
        p = PlanningEngine()
        tasks = p.decompose("Goal", team_id="team1")
        assert all(t.team_id == "team1" for t in tasks)

    def test_order_by_dependencies(self) -> None:
        p = PlanningEngine()
        t3 = Task(id="t3", title="C", dependencies=("t2",))
        t2 = Task(id="t2", title="B", dependencies=("t1",))
        t1 = Task(id="t1", title="A")
        ordered = p.order_by_dependencies([t3, t2, t1])
        assert [t.id for t in ordered] == ["t1", "t2", "t3"]

    def test_order_empty(self) -> None:
        p = PlanningEngine()
        assert p.order_by_dependencies([]) == []

    def test_critical_path(self) -> None:
        p = PlanningEngine()
        t1 = Task(id="t1", title="A")
        t2 = Task(id="t2", title="B", dependencies=("t1",))
        t3 = Task(id="t3", title="C", dependencies=("t2",))
        path = p.critical_path([t1, t2, t3])
        assert len(path) == 3
        assert path[0].id == "t1"
        assert path[-1].id == "t3"

    def test_critical_path_empty(self) -> None:
        p = PlanningEngine()
        assert p.critical_path([]) == []


# ===========================================================================
# Coordination
# ===========================================================================


class TestCoordination:
    def test_publish_artifact(self) -> None:
        c = CoordinationEngine()
        a = c.publish_artifact("t1", name="output.txt")
        assert a.name == "output.txt"

    def test_artifacts_for(self) -> None:
        c = CoordinationEngine()
        c.publish_artifact("t1", name="a.txt")
        c.publish_artifact("t1", name="b.txt")
        assert len(c.artifacts_for("t1")) == 2

    def test_all_artifacts(self) -> None:
        c = CoordinationEngine()
        c.publish_artifact("t1", name="a")
        c.publish_artifact("t2", name="b")
        assert len(c.all_artifacts()) == 2

    def test_artifact_count(self) -> None:
        c = CoordinationEngine()
        c.publish_artifact("t1", name="a")
        c.publish_artifact("t1", name="b")
        assert c.artifact_count() == 2

    def test_add_dependency(self) -> None:
        c = CoordinationEngine()
        c.add_dependency("t2", "t1")
        assert c.dependencies_of("t2") == ("t1",)

    def test_add_dependency_idempotent(self) -> None:
        c = CoordinationEngine()
        c.add_dependency("t2", "t1")
        c.add_dependency("t2", "t1")
        assert c.dependencies_of("t2") == ("t1",)

    def test_dependents_of(self) -> None:
        c = CoordinationEngine()
        c.add_dependency("t2", "t1")
        c.add_dependency("t3", "t1")
        assert set(c.dependents_of("t1")) == {"t2", "t3"}

    def test_is_blocked(self) -> None:
        c = CoordinationEngine()
        c.add_dependency("t2", "t1")
        assert c.is_blocked("t2", completed=set())
        assert not c.is_blocked("t2", completed={"t1"})

    def test_is_blocked_no_completion_info(self) -> None:
        c = CoordinationEngine()
        c.add_dependency("t2", "t1")
        assert not c.is_blocked("t2")  # None = no info

    def test_unblock_tasks(self) -> None:
        c = CoordinationEngine()
        c.add_dependency("t2", "t1")
        t2 = Task(id="t2", title="B", status=TaskStatus.BLOCKED.value)
        unblocked = c.unblock_tasks([t2], completed_task_ids={"t1"})
        assert len(unblocked) == 1

    def test_record_handoff(self) -> None:
        c = CoordinationEngine()
        c.record_handoff("t1", "t2")
        assert c.handoff_count() == 1

    def test_handoffs(self) -> None:
        c = CoordinationEngine()
        c.record_handoff("t1", "t2")
        c.record_handoff("t2", "t3")
        assert len(c.handoffs()) == 2

    def test_shared_state(self) -> None:
        c = CoordinationEngine()
        c.publish_artifact("t1", name="a")
        c.add_dependency("t2", "t1")
        c.record_handoff("t1", "t2")
        state = c.shared_state()
        assert state["total_artifacts"] == 1
        assert state["dependencies"] == 1
        assert state["handoffs"] == 1

    def test_clear(self) -> None:
        c = CoordinationEngine()
        c.publish_artifact("t1", name="a")
        c.clear()
        assert c.artifact_count() == 0


# ===========================================================================
# Review
# ===========================================================================


class TestReview:
    def test_submit_review(self) -> None:
        r = ReviewEngine()
        review = r.submit_review("t1", "w1", verdict=ReviewVerdict.APPROVED.value)
        assert review.verdict == ReviewVerdict.APPROVED.value

    def test_get_review(self) -> None:
        r = ReviewEngine()
        review = r.submit_review("t1", "w1")
        assert r.get_review(review.id) is review

    def test_reviews_for_task(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1")
        r.submit_review("t1", "w2")
        assert len(r.reviews_for_task("t1")) == 2

    def test_reviews_by(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1")
        r.submit_review("t2", "w1")
        assert len(r.reviews_by("w1")) == 2

    def test_latest_review(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", quality_score=0.5)
        latest = r.submit_review("t1", "w2", quality_score=0.9)
        assert r.latest_review("t1").id == latest.id

    def test_latest_review_none(self) -> None:
        r = ReviewEngine()
        assert r.latest_review("missing") is None

    def test_is_approved(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", verdict=ReviewVerdict.APPROVED.value)
        assert r.is_approved("t1")

    def test_is_rejected(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", verdict=ReviewVerdict.REJECTED.value)
        assert r.is_rejected("t1")

    def test_needs_rework(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", verdict=ReviewVerdict.CHANGES_REQUESTED.value)
        assert r.needs_rework("t1")

    def test_average_quality(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", quality_score=0.8)
        r.submit_review("t1", "w2", quality_score=0.6)
        assert r.average_quality("t1") == 0.7

    def test_average_quality_all(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", quality_score=0.8)
        r.submit_review("t2", "w2", quality_score=0.6)
        assert r.average_quality() == 0.7

    def test_request_approval(self) -> None:
        r = ReviewEngine()
        a = r.request_approval("w1", task_id="t1", kind="deployment")
        assert a.granted is None  # pending

    def test_grant_approval(self) -> None:
        r = ReviewEngine()
        a = r.request_approval("w1", task_id="t1")
        granted = r.grant_approval(a.id, "w2")
        assert granted.granted is True

    def test_deny_approval(self) -> None:
        r = ReviewEngine()
        a = r.request_approval("w1", task_id="t1")
        denied = r.deny_approval(a.id, "w2")
        assert denied.granted is False

    def test_pending_approvals(self) -> None:
        r = ReviewEngine()
        r.request_approval("w1", task_id="t1")
        r.request_approval("w2", task_id="t2")
        assert len(r.pending_approvals()) == 2

    def test_decided_approvals(self) -> None:
        r = ReviewEngine()
        a = r.request_approval("w1", task_id="t1")
        r.grant_approval(a.id, "w2")
        assert len(r.decided_approvals()) == 1

    def test_approvals_for_task(self) -> None:
        r = ReviewEngine()
        r.request_approval("w1", task_id="t1")
        r.request_approval("w2", task_id="t2")
        assert len(r.approvals_for_task("t1")) == 1

    def test_approval_rate(self) -> None:
        r = ReviewEngine()
        a1 = r.request_approval("w1", task_id="t1")
        a2 = r.request_approval("w2", task_id="t2")
        r.grant_approval(a1.id, "w3")
        r.deny_approval(a2.id, "w3")
        assert r.approval_rate() == 0.5

    def test_apply_verdict_approved(self) -> None:
        r = ReviewEngine()
        task = Task(id="t1", title="Test")
        review = r.submit_review("t1", "w1", verdict=ReviewVerdict.APPROVED.value)
        updated = r.apply_verdict(task, review)
        assert updated.status == TaskStatus.APPROVED.value

    def test_apply_verdict_rejected(self) -> None:
        r = ReviewEngine()
        task = Task(id="t1", title="Test")
        review = r.submit_review("t1", "w1", verdict=ReviewVerdict.REJECTED.value)
        updated = r.apply_verdict(task, review)
        assert updated.status == TaskStatus.REJECTED.value

    def test_count_by_verdict(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1", verdict=ReviewVerdict.APPROVED.value)
        r.submit_review("t2", "w2", verdict=ReviewVerdict.REJECTED.value)
        counts = r.count_by_verdict()
        assert counts[ReviewVerdict.APPROVED.value] == 1

    def test_review_count(self) -> None:
        r = ReviewEngine()
        r.submit_review("t1", "w1")
        assert r.review_count() == 1


# ===========================================================================
# Learning
# ===========================================================================


class TestLearning:
    def test_record_lesson(self) -> None:
        e = LearningEngine()
        lesson = e.record_lesson("w1", "Always test your code", skill_name="python")
        assert lesson.worker_id == "w1"
        assert lesson.skill_name == "python"

    def test_get_lesson(self) -> None:
        e = LearningEngine()
        lesson = e.record_lesson("w1", "Test")
        assert e.get_lesson(lesson.id) is lesson

    def test_lessons_for(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A")
        e.record_lesson("w1", "B")
        e.record_lesson("w2", "C")
        assert len(e.lessons_for("w1")) == 2

    def test_lessons_for_skill(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A", skill_name="python")
        e.record_lesson("w2", "B", skill_name="rust")
        assert len(e.lessons_for_skill("python")) == 1

    def test_pending_lessons(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A", skill_name="python", impact=0.1)
        assert len(e.pending_lessons()) == 1

    def test_apply_lesson(self) -> None:
        e = LearningEngine()
        lesson = e.record_lesson(
            "w1", "Learned python", skill_name="python", impact=0.1
        )
        skills = (WorkerSkill(name="python", level=0.5),)
        new_skills = e.apply_lesson(lesson.id, skills)
        assert new_skills[0].level == 0.6

    def test_apply_lesson_new_skill(self) -> None:
        e = LearningEngine()
        lesson = e.record_lesson("w1", "Learned rust", skill_name="rust", impact=0.3)
        skills = (WorkerSkill(name="python", level=0.5),)
        new_skills = e.apply_lesson(lesson.id, skills)
        assert any(s.name == "rust" for s in new_skills)

    def test_apply_lesson_capped_at_1(self) -> None:
        e = LearningEngine()
        lesson = e.record_lesson("w1", "Mastery", skill_name="python", impact=0.5)
        skills = (WorkerSkill(name="python", level=0.8),)
        new_skills = e.apply_lesson(lesson.id, skills)
        assert new_skills[0].level == 1.0

    def test_apply_lesson_general(self) -> None:
        e = LearningEngine()
        lesson = e.record_lesson("w1", "General insight", skill_name="")
        skills = (WorkerSkill(name="python", level=0.5),)
        new_skills = e.apply_lesson(lesson.id, skills)
        assert new_skills == skills  # unchanged

    def test_apply_all_pending(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A", skill_name="python", impact=0.1)
        e.record_lesson("w1", "B", skill_name="python", impact=0.1)
        skills = (WorkerSkill(name="python", level=0.5),)
        new_skills = e.apply_all_pending("w1", skills)
        assert new_skills[0].level == 0.7

    def test_lesson_count(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A")
        assert e.lesson_count() == 1

    def test_count_for(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A")
        e.record_lesson("w2", "B")
        assert e.count_for("w1") == 1

    def test_count_by_kind(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A", kind="best_practice")
        e.record_lesson("w1", "B", kind="mistake")
        counts = e.count_by_kind()
        assert counts["best_practice"] == 1

    def test_average_impact(self) -> None:
        e = LearningEngine()
        e.record_lesson("w1", "A", impact=0.2)
        e.record_lesson("w1", "B", impact=0.4)
        assert abs(e.average_impact("w1") - 0.3) < 1e-9


# ===========================================================================
# Supervisor
# ===========================================================================


class TestSupervisor:
    def test_escalate(self) -> None:
        s = Supervisor()
        e = s.escalate("w1", "I'm stuck", level=EscalationLevel.HIGH.value)
        assert e.from_worker_id == "w1"
        assert e.level == EscalationLevel.HIGH.value

    def test_get_escalation(self) -> None:
        s = Supervisor()
        e = s.escalate("w1", "stuck")
        assert s.get_escalation(e.id) is e

    def test_resolve_escalation(self) -> None:
        s = Supervisor()
        e = s.escalate("w1", "stuck")
        resolved = s.resolve_escalation(e.id, resolution="Fixed")
        assert resolved.resolved is True
        assert resolved.resolution == "Fixed"

    def test_pending_escalations(self) -> None:
        s = Supervisor()
        s.escalate("w1", "stuck")
        s.escalate("w2", "stuck")
        assert len(s.pending_escalations()) == 2

    def test_resolved_escalations(self) -> None:
        s = Supervisor()
        e = s.escalate("w1", "stuck")
        s.resolve_escalation(e.id)
        assert len(s.resolved_escalations()) == 1

    def test_escalations_by_worker(self) -> None:
        s = Supervisor()
        s.escalate("w1", "A")
        s.escalate("w2", "B")
        assert len(s.escalations_by_worker("w1")) == 1

    def test_escalations_by_level(self) -> None:
        s = Supervisor()
        s.escalate("w1", "A", level=EscalationLevel.LOW.value)
        s.escalate("w2", "B", level=EscalationLevel.CRITICAL.value)
        assert len(s.escalations_by_level(EscalationLevel.CRITICAL.value)) == 1

    def test_escalation_count(self) -> None:
        s = Supervisor()
        s.escalate("w1", "A")
        assert s.escalation_count() == 1

    def test_pending_count(self) -> None:
        s = Supervisor()
        s.escalate("w1", "A")
        assert s.pending_count() == 1

    def test_report_conflict(self) -> None:
        s = Supervisor()
        c = s.report_conflict(
            kind=ConflictKind.RESOURCE.value,
            worker_ids=("w1", "w2"),
            description="Both need the GPU",
        )
        assert c.kind == ConflictKind.RESOURCE.value

    def test_get_conflict(self) -> None:
        s = Supervisor()
        c = s.report_conflict(worker_ids=("w1", "w2"))
        assert s.get_conflict(c.id) is c

    def test_resolve_conflict(self) -> None:
        s = Supervisor()
        c = s.report_conflict(worker_ids=("w1", "w2"))
        resolved = s.resolve_conflict(
            c.id, resolution=ConflictResolution.MEDIATED.value
        )
        assert resolved.resolved is True
        assert resolved.resolution == ConflictResolution.MEDIATED.value

    def test_pending_conflicts(self) -> None:
        s = Supervisor()
        s.report_conflict(worker_ids=("w1", "w2"))
        assert len(s.pending_conflicts()) == 1

    def test_conflicts_involving(self) -> None:
        s = Supervisor()
        s.report_conflict(worker_ids=("w1", "w2"))
        s.report_conflict(worker_ids=("w1", "w3"))
        assert len(s.conflicts_involving("w1")) == 2

    def test_conflict_count(self) -> None:
        s = Supervisor()
        s.report_conflict(worker_ids=("w1", "w2"))
        assert s.conflict_count() == 1

    def test_count_by_kind(self) -> None:
        s = Supervisor()
        s.report_conflict(kind=ConflictKind.RESOURCE.value)
        s.report_conflict(kind=ConflictKind.PRIORITY.value)
        counts = s.count_by_kind()
        assert counts[ConflictKind.RESOURCE.value] == 1

    def test_reassign_task(self) -> None:
        s = Supervisor()
        task = Task(id="t1", title="Test", assignee_id="w1")
        reassigned = s.reassign_task(task, "w2", reason="Better fit")
        assert reassigned.assignee_id == "w2"

    def test_cancel_task(self) -> None:
        s = Supervisor()
        task = Task(id="t1", title="Test")
        cancelled = s.cancel_task(task, reason="No longer needed")
        assert cancelled.status == TaskStatus.CANCELLED.value

    def test_status(self) -> None:
        s = Supervisor()
        s.escalate("w1", "stuck")
        s.report_conflict(worker_ids=("w1", "w2"))
        status = s.status()
        assert status["total_escalations"] == 1
        assert status["total_conflicts"] == 1


# ===========================================================================
# Scheduler
# ===========================================================================


class TestScheduler:
    def test_schedule_shift(self) -> None:
        s = Scheduler()
        shift = s.schedule_shift("w1")
        assert shift.worker_id == "w1"
        assert shift.status == ShiftStatus.SCHEDULED.value

    def test_start_shift(self) -> None:
        s = Scheduler()
        shift = s.schedule_shift("w1")
        s.start_shift(shift.id)
        assert s.get_shift(shift.id).status == ShiftStatus.ACTIVE.value

    def test_complete_shift(self) -> None:
        s = Scheduler()
        shift = s.schedule_shift("w1")
        s.complete_shift(shift.id, tasks_completed=5)
        assert s.get_shift(shift.id).status == ShiftStatus.COMPLETED.value
        assert s.get_shift(shift.id).tasks_completed == 5

    def test_cancel_shift(self) -> None:
        s = Scheduler()
        shift = s.schedule_shift("w1")
        s.cancel_shift(shift.id)
        assert s.get_shift(shift.id).status == ShiftStatus.CANCELLED.value

    def test_shifts_for(self) -> None:
        s = Scheduler()
        s.schedule_shift("w1")
        s.schedule_shift("w1")
        s.schedule_shift("w2")
        assert len(s.shifts_for("w1")) == 2

    def test_active_shifts(self) -> None:
        s = Scheduler()
        sh1 = s.schedule_shift("w1")
        s.schedule_shift("w2")
        s.start_shift(sh1.id)
        assert len(s.active_shifts()) == 1

    def test_active_shift_for(self) -> None:
        s = Scheduler()
        shift = s.schedule_shift("w1")
        s.start_shift(shift.id)
        assert s.active_shift_for("w1").id == shift.id

    def test_pick_worker(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1",
            name="A",
            role=(
                WorkerRole.SWE.value
                if hasattr(WorkerRole, "SWE")
                else WorkerRole.SOFTWARE_ENGINEER.value
            ),
            status=WorkerStatus.IDLE.value,
        )
        w2 = WorkerState(
            id="w2",
            name="B",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            status=WorkerStatus.BUSY.value,
        )
        picked = s.pick_worker([w1, w2])
        assert picked is not None
        assert picked.id == "w1"

    def test_pick_worker_with_role(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1", name="A", role=WorkerRole.CEO.value, status=WorkerStatus.IDLE.value
        )
        w2 = WorkerState(
            id="w2",
            name="B",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            status=WorkerStatus.IDLE.value,
        )
        picked = s.pick_worker(
            [w1, w2], required_role=WorkerRole.SOFTWARE_ENGINEER.value
        )
        assert picked is not None
        assert picked.id == "w2"

    def test_pick_worker_none_eligible(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1", name="A", role=WorkerRole.CEO.value, status=WorkerStatus.BUSY.value
        )
        assert s.pick_worker([w1]) is None

    def test_pick_worker_load_balancing(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1",
            name="A",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            status=WorkerStatus.IDLE.value,
            tasks_completed=10,
        )
        w2 = WorkerState(
            id="w2",
            name="B",
            role=WorkerRole.SOFTWARE_ENGINEER.value,
            status=WorkerStatus.IDLE.value,
            tasks_completed=2,
        )
        picked = s.pick_worker([w1, w2])
        assert picked.id == "w2"  # fewer completed tasks

    def test_available_workers(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1", name="A", role=WorkerRole.CEO.value, status=WorkerStatus.IDLE.value
        )
        w2 = WorkerState(
            id="w2", name="B", role=WorkerRole.CEO.value, status=WorkerStatus.BUSY.value
        )
        assert len(s.available_workers([w1, w2])) == 1

    def test_workload(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1", name="A", role=WorkerRole.CEO.value, tasks_completed=5
        )
        w2 = WorkerState(
            id="w2", name="B", role=WorkerRole.CEO.value, tasks_completed=3
        )
        wl = s.workload([w1, w2])
        assert wl == {"w1": 5, "w2": 3}

    def test_balance_score_perfect(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1",
            name="A",
            role=WorkerRole.CEO.value,
            status=WorkerStatus.IDLE.value,
            tasks_completed=5,
        )
        w2 = WorkerState(
            id="w2",
            name="B",
            role=WorkerRole.CEO.value,
            status=WorkerStatus.IDLE.value,
            tasks_completed=5,
        )
        assert s.balance_score([w1, w2]) == 0.0

    def test_balance_score_imbalanced(self) -> None:
        s = Scheduler()
        w1 = WorkerState(
            id="w1",
            name="A",
            role=WorkerRole.CEO.value,
            status=WorkerStatus.IDLE.value,
            tasks_completed=10,
        )
        w2 = WorkerState(
            id="w2",
            name="B",
            role=WorkerRole.CEO.value,
            status=WorkerStatus.IDLE.value,
            tasks_completed=0,
        )
        assert s.balance_score([w1, w2]) > 0.0

    def test_shift_count(self) -> None:
        s = Scheduler()
        s.schedule_shift("w1")
        assert s.shift_count() == 1

    def test_count_by_status(self) -> None:
        s = Scheduler()
        s.schedule_shift("w1")
        s.schedule_shift("w2")
        counts = s.count_by_status()
        assert counts[ShiftStatus.SCHEDULED.value] == 2


# ===========================================================================
# Metrics
# ===========================================================================


class TestMetrics:
    def test_record_task(self) -> None:
        m = MetricsCollector()
        m.record_task(Task(id="t1", title="Test", assignee_id="w1"))
        assert m.task_count() == 1

    def test_worker_metrics(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1",
                title="A",
                assignee_id="w1",
                status=TaskStatus.COMPLETED.value,
                quality_score=0.8,
            )
        )
        m.record_task(
            Task(id="t2", title="B", assignee_id="w1", status=TaskStatus.FAILED.value)
        )
        metrics = m.worker_metrics("w1")
        assert metrics.tasks_assigned == 2
        assert metrics.tasks_completed == 1
        assert metrics.tasks_failed == 1

    def test_all_worker_metrics(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1", title="A", assignee_id="w1", status=TaskStatus.COMPLETED.value
            )
        )
        workers = [WorkerState(id="w1", name="A", role=WorkerRole.CEO.value)]
        metrics = m.all_worker_metrics(workers)
        assert "w1" in metrics
        assert metrics["w1"].tasks_completed == 1

    def test_team_metrics(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1",
                title="A",
                team_id="t1",
                assignee_id="w1",
                status=TaskStatus.COMPLETED.value,
                quality_score=0.8,
            )
        )
        team = Team(id="t1", name="Team A", member_ids=("w1",))
        metrics = m.team_metrics(team)
        assert metrics.tasks_total == 1
        assert metrics.tasks_completed == 1

    def test_all_team_metrics(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1",
                title="A",
                team_id="t1",
                assignee_id="w1",
                status=TaskStatus.COMPLETED.value,
            )
        )
        teams = [Team(id="t1", name="Team A", member_ids=("w1",))]
        metrics = m.all_team_metrics(teams)
        assert "t1" in metrics

    def test_top_performers(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1", title="A", assignee_id="w1", status=TaskStatus.COMPLETED.value
            )
        )
        m.record_task(
            Task(
                id="t2", title="B", assignee_id="w1", status=TaskStatus.COMPLETED.value
            )
        )
        m.record_task(
            Task(
                id="t3", title="C", assignee_id="w2", status=TaskStatus.COMPLETED.value
            )
        )
        workers = [
            WorkerState(id="w1", name="A", role=WorkerRole.CEO.value),
            WorkerState(id="w2", name="B", role=WorkerRole.CEO.value),
        ]
        top = m.top_performers(workers, limit=1)
        assert top[0].worker_id == "w1"

    def test_workforce_completion_rate(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1", title="A", assignee_id="w1", status=TaskStatus.COMPLETED.value
            )
        )
        m.record_task(
            Task(id="t2", title="B", assignee_id="w1", status=TaskStatus.FAILED.value)
        )
        assert m.workforce_completion_rate() == 0.5

    def test_workforce_average_quality(self) -> None:
        m = MetricsCollector()
        m.record_task(
            Task(
                id="t1",
                title="A",
                assignee_id="w1",
                status=TaskStatus.COMPLETED.value,
                quality_score=0.8,
            )
        )
        m.record_task(
            Task(
                id="t2",
                title="B",
                assignee_id="w1",
                status=TaskStatus.COMPLETED.value,
                quality_score=0.6,
            )
        )
        assert m.workforce_average_quality() == 0.7

    def test_clear(self) -> None:
        m = MetricsCollector()
        m.record_task(Task(id="t1", title="A"))
        m.clear()
        assert m.task_count() == 0


# ===========================================================================
# Reports
# ===========================================================================


class TestReports:
    def test_generate(self) -> None:
        r = ReportGenerator()
        report = r.generate(
            workers=[
                WorkerState(
                    id="w1",
                    name="A",
                    role=WorkerRole.CEO.value,
                    status=WorkerStatus.IDLE.value,
                )
            ],
            teams=[Team(id="t1", name="Team A")],
            tasks=[
                Task(
                    id="t1",
                    title="A",
                    status=TaskStatus.COMPLETED.value,
                    quality_score=0.8,
                )
            ],
        )
        assert report.total_workers == 1
        assert report.completed_tasks == 1

    def test_summary(self) -> None:
        r = ReportGenerator()
        report = r.generate(
            workers=[],
            teams=[],
            tasks=[Task(id="t1", title="A", status=TaskStatus.COMPLETED.value)],
        )
        summary = r.summary(report)
        assert summary["total_tasks"] == 1
        assert summary["completion_rate"] == 1.0

    def test_top_workers(self) -> None:
        r = ReportGenerator()
        report = r.generate(
            workers=[],
            teams=[],
            tasks=[],
            worker_metrics={
                "w1": WorkerMetrics(worker_id="w1", tasks_completed=5),
                "w2": WorkerMetrics(worker_id="w2", tasks_completed=3),
            },
        )
        top = r.top_workers(report, limit=1)
        assert top[0].worker_id == "w1"


# ===========================================================================
# Team
# ===========================================================================


class TestTeam:
    def test_create(self) -> None:
        tm = TeamManager.create(name="Team A", goal="Build something")
        assert tm.name == "Team A"
        assert tm.goal == "Build something"

    def test_add_member(self) -> None:
        tm = TeamManager.create(name="Team A")
        tm.add_member("w1")
        assert tm.has_member("w1")
        assert tm.member_count() == 1

    def test_add_member_idempotent(self) -> None:
        tm = TeamManager.create(name="Team A")
        tm.add_member("w1")
        tm.add_member("w1")
        assert tm.member_count() == 1

    def test_remove_member(self) -> None:
        tm = TeamManager.create(name="Team A", member_ids=("w1",))
        tm.remove_member("w1")
        assert not tm.has_member("w1")

    def test_set_lead(self) -> None:
        tm = TeamManager.create(name="Team A", member_ids=("w1",))
        tm.set_lead("w1")
        assert tm.lead_id == "w1"

    def test_set_lead_non_member_raises(self) -> None:
        tm = TeamManager.create(name="Team A")
        with pytest.raises(TeamError):
            tm.set_lead("w1")

    def test_disband(self) -> None:
        tm = TeamManager.create(name="Team A")
        tm.disband()
        assert not tm.is_active

    def test_reactivate(self) -> None:
        tm = TeamManager.create(name="Team A")
        tm.disband()
        tm.reactivate()
        assert tm.is_active

    def test_online_members(self) -> None:
        tm = TeamManager.create(name="Team A", member_ids=("w1", "w2"))
        workers = [
            WorkerState(
                id="w1",
                name="A",
                role=WorkerRole.CEO.value,
                status=WorkerStatus.IDLE.value,
            ),
            WorkerState(
                id="w2",
                name="B",
                role=WorkerRole.CEO.value,
                status=WorkerStatus.OFFLINE.value,
            ),
        ]
        online = tm.online_members(workers)
        assert len(online) == 1
        assert online[0].id == "w1"

    def test_available_members(self) -> None:
        tm = TeamManager.create(name="Team A", member_ids=("w1", "w2"))
        workers = [
            WorkerState(
                id="w1",
                name="A",
                role=WorkerRole.CEO.value,
                status=WorkerStatus.IDLE.value,
            ),
            WorkerState(
                id="w2",
                name="B",
                role=WorkerRole.CEO.value,
                status=WorkerStatus.BUSY.value,
            ),
        ]
        available = tm.available_members(workers)
        assert len(available) == 1


# ===========================================================================
# WorkforceManager
# ===========================================================================


class TestWorkforceManager:
    def test_hire(self) -> None:
        m = WorkforceManager()
        w = m.hire("Alice", WorkerRole.CEO.value)
        assert w.name == "Alice"
        assert m.worker_count() == 1

    def test_fire(self) -> None:
        m = WorkforceManager()
        w = m.hire("Alice", WorkerRole.CEO.value)
        assert m.fire(w.id) is True
        assert m.worker_count() == 0

    def test_fire_unknown(self) -> None:
        m = WorkforceManager()
        assert m.fire("missing") is False

    def test_get_worker(self) -> None:
        m = WorkforceManager()
        w = m.hire("Alice", WorkerRole.CEO.value)
        assert m.get_worker(w.id) is w

    def test_list_workers(self) -> None:
        m = WorkforceManager()
        m.hire("Alice", WorkerRole.CEO.value)
        m.hire("Bob", WorkerRole.CTO.value)
        assert len(m.list_workers()) == 2

    def test_list_workers_by_role(self) -> None:
        m = WorkforceManager()
        m.hire("Alice", WorkerRole.CEO.value)
        m.hire("Bob", WorkerRole.CTO.value)
        assert len(m.list_workers(role=WorkerRole.CEO.value)) == 1

    def test_online_workers(self) -> None:
        m = WorkforceManager()
        w = m.hire("Alice", WorkerRole.CEO.value)
        w.start()
        assert len(m.online_workers()) == 1

    def test_idle_workers(self) -> None:
        m = WorkforceManager()
        w = m.hire("Alice", WorkerRole.CEO.value)
        w.start()
        assert len(m.idle_workers()) == 1

    def test_hire_executive(self) -> None:
        m = WorkforceManager()
        w = m.hire_executive("Alice", WorkerRole.CEO.value)
        assert w.role == WorkerRole.CEO.value

    def test_hire_executive_invalid(self) -> None:
        m = WorkforceManager()
        with pytest.raises(WorkerError):
            m.hire_executive("Alice", WorkerRole.SOFTWARE_ENGINEER.value)

    def test_hire_engineer(self) -> None:
        m = WorkforceManager()
        w = m.hire_engineer("Bob")
        assert w.role == WorkerRole.SOFTWARE_ENGINEER.value

    def test_hire_agent(self) -> None:
        m = WorkforceManager()
        w = m.hire_agent("Browser")
        assert w.state.kind == WorkerKind.TEMPORARY.value

    def test_hire_temporary(self) -> None:
        m = WorkforceManager()
        w = m.hire_temporary("Temp", WorkerRole.SOFTWARE_ENGINEER.value)
        assert w.state.kind == WorkerKind.TEMPORARY.value

    def test_create_team(self) -> None:
        m = WorkforceManager()
        w1 = m.hire("Alice", WorkerRole.CEO.value)
        w2 = m.hire("Bob", WorkerRole.SOFTWARE_ENGINEER.value)
        tm = m.create_team("Team A", member_ids=(w1.id, w2.id))
        assert tm.member_count() == 2

    def test_create_team_unknown_member_raises(self) -> None:
        m = WorkforceManager()
        with pytest.raises(WorkerError):
            m.create_team("Team A", member_ids=("missing",))

    def test_disband_team(self) -> None:
        m = WorkforceManager()
        tm = m.create_team("Team A")
        assert m.disband_team(tm.id) is True
        assert not tm.is_active

    def test_status(self) -> None:
        m = WorkforceManager()
        m.hire("Alice", WorkerRole.CEO.value)
        status = m.status()
        assert status["total_workers"] == 1

    def test_start_all(self) -> None:
        m = WorkforceManager()
        m.hire("Alice", WorkerRole.CEO.value)
        m.hire("Bob", WorkerRole.CTO.value)
        m.start_all()
        assert len(m.online_workers()) == 2

    def test_stop_all(self) -> None:
        m = WorkforceManager()
        m.hire("Alice", WorkerRole.CEO.value)
        m.start_all()
        m.stop_all()
        assert len(m.online_workers()) == 0


# ===========================================================================
# WorkforceOrchestrator
# ===========================================================================


class TestOrchestrator:
    def test_construct(self) -> None:
        o = WorkforceOrchestrator()
        assert o is not None

    def test_hire(self) -> None:
        o = WorkforceOrchestrator()
        w = o.hire("Alice", WorkerRole.CEO.value)
        assert w.name == "Alice"

    def test_hire_default_workforce(self) -> None:
        o = WorkforceOrchestrator()
        hired = o.hire_default_workforce()
        assert len(hired) == 17

    def test_execute_goal(self) -> None:
        o = WorkforceOrchestrator()
        o.hire_default_workforce()
        report = o.execute_goal("Build a hello world app")
        assert report.total_workers == 17
        assert report.total_tasks > 0

    def test_execute_goal_with_think_fn(self) -> None:
        calls: list[str] = []

        def fake_think(**kwargs: object) -> str:
            calls.append(str(kwargs.get("goal_description", "")))
            return "done"

        o = WorkforceOrchestrator(think_fn=fake_think)
        o.hire_default_workforce()
        o.execute_goal("Test goal")
        assert len(calls) > 0

    def test_status(self) -> None:
        o = WorkforceOrchestrator()
        o.hire_default_workforce()
        status = o.status()
        assert status["manager"]["total_workers"] == 17

    def test_get_task(self) -> None:
        o = WorkforceOrchestrator()
        o.hire_default_workforce()
        o.execute_goal("Test")
        tasks = o.all_tasks()
        assert len(tasks) > 0
        assert o.get_task(tasks[0].id) is not None

    def test_task_count(self) -> None:
        o = WorkforceOrchestrator()
        o.hire_default_workforce()
        o.execute_goal("Test")
        assert o.task_count() > 0

    def test_engines_present(self) -> None:
        o = WorkforceOrchestrator()
        assert o.planning is not None
        assert o.coordination is not None
        assert o.review is not None
        assert o.learning is not None
        assert o.supervisor is not None
        assert o.scheduler is not None
        assert o.metrics is not None
        assert o.reports is not None
        assert o.communication is not None
        assert o.delegation is not None

    def test_no_brain_import(self) -> None:
        """The workforce package must not import Brain or any subsystem.

        The only exception is the ``has_brain()`` helper in
        ``__init__.py`` which does a lazy import check — that is the
        sanctioned bridge to the Brain, not a coupling.
        """
        import os
        import re

        import atlas.workforce

        root = os.path.dirname(atlas.workforce.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|providers|mcp|memory|knowledge|workflows|tools|integration|agents|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline)\b"
        )
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                # Allow the __init__.py has_brain() lazy import check
                is_init = os.path.basename(path) == "__init__.py"
                with open(path, encoding='utf-8') as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            if (
                                is_init
                                and "brain" in line
                                and "has_brain" in open(path, encoding='utf-8').read()
                            ):
                                # The has_brain() helper does a lazy import check — allowed
                                continue
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert (
            not offenders
        ), "atlas.workforce imports other Atlas subsystems:\n" + "\n".join(offenders)


# ===========================================================================
# End-to-end integration
# ===========================================================================


class TestIntegration:
    def test_full_workforce_scenario(self) -> None:
        """End-to-end: hire workforce → execute goal → verify report."""
        o = WorkforceOrchestrator()
        o.hire_default_workforce()
        report = o.execute_goal(
            "Build a web app",
            reviewer_id=o.manager.list_workers(role=WorkerRole.QA_ENGINEER.value)[0].id,
        )
        assert report.total_workers == 17
        assert report.total_tasks > 0
        assert report.completed_tasks > 0

    def test_delegation_scenario(self) -> None:
        """CEO delegates to SWE, SWE accepts."""
        o = WorkforceOrchestrator()
        ceo = o.hire("CEO", WorkerRole.CEO.value)
        swe = o.hire("SWE", WorkerRole.SOFTWARE_ENGINEER.value)
        ceo.start()
        swe.start()
        d = o.delegation.delegate(
            from_worker_id=ceo.id,
            to_worker_id=swe.id,
            task_id="t1",
            from_role=WorkerRole.CEO.value,
            to_role=WorkerRole.SOFTWARE_ENGINEER.value,
        )
        o.delegation.accept(d.id)
        assert o.delegation.count() == 1
        assert len(o.delegation.accepted()) == 1

    def test_escalation_scenario(self) -> None:
        """Worker escalates to supervisor, supervisor resolves."""
        o = WorkforceOrchestrator()
        w = o.hire("Worker", WorkerRole.SOFTWARE_ENGINEER.value)
        w.start()
        e = o.supervisor.escalate(
            from_worker_id=w.id,
            message="I need help with the database",
            level=EscalationLevel.HIGH.value,
        )
        assert o.supervisor.pending_count() == 1
        o.supervisor.resolve_escalation(e.id, resolution="Helped the worker")
        assert o.supervisor.pending_count() == 0

    def test_conflict_resolution_scenario(self) -> None:
        """Two workers conflict over a resource, supervisor mediates."""
        o = WorkforceOrchestrator()
        w1 = o.hire("W1", WorkerRole.SOFTWARE_ENGINEER.value)
        w2 = o.hire("W2", WorkerRole.SOFTWARE_ENGINEER.value)
        c = o.supervisor.report_conflict(
            kind=ConflictKind.RESOURCE.value,
            worker_ids=(w1.id, w2.id),
            description="Both need the same file",
        )
        o.supervisor.resolve_conflict(
            c.id, resolution=ConflictResolution.MEDIATED.value
        )
        assert len(o.supervisor.resolved_conflicts()) == 1

    def test_review_scenario(self) -> None:
        """Worker completes task, QA reviews and approves."""
        o = WorkforceOrchestrator()
        swe = o.hire("SWE", WorkerRole.SOFTWARE_ENGINEER.value)
        qa = o.hire("QA", WorkerRole.QA_ENGINEER.value)
        swe.start()
        qa.start()
        task = Task(id="t1", title="Implement feature", assignee_id=swe.id)
        swe.assign_task(task)
        swe.execute_task(task)
        swe.complete_task(task)
        review = o.review.submit_review(
            task_id=task.id,
            reviewer_id=qa.id,
            verdict=ReviewVerdict.APPROVED.value,
            quality_score=0.9,
        )
        assert o.review.is_approved(task.id)

    def test_learning_scenario(self) -> None:
        """Worker learns a lesson that boosts their skill."""
        o = WorkforceOrchestrator()
        w = o.hire("W", WorkerRole.SOFTWARE_ENGINEER.value)
        original_level = w.skill_level("python")
        lesson = o.learning.record_lesson(
            worker_id=w.id,
            description="Learned a new python pattern",
            skill_name="python",
            impact=0.1,
        )
        new_skills = o.learning.apply_lesson(lesson.id, w.skills())
        new_level = next(s.level for s in new_skills if s.name == "python")
        assert new_level > original_level


# ===========================================================================
# Package import test
# ===========================================================================


class TestPackageImports:
    def test_import_atlas_workforce(self) -> None:
        import atlas.workforce

        assert atlas.workforce.__version__ == "1.0.0"

    def test_reload(self) -> None:
        import importlib

        import atlas.workforce

        importlib.reload(atlas.workforce)
        assert atlas.workforce.__version__ == "1.0.0"
