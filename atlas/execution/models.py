"""Immutable data models for the Atlas Execution Engine.

Every model in this module is a frozen dataclass: once constructed, the
instance cannot be mutated in place. Updates are performed by producing
a new copy via :func:`dataclasses.replace`. This makes execution plans,
tasks, and results safe to share across components, store in history,
and inspect concurrently without defensive copies.

The module is a *leaf* in the execution package dependency graph: it
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


def _new_id(prefix: str = "exec") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExecutionStatus(enum.StrEnum):
    """Lifecycle states an execution (or task) can occupy.

    Attributes:
        PENDING: Created but not yet started.
        RUNNING: Actively executing.
        PAUSED: Suspended; may be resumed.
        COMPLETED: Finished successfully. Terminal.
        FAILED: Finished with an error. Terminal but retryable.
        CANCELLED: Operator cancelled. Terminal.
        SKIPPED: Optional task whose dependencies were not met. Terminal.
    """

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskKind(enum.StrEnum):
    """The kind of work a task represents.

    Attributes:
        RESEARCH: Gather information (knowledge search, web, etc.).
        GENERATE: Produce code, text, or assets.
        TEST: Run tests or validations.
        DEPLOY: Push to a target environment.
        GIT: Version-control operations.
        REVIEW: Self-review or reflection.
        CUSTOM: Free-form; resolved by the executor's action registry.
    """

    RESEARCH = "research"
    GENERATE = "generate"
    TEST = "test"
    DEPLOY = "deploy"
    GIT = "git"
    REVIEW = "review"
    CUSTOM = "custom"


class Priority(enum.IntEnum):
    """Task priority. Higher numbers run first within a phase.

    Attributes:
        LOW: Background work.
        NORMAL: Default.
        HIGH: Important.
        CRITICAL: Must run before everything else.
    """

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


#: Statuses from which an execution cannot be advanced further.
TERMINAL_STATUSES: frozenset[ExecutionStatus] = frozenset(
    {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.SKIPPED,
    }
)


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for a single task.

    Attributes:
        max_attempts: Maximum number of execution attempts. ``1`` means
            no retry. Defaults to ``3``.
        backoff_seconds: Base delay between retries. The actual delay
            is ``backoff_seconds * 2 ** (attempt - 1)``. Defaults to
            ``1.0``.
        max_backoff_seconds: Cap on the backoff delay. Defaults to
            ``60.0``.
        retryable_errors: If non-empty, only errors whose message
            contains one of these substrings (case-insensitive) are
            retryable. Empty means everything is retryable.
    """

    max_attempts: int = 3
    backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    retryable_errors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Execution task
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionTask:
    """A single unit of work inside an :class:`ExecutionPlan`.

    Attributes:
        id: Stable identifier used by other tasks to express dependencies.
        name: Human-readable label.
        kind: The :class:`TaskKind` governing how the dispatcher resolves
            this task.
        description: Free-form description of what the task should
            accomplish. Used by future AI planning.
        action: The action name resolved by the executor. Provider-
            agnostic — the executor decides how to dispatch this string.
        params: Static parameters passed to the action at execution time.
        dependencies: IDs of tasks that must complete successfully before
            this task may execute.
        priority: :class:`Priority` controlling intra-phase ordering.
        optional: If ``True``, failure of this task does not fail the
            execution.
        retry_policy: :class:`RetryPolicy` for this task.
        metadata: Free-form bag for tooling (tags, owner, etc.).
    """

    id: str = field(default_factory=lambda: _new_id("task"))
    name: str = ""
    kind: TaskKind = TaskKind.CUSTOM
    description: str = ""
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    priority: Priority = Priority.NORMAL
    optional: bool = False
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Execution plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionPlan:
    """An immutable, ordered plan of :class:`ExecutionTask` items.

    A plan is produced by the :class:`ExecutionPlanner` from a natural-
    language goal. It is consumed by the :class:`ExecutionDispatcher`
    and :class:`ExecutionExecutor`.

    Attributes:
        id: Unique identifier for the plan.
        goal: The original natural-language goal.
        tasks: Ordered list of :class:`ExecutionTask` items.
        strategy: The :class:`atlas.execution.strategy.ExecutionStrategy`
            to use. Stored as a string to keep this module leaf.
        created_at: When the plan was created.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("plan"))
    goal: str = ""
    tasks: list[ExecutionTask] = field(default_factory=list)
    strategy: str = "sequential"
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def task_ids(self) -> list[str]:
        """Return the IDs of every task in the plan, in declaration order."""
        return [task.id for task in self.tasks]

    def task_by_id(self, task_id: str) -> ExecutionTask | None:
        """Look up a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def dependencies_of(self, task_id: str) -> list[str]:
        """Return the dependencies of ``task_id``."""
        task = self.task_by_id(task_id)
        return list(task.dependencies) if task is not None else []


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionResult:
    """The outcome of executing a single :class:`ExecutionTask`.

    Attributes:
        task_id: The task that produced this result.
        status: The :class:`ExecutionStatus` of the task.
        output: The value produced by the task (any picklable object).
        error: An error message if ``status`` is ``FAILED``.
        started_at: When execution began.
        completed_at: When execution finished. ``None`` if interrupted.
        attempts: Number of execution attempts made.
        provider: Name of the provider used, if any.
        agent: Name of the agent used, if any.
        tool: Name of the tool used, if any.
        workflow: ID of the workflow used, if any.
        token_usage: Estimated token usage (prompt + completion).
        cost: Estimated dollar cost of the task.
        metadata: Free-form runtime metadata.
    """

    task_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    output: Any = None
    error: str | None = None
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    attempts: int = 1
    provider: str | None = None
    agent: str | None = None
    tool: str | None = None
    workflow: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Return ``True`` if the task completed successfully."""
        return self.status is ExecutionStatus.COMPLETED

    @property
    def duration_seconds(self) -> float:
        """Return the wall-clock duration of the task."""
        end = self.completed_at or _utcnow()
        return (end - self.started_at).total_seconds()


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable bundle carried through the execution pipeline.

    The context bundles the original goal, the plan, the per-task results,
    and any artifacts accumulated along the way. Because it is frozen,
    every pipeline stage produces a new context via
    :func:`dataclasses.replace`.

    Attributes:
        id: Unique identifier for this execution.
        goal: The original natural-language goal.
        plan: The :class:`ExecutionPlan` being executed.
        results: Mapping of task ID -> :class:`ExecutionResult`.
        artifacts: Named outputs accumulated by each task for downstream
            consumption.
        metadata: Free-form runtime metadata.
        started_at: When the execution started.
        user: Optional operator identifier (personal OS — usually ``None``).
    """

    id: str = field(default_factory=lambda: _new_id("exec"))
    goal: str = ""
    plan: ExecutionPlan | None = None
    results: dict[str, ExecutionResult] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utcnow)
    user: str | None = None

    def with_plan(self, plan: ExecutionPlan) -> ExecutionContext:
        """Return a new context with ``plan`` set."""
        return _replace(self, plan=plan)

    def with_result(self, result: ExecutionResult) -> ExecutionContext:
        """Return a new context with ``result`` merged into :attr:`results`."""
        new_results = {**self.results, result.task_id: result}
        return _replace(self, results=new_results)

    def with_artifact(self, key: str, value: Any) -> ExecutionContext:
        """Return a new context with ``key=value`` added to :attr:`artifacts`."""
        new_artifacts = {**self.artifacts, key: value}
        return _replace(self, artifacts=new_artifacts)

    def is_terminal(self) -> bool:
        """Return ``True`` if every task in the plan has a terminal status."""
        if self.plan is None:
            return False
        for task in self.plan.tasks:
            result = self.results.get(task.id)
            if result is None or result.status not in TERMINAL_STATUSES:
                return False
        return True


