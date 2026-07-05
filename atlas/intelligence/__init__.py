"""The Atlas Intelligence Layer.

The Intelligence Layer is the brain that connects ALL existing Atlas
subsystems together. It does NOT duplicate their functionality — it
orchestrates them through a single :class:`Brain` facade with one
public method: :meth:`Brain.think`.

Pipeline::

    Goal → Knowledge → Memory → Reason → Plan → Choose → Execute →
    Review → Reflect → Learn → Update Memory → Report

Dependency graph (acyclic):

* ``models`` — leaf (frozen dataclasses + enums).
* ``goal_manager`` — depends on ``models``.
* ``task_decomposer`` — depends on ``models``.
* ``reasoner`` — depends on ``models``.
* ``planner`` — depends on ``models``.
* ``decision`` — depends on ``models``.
* ``reflection`` — depends on ``models``.
* ``critic`` — depends on ``models``.
* ``learning`` — depends on ``models``.
* ``coordinator`` — depends on ``models``.
* ``brain`` — depends on all of the above.
"""

from __future__ import annotations

from atlas.intelligence.brain import Brain, BrainError
from atlas.intelligence.coordinator import Coordinator
from atlas.intelligence.critic import Critic
from atlas.intelligence.decision import DecisionEngine
from atlas.intelligence.goal_manager import GoalManager, GoalManagerError
from atlas.intelligence.learning import LearningEngine
from atlas.intelligence.models import (
    TERMINAL_STATUSES,
    AdaptivePlan,
    Critique,
    Decision,
    DecisionCandidate,
    ExecutionOutcome,
    Goal,
    GoalPriority,
    GoalScope,
    GoalStatus,
    GoalTree,
    IntelligenceTask,
    LearningSummary,
    Lesson,
    PlanAdjustment,
    ReasoningChain,
    ReasoningStep,
    ReasoningStepType,
    Reflection,
)
from atlas.intelligence.planner import AdaptivePlanner
from atlas.intelligence.reasoner import Reasoner
from atlas.intelligence.reflection import ReflectionEngine
from atlas.intelligence.task_decomposer import TaskDecomposer

__all__ = [
    "AdaptivePlan",
    "AdaptivePlanner",
    "Brain",
    "BrainError",
    "Coordinator",
    "Critique",
    "Critic",
    "Decision",
    "DecisionCandidate",
    "DecisionEngine",
    "ExecutionOutcome",
    "Goal",
    "GoalManager",
    "GoalManagerError",
    "GoalPriority",
    "GoalScope",
    "GoalStatus",
    "GoalTree",
    "IntelligenceTask",
    "LearningEngine",
    "LearningSummary",
    "Lesson",
    "PlanAdjustment",
    "Reasoner",
    "ReasoningChain",
    "ReasoningStep",
    "ReasoningStepType",
    "Reflection",
    "ReflectionEngine",
    "TERMINAL_STATUSES",
    "TaskDecomposer",
]
