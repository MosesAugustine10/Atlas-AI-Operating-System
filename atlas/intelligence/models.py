"""Immutable data models for the Atlas Intelligence Layer.

Every model in this module is a frozen dataclass: once constructed, the
instance cannot be mutated in place. Updates are performed by producing
a new copy via :func:`dataclasses.replace`.

The module is a *leaf* in the intelligence package dependency graph: it
depends only on the standard library.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "intel") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GoalStatus(enum.StrEnum):
    """Lifecycle states for a goal.

    Attributes:
        PENDING: Created but not yet started.
        ACTIVE: Currently being worked on.
        PAUSED: Suspended; may be resumed.
        COMPLETED: Finished successfully. Terminal.
        FAILED: Finished with an error. Terminal but retryable.
        CANCELLED: Operator cancelled. Terminal.
    """

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalScope(enum.StrEnum):
    """Time horizon of a goal.

    Attributes:
        SHORT_TERM: Immediate / session-scoped.
        LONG_TERM: Persistent across sessions.
    """

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class GoalPriority(enum.IntEnum):
    """Goal priority. Higher = more important.

    Attributes:
        LOW: Background work.
        NORMAL: Default.
        HIGH: Important.
        CRITICAL: Must be done before everything else.
    """

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class ReasoningStepType(enum.StrEnum):
    """Types of reasoning steps.

    Attributes:
        OBSERVE: Gather information.
        HYPOTHESIZE: Form a hypothesis.
        DEDUCE: Deduce from known facts.
        INFER: Infer from patterns.
        EVALUATE: Evaluate a candidate.
        DECIDE: Make a decision.
    """

    OBSERVE = "observe"
    HYPOTHESIZE = "hypothesize"
    DEDUCE = "deduce"
    INFER = "infer"
    EVALUATE = "evaluate"
    DECIDE = "decide"


class PlanAdjustment(enum.StrEnum):
    """How an adaptive plan was adjusted.

    Attributes:
        SPLIT: A task was split into sub-tasks.
        MERGE: Multiple tasks were merged into one.
        REMOVE: A task was removed.
        INSERT: A new task was inserted.
        REORDER: Tasks were reordered.
        NONE: No adjustment was made.
    """

    SPLIT = "split"
    MERGE = "merge"
    REMOVE = "remove"
    INSERT = "insert"
    REORDER = "reorder"
    NONE = "none"


#: Statuses from which a goal cannot be advanced further.
TERMINAL_STATUSES: frozenset[GoalStatus] = frozenset(
    {
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
    }
)


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Goal:
    """A single goal tracked by the :class:`GoalManager`.

    Attributes:
        id: Unique identifier.
        description: Human-readable goal statement.
        scope: :class:`GoalScope` — short-term or long-term.
        priority: :class:`GoalPriority`.
        status: :class:`GoalStatus`.
        parent_id: If this is a sub-goal, the id of the parent goal.
        dependencies: IDs of goals that must complete before this one.
        created_at: When the goal was created.
        updated_at: When the goal was last modified.
        completed_at: When the goal reached a terminal state.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("goal"))
    description: str = ""
    scope: GoalScope = GoalScope.SHORT_TERM
    priority: GoalPriority = GoalPriority.NORMAL
    status: GoalStatus = GoalStatus.PENDING
    parent_id: str | None = None
    dependencies: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if the goal is in a terminal state."""
        return self.status in TERMINAL_STATUSES

    @property
    def is_active(self) -> bool:
        """Return ``True`` if the goal is currently active."""
        return self.status is GoalStatus.ACTIVE


# ---------------------------------------------------------------------------
# Sub-goal tree
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoalTree:
    """A tree of goals produced by the :class:`TaskDecomposer`.

    Attributes:
        root: The top-level :class:`Goal`.
        children: Sub-goals of ``root``.
    """

    root: Goal
    children: list[GoalTree] = field(default_factory=list)

    def flatten(self) -> list[Goal]:
        """Return every goal in the tree (depth-first)."""
        result: list[Goal] = [self.root]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def depth(self) -> int:
        """Return the maximum depth of the tree."""
        if not self.children:
            return 0
        return 1 + max(child.depth() for child in self.children)


# ---------------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReasoningStep:
    """A single step in a reasoning chain.

    Attributes:
        id: Unique step identifier.
        step_type: :class:`ReasoningStepType`.
        content: The reasoning content (text or structured data).
        evidence: Supporting evidence (facts, citations, memory hits).
        confidence: 0.0 - 1.0 confidence in this step.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("step"))
    step_type: ReasoningStepType = ReasoningStepType.OBSERVE
    content: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReasoningChain:
    """A chain of :class:`ReasoningStep` items leading to a conclusion.

    Attributes:
        id: Unique chain identifier.
        goal_id: The goal this chain reasons about.
        steps: Ordered list of :class:`ReasoningStep` items.
        conclusion: The final conclusion.
        overall_confidence: 0.0 - 1.0 confidence in the conclusion.
        created_at: When the chain was produced.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("chain"))
    goal_id: str | None = None
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    overall_confidence: float = 0.0
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adaptive plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntelligenceTask:
    """A single task in an adaptive plan.

    Attributes:
        id: Unique task identifier.
        description: Human-readable task description.
        capability: The capability required to execute this task.
        params: Parameters for the task.
        dependencies: IDs of tasks that must complete first.
        priority: :class:`GoalPriority` for intra-plan ordering.
        optional: If ``True``, failure does not fail the plan.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("task"))
    description: str = ""
    capability: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    priority: GoalPriority = GoalPriority.NORMAL
    optional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdaptivePlan:
    """A plan that can be dynamically adjusted during execution.

    Attributes:
        id: Unique plan identifier.
        goal_id: The goal this plan serves.
        tasks: Ordered list of :class:`IntelligenceTask` items.
        adjustments: History of :class:`PlanAdjustment` values applied.
        version: Plan version (incremented on each adjustment).
        created_at: When the plan was created.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("plan"))
    goal_id: str | None = None
    tasks: list[IntelligenceTask] = field(default_factory=list)
    adjustments: list[PlanAdjustment] = field(default_factory=list)
    version: int = 1
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def task_ids(self) -> list[str]:
        """Return the IDs of every task in declaration order."""
        return [t.id for t in self.tasks]

    def task_by_id(self, task_id: str) -> IntelligenceTask | None:
        """Look up a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionCandidate:
    """A candidate considered by the :class:`DecisionEngine`.

    Attributes:
        name: Candidate name (e.g. provider name, tool name).
        kind: Candidate kind (``"provider"``, ``"agent"``, ``"tool"``,
            ``"workflow"``, ``"mcp"``).
        capabilities: Capabilities the candidate offers.
        cost: Estimated cost (0.0 = free, higher = more expensive).
        availability: 0.0 - 1.0 availability score.
        latency_ms: Estimated latency in milliseconds.
        quality: 0.0 - 1.0 historical quality score.
        metadata: Free-form metadata.
    """

    name: str
    kind: str = ""
    capabilities: tuple[str, ...] = ()
    cost: float = 0.0
    availability: float = 1.0
    latency_ms: float = 0.0
    quality: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """The outcome of a :class:`DecisionEngine` selection.

    Attributes:
        id: Unique decision identifier.
        selected: The name of the selected candidate.
        kind: Candidate kind (``"provider"``, ``"agent"``, etc.).
        reason: Human-readable explanation.
        alternatives: Names of candidates that were considered but not
            selected.
        score: 0.0 - 1.0 score of the selected candidate.
        created_at: When the decision was made.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("dec"))
    selected: str = ""
    kind: str = ""
    reason: str = ""
    alternatives: list[str] = field(default_factory=list)
    score: float = 0.0
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Reflection & Critic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Critique:
    """The :class:`Critic`'s review of an output.

    Attributes:
        warnings: List of human-readable warning messages.
        confidence: 0.0 - 1.0 confidence in the output.
        quality_score: 0.0 - 1.0 quality score.
        notes: Free-form notes.
    """

    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    quality_score: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class Reflection:
    """The :class:`ReflectionEngine`'s evaluation of an execution.

    Attributes:
        id: Unique reflection identifier.
        goal_id: The goal that was executed.
        expected: What was expected to happen.
        actual: What actually happened.
        mistakes: List of detected mistakes.
        lessons: List of :class:`Lesson` items extracted.
        quality_score: 0.0 - 1.0 quality score.
        should_retry: Whether a retry is recommended.
        created_at: When the reflection was produced.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("reflection"))
    goal_id: str | None = None
    expected: str = ""
    actual: str = ""
    mistakes: list[str] = field(default_factory=list)
    lessons: list[Lesson] = field(default_factory=list)
    quality_score: float = 0.0
    should_retry: bool = False
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Lesson:
    """A single lesson learned by the :class:`LearningEngine`.

    Attributes:
        id: Unique lesson identifier.
        content: The lesson text.
        category: Lesson category (e.g. ``"planning"``, ``"execution"``).
        source: What produced the lesson (``"reflection"``,
            ``"history"``, ``"memory"``).
        confidence: 0.0 - 1.0 confidence in the lesson.
        created_at: When the lesson was recorded.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("lesson"))
    content: str = ""
    category: str = "general"
    source: str = "reflection"
    confidence: float = 0.5
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningSummary:
    """A summary of everything the :class:`LearningEngine` has learned.

    Attributes:
        total_lessons: Total number of lessons stored.
        categories: Mapping of category -> count.
        avg_confidence: Average confidence across all lessons.
        top_lessons: The highest-confidence lessons.
    """

    total_lessons: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    top_lessons: list[Lesson] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution outcome & report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionOutcome:
    """The outcome of executing a goal via the :class:`Brain`.

    Attributes:
        goal_id: The goal that was executed.
        status: Final :class:`GoalStatus`.
        result: The output produced by the execution.
        reasoning: The :class:`ReasoningChain` used.
        plan: The :class:`AdaptivePlan` that was executed.
        decisions: List of :class:`Decision` items made during execution.
        critique: The :class:`Critique` of the output.
        reflection: The :class:`Reflection` on the execution.
        lessons: List of :class:`Lesson` items learned.
        duration_seconds: Wall-clock duration.
        started_at: When execution started.
        completed_at: When execution completed.
        error: Error message if the execution failed.
        metadata: Free-form metadata.
    """

    goal_id: str = ""
    status: GoalStatus = GoalStatus.PENDING
    result: Any = None
    reasoning: ReasoningChain | None = None
    plan: AdaptivePlan | None = None
    decisions: list[Decision] = field(default_factory=list)
    critique: Critique | None = None
    reflection: Reflection | None = None
    lessons: list[Lesson] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Return ``True`` if the execution completed successfully."""
        return self.status is GoalStatus.COMPLETED


__all__ = [
    "AdaptivePlan",
    "Critique",
    "Decision",
    "DecisionCandidate",
    "ExecutionOutcome",
    "Goal",
    "GoalPriority",
    "GoalScope",
    "GoalStatus",
    "GoalTree",
    "IntelligenceTask",
    "LearningSummary",
    "Lesson",
    "PlanAdjustment",
    "ReasoningChain",
    "ReasoningStep",
    "ReasoningStepType",
    "Reflection",
    "TERMINAL_STATUSES",
]