def _replace(instance: Any, **changes: Any) -> Any:
    """Wrapper around :func:`dataclasses.replace` for convenience."""
    import dataclasses

    return dataclasses.replace(instance, **changes)


# ---------------------------------------------------------------------------
# Execution metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionMetrics:
    """Aggregate metrics across every task in an execution.

    Attributes:
        total_tasks: Number of tasks in the plan.
        completed_tasks: Number of tasks that completed successfully.
        failed_tasks: Number of tasks that failed.
        skipped_tasks: Number of optional tasks that were skipped.
        cancelled_tasks: Number of tasks that were cancelled.
        total_attempts: Sum of attempts across every task.
        total_duration_seconds: Wall-clock duration of the entire execution.
        total_tokens: Total tokens consumed (prompt + completion).
        total_cost: Total estimated dollar cost.
        providers_used: Set of provider names that were used.
        tools_used: Set of tool names that were used.
        agents_used: Set of agent names that were used.
        workflows_used: Set of workflow IDs that were used.
    """

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    cancelled_tasks: int = 0
    total_attempts: int = 0
    total_duration_seconds: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    providers_used: frozenset[str] = field(default_factory=frozenset)
    tools_used: frozenset[str] = field(default_factory=frozenset)
    agents_used: frozenset[str] = field(default_factory=frozenset)
    workflows_used: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Execution summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionSummary:
    """A short summary of an execution.

    Attributes:
        execution_id: The execution this summary describes.
        goal: The original goal.
        status: The overall :class:`ExecutionStatus`.
        duration_seconds: Wall-clock duration.
        completed_tasks: Number of successfully completed tasks.
        failed_tasks: Number of failed tasks.
        total_tasks: Total number of tasks in the plan.
        overall_quality_score: 0.0 - 1.0 quality score from the reviewer.
    """

    execution_id: str
    goal: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    duration_seconds: float = 0.0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tasks: int = 0
    overall_quality_score: float = 0.0


