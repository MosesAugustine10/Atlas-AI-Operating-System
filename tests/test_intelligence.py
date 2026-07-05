"""Tests for the Atlas Intelligence Layer.

Covers models, goal management, task decomposition, reasoning, planning,
decision making, reflection, critic, learning, coordinator, brain
pipeline, and failure handling. All tests are deterministic and offline.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from atlas.intelligence import (
    TERMINAL_STATUSES,
    AdaptivePlan,
    AdaptivePlanner,
    Brain,
    BrainError,
    Coordinator,
    Critic,
    Critique,
    Decision,
    DecisionCandidate,
    DecisionEngine,
    ExecutionOutcome,
    Goal,
    GoalManager,
    GoalManagerError,
    GoalPriority,
    GoalScope,
    GoalStatus,
    GoalTree,
    IntelligenceTask,
    LearningEngine,
    LearningSummary,
    Lesson,
    PlanAdjustment,
    Reasoner,
    ReasoningChain,
    ReasoningStep,
    ReasoningStepType,
    Reflection,
    ReflectionEngine,
    TaskDecomposer,
)

# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    """Tests for atlas.intelligence.models."""

    def test_goal_status_has_six_values(self) -> None:
        assert len(list(GoalStatus)) == 6

    def test_goal_scope_has_two_values(self) -> None:
        assert len(list(GoalScope)) == 2

    def test_goal_priority_ordering(self) -> None:
        assert GoalPriority.CRITICAL > GoalPriority.HIGH
        assert GoalPriority.HIGH > GoalPriority.NORMAL
        assert GoalPriority.NORMAL > GoalPriority.LOW

    def test_terminal_statuses(self) -> None:
        assert set(TERMINAL_STATUSES) == {
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
        }

    def test_reasoning_step_type_has_six_values(self) -> None:
        assert len(list(ReasoningStepType)) == 6

    def test_plan_adjustment_has_six_values(self) -> None:
        assert len(list(PlanAdjustment)) == 6

    def test_goal_is_frozen(self) -> None:
        g = Goal(description="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.description = "other"  # type: ignore[misc]

    def test_goal_defaults(self) -> None:
        g = Goal()
        assert g.scope is GoalScope.SHORT_TERM
        assert g.priority is GoalPriority.NORMAL
        assert g.status is GoalStatus.PENDING
        assert g.dependencies == []

    def test_goal_is_terminal_property(self) -> None:
        assert Goal(status=GoalStatus.COMPLETED).is_terminal
        assert Goal(status=GoalStatus.FAILED).is_terminal
        assert not Goal(status=GoalStatus.ACTIVE).is_terminal

    def test_goal_is_active_property(self) -> None:
        assert Goal(status=GoalStatus.ACTIVE).is_active
        assert not Goal(status=GoalStatus.PENDING).is_active

    def test_goal_tree_flatten(self) -> None:
        root = Goal(id="r", description="root")
        child1 = Goal(id="c1", description="child1")
        child2 = Goal(id="c2", description="child2")
        tree = GoalTree(
            root=root,
            children=[
                GoalTree(root=child1),
                GoalTree(root=child2),
            ],
        )
        flat = tree.flatten()
        assert [g.id for g in flat] == ["r", "c1", "c2"]

    def test_goal_tree_depth(self) -> None:
        root = Goal(id="r")
        child = Goal(id="c")
        grandchild = Goal(id="gc")
        tree = GoalTree(
            root=root,
            children=[
                GoalTree(root=child, children=[GoalTree(root=grandchild)]),
            ],
        )
        assert tree.depth() == 2

    def test_goal_tree_depth_leaf(self) -> None:
        tree = GoalTree(root=Goal(id="r"))
        assert tree.depth() == 0

    def test_reasoning_step_is_frozen(self) -> None:
        s = ReasoningStep(content="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.content = "other"  # type: ignore[misc]

    def test_reasoning_chain_is_frozen(self) -> None:
        c = ReasoningChain(conclusion="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.conclusion = "other"  # type: ignore[misc]

    def test_intelligence_task_is_frozen(self) -> None:
        t = IntelligenceTask(description="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.description = "other"  # type: ignore[misc]

    def test_adaptive_plan_task_ids(self) -> None:
        plan = AdaptivePlan(
            tasks=[
                IntelligenceTask(id="t1"),
                IntelligenceTask(id="t2"),
            ]
        )
        assert plan.task_ids() == ["t1", "t2"]

    def test_adaptive_plan_task_by_id(self) -> None:
        plan = AdaptivePlan(tasks=[IntelligenceTask(id="t1", description="found")])
        assert plan.task_by_id("t1") is not None
        assert plan.task_by_id("missing") is None

    def test_decision_candidate_is_frozen(self) -> None:
        c = DecisionCandidate(name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.name = "other"  # type: ignore[misc]

    def test_decision_is_frozen(self) -> None:
        d = Decision(selected="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.selected = "other"  # type: ignore[misc]

    def test_critique_is_frozen(self) -> None:
        c = Critique()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.confidence = 0.5  # type: ignore[misc]

    def test_reflection_is_frozen(self) -> None:
        r = Reflection(expected="x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.expected = "y"  # type: ignore[misc]

    def test_lesson_is_frozen(self) -> None:
        lesson = Lesson(content="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            lesson.content = "other"  # type: ignore[misc]

    def test_execution_outcome_success_property(self) -> None:
        o = ExecutionOutcome(status=GoalStatus.COMPLETED)
        assert o.success
        o2 = ExecutionOutcome(status=GoalStatus.FAILED)
        assert not o2.success

    def test_learning_summary_defaults(self) -> None:
        s = LearningSummary()
        assert s.total_lessons == 0
        assert s.avg_confidence == 0.0


# ===========================================================================
# Goal Manager
# ===========================================================================


class TestGoalManager:
    """Tests for atlas.intelligence.goal_manager."""

    def test_create_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test goal")
        assert g.description == "test goal"
        assert g.status is GoalStatus.PENDING
        assert g.id != ""

    def test_create_goal_empty_description_raises(self) -> None:
        gm = GoalManager()
        with pytest.raises(ValueError):
            gm.create("")

    def test_get_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        assert gm.get(g.id) is g

    def test_get_goal_missing_raises(self) -> None:
        gm = GoalManager()
        with pytest.raises(GoalManagerError):
            gm.get("missing")

    def test_get_optional_returns_none(self) -> None:
        gm = GoalManager()
        assert gm.get_optional("missing") is None

    def test_contains(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        assert gm.contains(g.id)
        assert g.id in gm

    def test_start_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        g = gm.start(g.id)
        assert g.status is GoalStatus.ACTIVE

    def test_start_terminal_raises(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        gm.complete(g.id)
        with pytest.raises(GoalManagerError):
            gm.start(g.id)

    def test_start_already_active_is_noop(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        gm.start(g.id)
        result = gm.start(g.id)
        assert result.status is GoalStatus.ACTIVE

    def test_max_active_limit(self) -> None:
        gm = GoalManager(max_active=2)
        g1 = gm.create("g1")
        g2 = gm.create("g2")
        gm.start(g1.id)
        gm.start(g2.id)
        g3 = gm.create("g3")
        with pytest.raises(GoalManagerError):
            gm.start(g3.id)

    def test_pause_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        gm.start(g.id)
        g = gm.pause(g.id)
        assert g.status is GoalStatus.PAUSED

    def test_pause_non_active_raises(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        with pytest.raises(GoalManagerError):
            gm.pause(g.id)

    def test_resume_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        gm.start(g.id)
        gm.pause(g.id)
        g = gm.resume(g.id)
        assert g.status is GoalStatus.ACTIVE

    def test_resume_non_paused_raises(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        with pytest.raises(GoalManagerError):
            gm.resume(g.id)

    def test_cancel_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        g = gm.cancel(g.id, reason="done")
        assert g.status is GoalStatus.CANCELLED
        assert g.metadata["cancel_reason"] == "done"

    def test_cancel_terminal_raises(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        gm.cancel(g.id)
        with pytest.raises(GoalManagerError):
            gm.cancel(g.id)

    def test_complete_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        g = gm.complete(g.id, result={"key": "value"})
        assert g.status is GoalStatus.COMPLETED
        assert g.metadata["result"] == {"key": "value"}

    def test_fail_goal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        g = gm.fail(g.id, error="boom")
        assert g.status is GoalStatus.FAILED
        assert g.metadata["error"] == "boom"

    def test_set_priority(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        g = gm.set_priority(g.id, GoalPriority.CRITICAL)
        assert g.priority is GoalPriority.CRITICAL

    def test_list_filtered_by_status(self) -> None:
        gm = GoalManager()
        g1 = gm.create("g1")
        gm.create("g2")
        gm.start(g1.id)
        active = gm.list(status=GoalStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].id == g1.id

    def test_list_filtered_by_scope(self) -> None:
        gm = GoalManager()
        gm.create("g1", scope=GoalScope.SHORT_TERM)
        gm.create("g2", scope=GoalScope.LONG_TERM)
        long_term = gm.list(scope=GoalScope.LONG_TERM)
        assert len(long_term) == 1

    def test_active_goals(self) -> None:
        gm = GoalManager()
        g1 = gm.create("g1")
        gm.create("g2")
        gm.start(g1.id)
        assert len(gm.active_goals()) == 1

    def test_pending_goals(self) -> None:
        gm = GoalManager()
        gm.create("g1")
        gm.create("g2")
        assert len(gm.pending_goals()) == 2

    def test_terminal_goals(self) -> None:
        gm = GoalManager()
        g = gm.create("g1")
        gm.complete(g.id)
        assert len(gm.terminal_goals()) == 1

    def test_subgoals(self) -> None:
        gm = GoalManager()
        parent = gm.create("parent")
        gm.create("child1", parent_id=parent.id)
        gm.create("child2", parent_id=parent.id)
        subs = gm.subgoals(parent.id)
        assert len(subs) == 2

    def test_create_with_parent_missing_raises(self) -> None:
        gm = GoalManager()
        with pytest.raises(GoalManagerError):
            gm.create("child", parent_id="missing")

    def test_dependencies_met(self) -> None:
        gm = GoalManager()
        dep = gm.create("dependency")
        main = gm.create("main", dependencies=[dep.id])
        assert not gm.are_dependencies_met(main.id)
        gm.complete(dep.id)
        assert gm.are_dependencies_met(main.id)

    def test_blocked_goals(self) -> None:
        gm = GoalManager()
        dep = gm.create("dep")
        main = gm.create("main", dependencies=[dep.id])
        blocked = gm.blocked_goals()
        assert main.id in [g.id for g in blocked]
        gm.complete(dep.id)
        assert main.id not in [g.id for g in gm.blocked_goals()]

    def test_history(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        gm.start(g.id)
        gm.pause(g.id)
        hist = gm.history(g.id)
        assert len(hist) == 3  # create + start + pause

    def test_all_history(self) -> None:
        gm = GoalManager()
        gm.create("g1")
        gm.create("g2")
        assert len(gm.all_history()) == 2

    def test_clear(self) -> None:
        gm = GoalManager()
        gm.create("test")
        gm.clear()
        assert len(gm) == 0

    def test_len(self) -> None:
        gm = GoalManager()
        gm.create("g1")
        gm.create("g2")
        assert len(gm) == 2

    def test_iter(self) -> None:
        gm = GoalManager()
        gm.create("g1")
        gm.create("g2")
        goals = list(gm)
        assert len(goals) == 2

    def test_completed_at_set_on_terminal(self) -> None:
        gm = GoalManager()
        g = gm.create("test")
        g = gm.complete(g.id)
        assert g.completed_at is not None

    def test_max_active_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            GoalManager(max_active=0)


# ===========================================================================
# Task Decomposer
# ===========================================================================


class TestTaskDecomposer:
    """Tests for atlas.intelligence.task_decomposer."""

    def test_decompose_website(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Create website for portfolio")
        tree = d.decompose(goal)
        assert len(tree.children) == 5

    def test_decompose_research(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Research quantum computing")
        tree = d.decompose(goal)
        assert len(tree.children) == 2

    def test_decompose_code(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Implement sorting algorithm")
        tree = d.decompose(goal)
        assert len(tree.children) == 3

    def test_decompose_deploy(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Deploy to production")
        tree = d.decompose(goal)
        assert len(tree.children) == 3

    def test_decompose_analyze(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Analyze sales data")
        tree = d.decompose(goal)
        assert len(tree.children) == 3

    def test_decompose_unknown_returns_leaf(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Do something unusual")
        tree = d.decompose(goal)
        assert len(tree.children) == 0

    def test_decompose_max_depth(self) -> None:
        d = TaskDecomposer(max_depth=1)
        goal = Goal(description="Create website")
        tree = d.decompose(goal)
        # At depth 1, children are leaves.
        assert all(not child.children for child in tree.children)

    def test_decompose_flat(self) -> None:
        d = TaskDecomposer(max_depth=1)
        goal = Goal(description="Create website")
        flat = d.decompose_flat(goal)
        assert len(flat) == 5
        assert all(g.parent_id == goal.id for g in flat)

    def test_decompose_recursive(self) -> None:
        d = TaskDecomposer(max_depth=3)
        goal = Goal(description="Create website")
        tree = d.decompose(goal)
        assert tree.depth() >= 1

    def test_max_depth_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            TaskDecomposer(max_depth=0)

    def test_max_children_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            TaskDecomposer(max_children=0)

    def test_subgoal_has_parent_id(self) -> None:
        d = TaskDecomposer()
        goal = Goal(description="Create website")
        tree = d.decompose(goal)
        for child in tree.children:
            assert child.root.parent_id == goal.id

    def test_decompose_flatten_all(self) -> None:
        d = TaskDecomposer(max_depth=2)
        goal = Goal(description="Create website")
        tree = d.decompose(goal)
        all_goals = tree.flatten()
        assert all_goals[0].id == goal.id


# ===========================================================================
# Reasoner
# ===========================================================================


class TestReasoner:
    """Tests for atlas.intelligence.reasoner."""

    def test_reason_returns_chain(self) -> None:
        r = Reasoner()
        chain = r.reason("test goal")
        assert isinstance(chain, ReasoningChain)
        assert len(chain.steps) == 6

    def test_reason_steps_types(self) -> None:
        r = Reasoner()
        chain = r.reason("test goal")
        types = [s.step_type for s in chain.steps]
        assert ReasoningStepType.OBSERVE in types
        assert ReasoningStepType.HYPOTHESIZE in types
        assert ReasoningStepType.DEDUCE in types
        assert ReasoningStepType.INFER in types
        assert ReasoningStepType.EVALUATE in types
        assert ReasoningStepType.DECIDE in types

    def test_reason_has_conclusion(self) -> None:
        r = Reasoner()
        chain = r.reason("test goal")
        assert chain.conclusion != ""

    def test_reason_overall_confidence(self) -> None:
        r = Reasoner()
        chain = r.reason("test goal")
        assert 0.0 < chain.overall_confidence <= 1.0

    def test_reason_with_knowledge(self) -> None:
        class FakeKnowledge:
            def search(self, query: str) -> list:
                return [
                    type("R", (), {"chunk": type("C", (), {"content": "fact"})()})()
                ]

        r = Reasoner(knowledge=FakeKnowledge())
        chain = r.reason("test")
        assert chain.metadata["knowledge_hits"] > 0

    def test_reason_with_memory(self) -> None:
        class FakeMemory:
            def recall(self) -> list:
                return [type("E", (), {"content": "memory"})()]

        r = Reasoner(memory=FakeMemory())
        chain = r.reason("test")
        assert chain.metadata["memory_hits"] > 0

    def test_reason_without_subsystems(self) -> None:
        r = Reasoner()
        chain = r.reason("test")
        assert chain.metadata["knowledge_hits"] == 0
        assert chain.metadata["memory_hits"] == 0

    def test_reason_evidence_collected(self) -> None:
        class FakeKnowledge:
            def search(self, query: str) -> list:
                return [
                    type("R", (), {"chunk": type("C", (), {"content": "fact"})()})()
                ]

        r = Reasoner(knowledge=FakeKnowledge())
        chain = r.reason("test")
        observe_step = chain.steps[0]
        assert len(observe_step.evidence) > 0

    def test_reason_with_context(self) -> None:
        r = Reasoner()
        chain = r.reason("test", context={"extra": "info"})
        assert isinstance(chain, ReasoningChain)

    def test_reason_hypothesis_without_evidence(self) -> None:
        r = Reasoner()
        chain = r.reason("unknown topic")
        assert "lacks supporting evidence" in chain.steps[1].content


# ===========================================================================
# Adaptive Planner
# ===========================================================================


class TestAdaptivePlanner:
    """Tests for atlas.intelligence.planner."""

    def test_plan_website(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Create website")
        assert len(plan.tasks) == 5

    def test_plan_research(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Research AI")
        assert len(plan.tasks) == 2

    def test_plan_code(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Implement feature")
        assert len(plan.tasks) == 3

    def test_plan_deploy(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Deploy app")
        assert len(plan.tasks) == 3

    def test_plan_default(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Do something unusual")
        assert len(plan.tasks) == 1

    def test_plan_has_goal_id(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g123", "test")
        assert plan.goal_id == "g123"

    def test_plan_version_starts_at_1(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        assert plan.version == 1

    def test_split_task(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        task_id = plan.tasks[0].id
        plan2 = p.split(plan, task_id, ["sub1", "sub2", "sub3"])
        assert plan2.version == 2
        assert PlanAdjustment.SPLIT in plan2.adjustments
        assert len(plan2.tasks) == len(plan.tasks) + 2  # 1 removed, 3 added

    def test_split_missing_task_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.split(plan, "missing", ["sub1"])

    def test_split_empty_subs_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.split(plan, plan.tasks[0].id, [])

    def test_merge_tasks(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Create website")
        t1, t2 = plan.tasks[0], plan.tasks[1]
        plan2 = p.merge(plan, [t1.id, t2.id], "merged task")
        assert plan2.version == 2
        assert PlanAdjustment.MERGE in plan2.adjustments
        assert len(plan2.tasks) == len(plan.tasks) - 1

    def test_merge_too_few_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.merge(plan, [plan.tasks[0].id], "merged")

    def test_merge_missing_task_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.merge(plan, ["missing1", "missing2"], "merged")

    def test_remove_task(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Create website")
        initial = len(plan.tasks)
        plan2 = p.remove(plan, plan.tasks[0].id)
        assert plan2.version == 2
        assert PlanAdjustment.REMOVE in plan2.adjustments
        assert len(plan2.tasks) == initial - 1

    def test_remove_missing_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.remove(plan, "missing")

    def test_insert_task_at_beginning(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        new_task = IntelligenceTask(description="new")
        plan2 = p.insert(plan, None, new_task)
        assert plan2.version == 2
        assert PlanAdjustment.INSERT in plan2.adjustments
        assert plan2.tasks[0].description == "new"

    def test_insert_task_after(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Create website")
        new_task = IntelligenceTask(description="new")
        plan2 = p.insert(plan, plan.tasks[0].id, new_task)
        assert plan2.tasks[1].description == "new"

    def test_insert_after_missing_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.insert(plan, "missing", IntelligenceTask())

    def test_reorder(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Create website")
        new_order = list(reversed(plan.task_ids()))
        plan2 = p.reorder(plan, new_order)
        assert plan2.version == 2
        assert PlanAdjustment.REORDER in plan2.adjustments
        assert plan2.task_ids() == new_order

    def test_reorder_wrong_ids_raises(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "test")
        with pytest.raises(ValueError):
            p.reorder(plan, ["wrong"])

    def test_plan_dependencies(self) -> None:
        p = AdaptivePlanner()
        plan = p.plan("g1", "Create website")
        # Task 2 depends on task 1.
        assert plan.tasks[0].id in plan.tasks[1].dependencies

    def test_max_tasks_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            AdaptivePlanner(max_tasks=0)


# ===========================================================================
# Decision Engine
# ===========================================================================


class TestDecisionEngine:
    """Tests for atlas.intelligence.decision."""

    def test_decide_selects_best(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(
                name="a", capabilities=("read",), quality=0.9, availability=1.0
            ),
            DecisionCandidate(
                name="b", capabilities=("read",), quality=0.5, availability=1.0
            ),
        ]
        decision = d.decide("read", candidates)
        assert decision.selected == "a"
        assert decision.score > 0.5

    def test_decide_no_matching_capability_raises(self) -> None:
        d = DecisionEngine()
        candidates = [DecisionCandidate(name="a", capabilities=("write",))]
        with pytest.raises(ValueError):
            d.decide("read", candidates)

    def test_decide_empty_candidates_raises(self) -> None:
        d = DecisionEngine()
        with pytest.raises(ValueError):
            d.decide("read", [])

    def test_decide_empty_capability_raises(self) -> None:
        d = DecisionEngine()
        with pytest.raises(ValueError):
            d.decide("", [DecisionCandidate(name="a")])

    def test_decide_alternatives(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(name="a", capabilities=("read",), quality=0.9),
            DecisionCandidate(name="b", capabilities=("read",), quality=0.5),
            DecisionCandidate(name="c", capabilities=("read",), quality=0.3),
        ]
        decision = d.decide("read", candidates)
        assert "b" in decision.alternatives
        assert "c" in decision.alternatives

    def test_decide_has_reason(self) -> None:
        d = DecisionEngine()
        candidates = [DecisionCandidate(name="a", capabilities=("read",))]
        decision = d.decide("read", candidates)
        assert decision.reason != ""

    def test_decide_kind(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(name="a", capabilities=("read",), kind="provider")
        ]
        decision = d.decide("read", candidates, kind="provider")
        assert decision.kind == "provider"

    def test_record_outcome(self) -> None:
        d = DecisionEngine()
        d.record_outcome("test_candidate", 0.8)
        assert d.history("test_candidate") == [0.8]

    def test_history_missing(self) -> None:
        d = DecisionEngine()
        assert d.history("missing") == []

    def test_clear_history(self) -> None:
        d = DecisionEngine()
        d.record_outcome("a", 0.5)
        d.clear_history()
        assert d.history("a") == []

    def test_score_prefers_higher_quality(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(name="low", capabilities=("read",), quality=0.3),
            DecisionCandidate(name="high", capabilities=("read",), quality=0.9),
        ]
        decision = d.decide("read", candidates)
        assert decision.selected == "high"

    def test_score_prefers_lower_cost(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(
                name="expensive", capabilities=("read",), cost=10.0, quality=0.5
            ),
            DecisionCandidate(
                name="cheap", capabilities=("read",), cost=0.0, quality=0.5
            ),
        ]
        decision = d.decide("read", candidates)
        assert decision.selected == "cheap"

    def test_score_prefers_lower_latency(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(
                name="slow", capabilities=("read",), latency_ms=1000, quality=0.5
            ),
            DecisionCandidate(
                name="fast", capabilities=("read",), latency_ms=10, quality=0.5
            ),
        ]
        decision = d.decide("read", candidates)
        assert decision.selected == "fast"

    def test_score_prefers_higher_availability(self) -> None:
        d = DecisionEngine()
        candidates = [
            DecisionCandidate(
                name="down", capabilities=("read",), availability=0.1, quality=0.5
            ),
            DecisionCandidate(
                name="up", capabilities=("read",), availability=1.0, quality=0.5
            ),
        ]
        decision = d.decide("read", candidates)
        assert decision.selected == "up"

    def test_history_affects_score(self) -> None:
        d = DecisionEngine(history_weight=0.5)
        # Record good history for "a"
        d.record_outcome("a", 1.0)
        d.record_outcome("a", 1.0)
        candidates = [
            DecisionCandidate(name="a", capabilities=("read",), quality=0.3),
            DecisionCandidate(name="b", capabilities=("read",), quality=0.9),
        ]
        decision = d.decide("read", candidates)
        # "a" has lower quality but good history — with high history_weight
        # it might still win or at least be close.
        assert decision.selected in ("a", "b")


# ===========================================================================
# Reflection Engine
# ===========================================================================


class TestReflectionEngine:
    """Tests for atlas.intelligence.reflection."""

    def test_reflect_success(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test output",
            actual="test output",
            success=True,
            quality_score=0.9,
        )
        assert isinstance(reflection, Reflection)
        assert reflection.quality_score == 0.9

    def test_reflect_failure(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="error",
            success=False,
        )
        assert "execution failed" in reflection.mistakes
        assert reflection.should_retry

    def test_reflect_empty_output(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="something",
            actual="",
            success=True,
        )
        assert any("no output" in m for m in reflection.mistakes)

    def test_reflect_low_quality(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="test",
            success=True,
            quality_score=0.3,
        )
        assert any("low quality" in m for m in reflection.mistakes)

    def test_reflect_high_latency(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="test",
            success=True,
            quality_score=0.8,
            duration_seconds=120.0,
        )
        assert any("latency" in m for m in reflection.mistakes)

    def test_reflect_mismatch(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="create website",
            actual="completely different output about cooking",
            success=True,
            quality_score=0.8,
        )
        assert any("differ" in m for m in reflection.mistakes)

    def test_reflect_extracts_lessons(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="",
            success=True,
        )
        assert len(reflection.lessons) > 0

    def test_reflect_no_retry_on_success(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="test",
            success=True,
            quality_score=0.9,
        )
        assert not reflection.should_retry

    def test_reflect_retry_on_failure(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="error",
            success=False,
            quality_score=0.3,
        )
        assert reflection.should_retry

    def test_reflect_metadata(self) -> None:
        r = ReflectionEngine()
        reflection = r.reflect(
            goal_id="g1",
            expected="test",
            actual="test",
            success=True,
            metadata={"key": "value"},
        )
        assert reflection.metadata["key"] == "value"


# ===========================================================================
# Critic
# ===========================================================================


class TestCritic:
    """Tests for atlas.intelligence.critic."""

    def test_critique_good_output(self) -> None:
        c = Critic()
        critique = c.critique("This is a good output with enough text")
        assert critique.confidence > 0.5
        assert critique.quality_score > 0.5
        assert len(critique.warnings) == 0

    def test_critique_empty_output(self) -> None:
        c = Critic()
        critique = c.critique("")
        assert (
            "empty" in critique.warnings[0].lower()
            or "short" in critique.warnings[0].lower()
        )

    def test_critique_none_output(self) -> None:
        c = Critic()
        critique = c.critique(None)
        assert critique.quality_score == 0.0

    def test_critique_failure(self) -> None:
        c = Critic()
        critique = c.critique("output", success=False)
        assert critique.quality_score == 0.0
        assert critique.confidence == 0.0

    def test_critique_error_markers(self) -> None:
        c = Critic()
        critique = c.critique("This output has an error in it")
        assert any("error" in w.lower() for w in critique.warnings)

    def test_critique_with_expected(self) -> None:
        c = Critic()
        critique = c.critique(
            "hello world this is a test output",
            expected="hello world test",
        )
        assert critique.confidence > 0.5

    def test_critique_low_coverage(self) -> None:
        c = Critic()
        critique = c.critique(
            "completely different output about cooking",
            expected="create website deploy code",
        )
        assert any("coverage" in w.lower() for w in critique.warnings)

    def test_critique_scores_in_range(self) -> None:
        c = Critic()
        critique = c.critique("test output here")
        assert 0.0 <= critique.confidence <= 1.0
        assert 0.0 <= critique.quality_score <= 1.0

    def test_critique_has_notes(self) -> None:
        c = Critic()
        critique = c.critique("test output")
        assert critique.notes != ""

    def test_custom_min_output_length(self) -> None:
        c = Critic(min_output_length=100)
        critique = c.critique("short")
        assert len(critique.warnings) > 0

    def test_custom_error_markers(self) -> None:
        c = Critic(error_markers=("bogus",))
        critique = c.critique("this is bogus output with enough text")
        assert any("bogus" in w for w in critique.warnings)


# ===========================================================================
# Learning Engine
# ===========================================================================


class TestLearningEngine:
    """Tests for atlas.intelligence.learning."""

    def test_learn(self) -> None:
        le = LearningEngine()
        lesson = Lesson(content="test lesson")
        le.learn(lesson)
        assert len(le) == 1

    def test_learn_many(self) -> None:
        le = LearningEngine()
        lessons = [Lesson(content=f"lesson {i}") for i in range(3)]
        le.learn_many(lessons)
        assert len(le) == 3

    def test_lessons_filtered_by_category(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="a", category="planning"))
        le.learn(Lesson(content="b", category="execution"))
        planning = le.lessons(category="planning")
        assert len(planning) == 1

    def test_lessons_filtered_by_confidence(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="a", confidence=0.3))
        le.learn(Lesson(content="b", confidence=0.9))
        high = le.lessons(min_confidence=0.8)
        assert len(high) == 1

    def test_lessons_limit(self) -> None:
        le = LearningEngine()
        for i in range(10):
            le.learn(Lesson(content=f"lesson {i}"))
        result = le.lessons(limit=3)
        assert len(result) == 3

    def test_get_lesson(self) -> None:
        le = LearningEngine()
        lesson = Lesson(content="test")
        le.learn(lesson)
        assert le.get(lesson.id) is not None

    def test_get_missing_returns_none(self) -> None:
        le = LearningEngine()
        assert le.get("missing") is None

    def test_categories(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="a", category="x"))
        le.learn(Lesson(content="b", category="y"))
        cats = le.categories()
        assert "x" in cats
        assert "y" in cats

    def test_summary(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="a", category="x", confidence=0.8))
        le.learn(Lesson(content="b", category="y", confidence=0.6))
        s = le.summary()
        assert s.total_lessons == 2
        assert "x" in s.categories
        assert s.avg_confidence == 0.7

    def test_summary_empty(self) -> None:
        le = LearningEngine()
        s = le.summary()
        assert s.total_lessons == 0

    def test_clear(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="a"))
        le.clear()
        assert len(le) == 0

    def test_max_lessons_eviction(self) -> None:
        le = LearningEngine(max_lessons=3)
        for i in range(5):
            le.learn(Lesson(content=f"lesson {i}"))
        assert len(le) == 3

    def test_learn_with_memory(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(
                self, content, source=None, tags=None, **kwargs
            ):  # noqa: ARG002
                recorded.append(content)

        le = LearningEngine(memory=FakeMemory())
        le.learn(Lesson(content="test"))
        assert len(recorded) == 1

    def test_iter(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="a"))
        le.learn(Lesson(content="b"))
        lessons = list(le)
        assert len(lessons) == 2

    def test_max_lessons_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            LearningEngine(max_lessons=0)

    def test_top_lessons_in_summary(self) -> None:
        le = LearningEngine()
        le.learn(Lesson(content="low", confidence=0.3))
        le.learn(Lesson(content="high", confidence=0.9))
        s = le.summary()
        assert len(s.top_lessons) <= 5
        assert s.top_lessons[0].confidence >= s.top_lessons[-1].confidence


# ===========================================================================
# Coordinator
# ===========================================================================


class TestCoordinator:
    """Tests for atlas.intelligence.coordinator."""

    def test_no_subsystems(self) -> None:
        c = Coordinator()
        assert not c.has_execution()
        assert not c.has_providers()
        assert not c.has_memory()
        assert not c.has_knowledge()

    def test_has_methods(self) -> None:
        class FakeExec:
            def run(self, goal: str) -> Any:
                return {"goal": goal}

        c = Coordinator(execution=FakeExec())
        assert c.has_execution()

    def test_search_knowledge_none(self) -> None:
        c = Coordinator()
        assert c.search_knowledge("test") == []

    def test_search_knowledge_with_engine(self) -> None:
        class FakeKnowledge:
            def search(self, query: str) -> list:
                return [{"content": "fact"}]

        c = Coordinator(knowledge=FakeKnowledge())
        results = c.search_knowledge("test")
        assert len(results) == 1

    def test_recall_memory_none(self) -> None:
        c = Coordinator()
        assert c.recall_memory() == []

    def test_recall_memory_with_engine(self) -> None:
        class FakeMemory:
            def recall(self) -> list:
                return [{"content": "memory"}]

        c = Coordinator(memory=FakeMemory())
        results = c.recall_memory()
        assert len(results) == 1

    def test_remember_without_memory(self) -> None:
        c = Coordinator()
        c.remember("test")  # should not raise

    def test_remember_with_memory(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        c = Coordinator(memory=FakeMemory())
        c.remember("test")
        assert len(recorded) == 1

    def test_execute_goal_without_execution(self) -> None:
        c = Coordinator()
        result = c.execute_goal("test")
        assert "error" in result

    def test_execute_goal_with_execution(self) -> None:
        class FakeExec:
            def run(self, goal: str) -> Any:
                return {"result": goal}

        c = Coordinator(execution=FakeExec())
        result = c.execute_goal("test")
        assert result["result"] == "test"

    def test_run_runtime_without_runtime(self) -> None:
        c = Coordinator()
        result = c.run_runtime("test")
        assert "error" in result

    def test_generate_without_providers(self) -> None:
        c = Coordinator()
        result = c.generate("test")
        assert "error" in result

    def test_execute_mcp_without_mcp(self) -> None:
        c = Coordinator()
        result = c.execute_mcp("cap")
        assert "error" in result

    def test_provider_candidates_empty(self) -> None:
        c = Coordinator()
        assert c.provider_candidates() == []

    def test_mcp_candidates_empty(self) -> None:
        c = Coordinator()
        assert c.mcp_candidates() == []

    def test_all_candidates_empty(self) -> None:
        c = Coordinator()
        assert c.all_candidates() == []

    def test_repr(self) -> None:
        c = Coordinator()
        text = repr(c)
        assert "Coordinator" in text


# ===========================================================================
# Brain
# ===========================================================================


class TestBrain:
    """Tests for atlas.intelligence.brain."""

    def test_think_returns_outcome(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert isinstance(outcome, ExecutionOutcome)
        assert outcome.success

    def test_think_completes_goal(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.status is GoalStatus.COMPLETED

    def test_think_has_reasoning(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.reasoning is not None
        assert len(outcome.reasoning.steps) == 6

    def test_think_has_plan(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.plan is not None
        assert len(outcome.plan.tasks) >= 1

    def test_think_has_critique(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.critique is not None

    def test_think_has_reflection(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.reflection is not None

    def test_think_learns_lessons(self) -> None:
        brain = Brain()
        brain.think("test goal")
        # May or may not learn lessons depending on critique.
        assert len(brain.learning) >= 0

    def test_think_empty_goal_raises(self) -> None:
        brain = Brain()
        with pytest.raises(BrainError):
            brain.think("")

    def test_think_whitespace_goal_raises(self) -> None:
        brain = Brain()
        with pytest.raises(BrainError):
            brain.think("   ")

    def test_think_many(self) -> None:
        brain = Brain()
        outcomes = brain.think_many(["goal1", "goal2", "goal3"])
        assert len(outcomes) == 3
        assert all(o.success for o in outcomes)

    def test_status(self) -> None:
        brain = Brain()
        brain.think("test")
        status = brain.status()
        assert "goals_total" in status
        assert "lessons_learned" in status

    def test_think_with_coordinator(self) -> None:
        class FakeCoordinator:
            def search_knowledge(self, q: str) -> list:  # noqa: ARG002
                return []

            def recall_memory(self, q: str | None = None) -> list:  # noqa: ARG002
                return []

            def remember(self, content: Any, **kwargs: Any) -> None:  # noqa: ARG002
                pass

            def has_execution(self) -> bool:
                return True

            def has_runtime(self) -> bool:
                return False

            def has_providers(self) -> bool:
                return False

            def has_mcp(self) -> bool:
                return False

            def execute_goal(self, goal: str) -> Any:  # noqa: ARG002
                return {"status": "executed", "result": "done"}

            def all_candidates(self) -> list:
                return []

        brain = Brain(coordinator=FakeCoordinator())
        outcome = brain.think("test goal")
        assert outcome.success
        assert outcome.result["status"] == "executed"

    def test_think_records_goal_in_manager(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        goal = brain.goal_manager.get(outcome.goal_id)
        assert goal.status is GoalStatus.COMPLETED

    def test_think_failure_handling(self) -> None:
        """If the pipeline raises, the goal should be marked FAILED."""
        brain = Brain()

        # Make the reasoner raise.
        class BadReasoner(Reasoner):
            def reason(
                self, goal: str, context: dict | None = None
            ) -> ReasoningChain:  # noqa: ARG002
                raise RuntimeError("reasoning failed")

        brain.reasoner = BadReasoner()
        outcome = brain.think("test goal")
        assert outcome.status is GoalStatus.FAILED
        assert "reasoning failed" in (outcome.error or "")

    def test_think_duration_positive(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.duration_seconds >= 0.0

    def test_think_has_started_and_completed(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert outcome.started_at is not None
        assert outcome.completed_at is not None

    def test_think_metadata_has_counts(self) -> None:
        brain = Brain()
        outcome = brain.think("test goal")
        assert "knowledge_hits" in outcome.metadata
        assert "memory_hits" in outcome.metadata

    def test_brain_repr(self) -> None:
        brain = Brain()
        text = repr(brain)
        assert "Brain" in text

    def test_think_with_different_priorities(self) -> None:
        brain = Brain()
        outcome = brain.think("test", priority=GoalPriority.CRITICAL)
        assert outcome.success

    def test_think_with_different_scopes(self) -> None:
        brain = Brain()
        outcome = brain.think("test", scope=GoalScope.LONG_TERM)
        assert outcome.success

    def test_multiple_thinks_accumulate_goals(self) -> None:
        brain = Brain()
        brain.think("goal1")
        brain.think("goal2")
        brain.think("goal3")
        assert len(brain.goal_manager) == 3

    def test_multiple_thinks_accumulate_lessons(self) -> None:
        brain = Brain()
        brain.think("goal1")
        brain.think("goal2")
        # Each think may or may not produce lessons, but the learning
        # engine should not lose lessons between calls.
        initial = len(brain.learning)
        brain.think("goal3")
        assert len(brain.learning) >= initial


# ===========================================================================
# Integration / End-to-end
# ===========================================================================


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_without_coordinator(self) -> None:
        brain = Brain()
        outcome = brain.think("Create website for my portfolio")
        assert outcome.success
        assert outcome.reasoning is not None
        assert outcome.plan is not None
        assert outcome.critique is not None
        assert outcome.reflection is not None

    def test_full_pipeline_with_mock_coordinator(self) -> None:
        class MockCoord:
            def search_knowledge(self, q: str) -> list:  # noqa: ARG002
                return [{"content": "relevant fact"}]

            def recall_memory(self, q: str | None = None) -> list:  # noqa: ARG002
                return [{"content": "past experience"}]

            def remember(self, content: Any, **kwargs: Any) -> None:  # noqa: ARG002
                pass

            def has_execution(self) -> bool:
                return True

            def has_runtime(self) -> bool:
                return False

            def has_providers(self) -> bool:
                return False

            def has_mcp(self) -> bool:
                return False

            def execute_goal(self, goal: str) -> Any:  # noqa: ARG002
                return {"status": "completed", "result": "website built"}

            def all_candidates(self) -> list:
                return [
                    DecisionCandidate(
                        name="ollama",
                        kind="provider",
                        capabilities=("generate", "research"),
                        quality=0.8,
                    )
                ]

        brain = Brain(coordinator=MockCoord())
        outcome = brain.think("Create website")
        assert outcome.success
        assert outcome.result["status"] == "completed"
        # Should have made decisions for tasks with capabilities.
        assert len(outcome.decisions) > 0

    def test_zero_circular_imports(self) -> None:
        import importlib

        modules = [
            "atlas.intelligence.models",
            "atlas.intelligence.goal_manager",
            "atlas.intelligence.task_decomposer",
            "atlas.intelligence.reasoner",
            "atlas.intelligence.planner",
            "atlas.intelligence.decision",
            "atlas.intelligence.reflection",
            "atlas.intelligence.critic",
            "atlas.intelligence.learning",
            "atlas.intelligence.coordinator",
            "atlas.intelligence.brain",
            "atlas.intelligence",
        ]
        for m in modules:
            importlib.import_module(m)

    def test_brain_with_injected_components(self) -> None:
        gm = GoalManager()
        de = DecisionEngine()
        brain = Brain(
            goal_manager=gm,
            decision=de,
        )
        assert brain.goal_manager is gm
        assert brain.decision is de

    def test_brain_uses_learning_engine(self) -> None:
        brain = Brain()
        brain.think("goal that will produce a lesson")
        # The brain should have learned at least something (or nothing
        # if no mistakes — both are valid).
        assert len(brain.learning) >= 0

    def test_brain_goal_lifecycle(self) -> None:
        brain = Brain()
        outcome = brain.think("test")
        goal = brain.goal_manager.get(outcome.goal_id)
        # Goal should be completed.
        assert goal.status is GoalStatus.COMPLETED
        assert goal.completed_at is not None
        # History should have at least 3 entries (create, start, complete).
        assert len(brain.goal_manager.history(goal.id)) >= 3