# ---------------------------------------------------------------------------
# Execution report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionReport:
    """The full professional report produced after an execution.

    Attributes:
        execution_id: The execution this report describes.
        goal: The original natural-language goal.
        status: The overall :class:`ExecutionStatus`.
        started_at: When the execution started.
        completed_at: When the execution reached a terminal state.
        duration_seconds: Wall-clock duration.
        plan_id: The :attr:`ExecutionPlan.id` that was executed.
        strategy: The execution strategy used.
        results: Mapping of task ID -> :class:`ExecutionResult`.
        metrics: Aggregate :class:`ExecutionMetrics`.
        summary: Short :class:`ExecutionSummary`.
        providers_used: Sorted list of provider names used.
        agents_used: Sorted list of agent names used.
        tools_used: Sorted list of tool names used.
        workflows_used: Sorted list of workflow IDs used.
        memory_usage: Memory engine statistics.
        knowledge_hits: Number of knowledge search hits.
        files_created: List of files created during execution.
        files_modified: List of files modified during execution.
        git_commits: List of git commit hashes produced.
        tool_calls: Total number of tool invocations.
        mcp_calls: Total number of MCP server calls.
        warnings: List of human-readable warning messages.
        errors: List of human-readable error messages.
        token_usage: Breakdown of token usage (prompt, completion, total).
        estimated_cost: Estimated dollar cost.
        quality_score: 0.0 - 1.0 quality score from the reviewer.
        retry_recommendation: Reviewer's recommendation on whether to retry.
        metadata: Free-form metadata.
    """

    execution_id: str
    goal: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    plan_id: str | None = None
    strategy: str = "sequential"
    results: dict[str, ExecutionResult] = field(default_factory=dict)
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    summary: ExecutionSummary | None = None
    providers_used: list[str] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    workflows_used: list[str] = field(default_factory=list)
    memory_usage: dict[str, Any] = field(default_factory=dict)
    knowledge_hits: int = 0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    git_commits: list[str] = field(default_factory=list)
    tool_calls: int = 0
    mcp_calls: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    estimated_cost: float = 0.0
    quality_score: float = 0.0
    retry_recommendation: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Return ``True`` if the execution completed successfully."""
        return self.status is ExecutionStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict representation (for JSON export / logging)."""
        import dataclasses

        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Execution history
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionHistoryEntry:
    """A single recorded execution snapshot.

    Attributes:
        execution_id: The execution this entry records.
        goal: The original goal.
        status: The final :class:`ExecutionStatus`.
        started_at: When the execution started.
        completed_at: When the execution reached a terminal state.
        duration_seconds: Wall-clock duration.
        task_count: Number of tasks in the plan.
        completed_tasks: Number of successfully completed tasks.
        failed_tasks: Number of failed tasks.
        quality_score: 0.0 - 1.0 quality score.
        report: The full :class:`ExecutionReport` (optional — may be
            omitted to save space).
    """

    execution_id: str
    goal: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    task_count: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    quality_score: float = 0.0
    report: ExecutionReport | None = None


class ExecutionHistory:
    """Append-only history of :class:`ExecutionHistoryEntry` records.

    The history is in-memory and append-only. For persistence, wrap it
    in a concrete adapter that forwards to a database or filesystem.
    """

    def __init__(self) -> None:
        self._entries: list[ExecutionHistoryEntry] = []

    def record(self, entry: ExecutionHistoryEntry) -> ExecutionHistoryEntry:
        """Append ``entry`` to the history."""
        self._entries.append(entry)
        return entry

    def list(self, limit: int = 100) -> list[ExecutionHistoryEntry]:
        """Return the most recent ``limit`` entries (newest first)."""
        return list(reversed(self._entries[-limit:]))

    def get(self, execution_id: str) -> ExecutionHistoryEntry | None:
        """Return the entry for ``execution_id`` or ``None``."""
        for entry in reversed(self._entries):
            if entry.execution_id == execution_id:
                return entry
        return None

    def clear(self) -> None:
        """Drop every recorded entry."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __contains__(self, execution_id: object) -> bool:
        if not isinstance(execution_id, str):
            return False
        return any(e.execution_id == execution_id for e in self._entries)

    def __repr__(self) -> str:
        return f"<ExecutionHistory entries={len(self)}>"


__all__ = [
    "TERMINAL_STATUSES",
    "ExecutionContext",
    "ExecutionHistory",
    "ExecutionHistoryEntry",
    "ExecutionMetrics",
    "ExecutionPlan",
    "ExecutionReport",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionSummary",
    "ExecutionTask",
    "Priority",
    "RetryPolicy",
    "TaskKind",
]
