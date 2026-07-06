"""Atlas Workforce data models — frozen dataclasses and enums.

This module is a *leaf* in the workforce package dependency graph. It
defines every value object exchanged between the worker, team,
manager, orchestrator, and engine layers of :mod:`atlas.workforce`.
Nothing here imports Qt, Brain, or any other Atlas subsystem — the
models are pure, immutable and dependency-free so they can be used
from tests, engines, and headless scripts alike.

All dataclasses are :func:`dataclasses.dataclass` with ``frozen=True``
so instances are hashable and safe to share across threads. Mutable
defaults (``list``, ``dict``) always use ``field(default_factory=...)``;
collection-valued fields that must remain hashable use ``tuple``.

The Workforce Layer sits ABOVE the Brain in the Atlas stack:

    User
      ↓
    Workforce  ← this package
      ↓
    Brain
      ↓
    Execution
      ↓
    Runtime
      ↓
    Providers / MCP / Workflows

Workers never import Brain, Execution, or any subsystem directly —
they communicate only through dependency-injected callbacks (e.g.
``think_fn``, ``execute_fn``) so the workforce package has zero
coupling to concrete subsystem implementations.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "wf") -> str:
    """Return a new unique identifier prefixed with ``prefix``."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ===========================================================================
# Enumerations
# ===========================================================================


class WorkerRole(enum.StrEnum):
    """Every autonomous AI employee role in the Atlas workforce.

    The roles are grouped by specialisation:

    * **Executive** — CEO, CTO
    * **Engineering** — Software Engineer, Research Engineer, Mining
      Engineer, DevOps Engineer
    * **Creative** — UI Designer, Video Creator, Technical Writer
    * **Quality** — QA Engineer
    * **Operations** — Project Manager
    * **Specialists** — Knowledge Specialist, Memory Specialist,
      Vision Specialist
    * **Agents** — Browser Agent, GitHub Agent, Blender Artist
    """

    CEO = "ceo"
    CTO = "cto"
    SOFTWARE_ENGINEER = "software_engineer"
    RESEARCH_ENGINEER = "research_engineer"
    MINING_ENGINEER = "mining_engineer"
    UI_DESIGNER = "ui_designer"
    VIDEO_CREATOR = "video_creator"
    TECHNICAL_WRITER = "technical_writer"
    QA_ENGINEER = "qa_engineer"
    DEVOPS_ENGINEER = "devops_engineer"
    PROJECT_MANAGER = "project_manager"
    KNOWLEDGE_SPECIALIST = "knowledge_specialist"
    MEMORY_SPECIALIST = "memory_specialist"
    BROWSER_AGENT = "browser_agent"
    GITHUB_AGENT = "github_agent"
    BLENDER_ARTIST = "blender_artist"
    VISION_SPECIALIST = "vision_specialist"


class WorkerStatus(enum.StrEnum):
    """Lifecycle status of a worker.

    Attributes:
        OFFLINE: The worker has not been started or has been stopped.
        IDLE: The worker is online and accepting tasks.
        BUSY: The worker is executing a task.
        PAUSED: The worker is paused (not accepting new tasks).
        STOPPED: The worker has been permanently stopped.
        ERROR: The worker encountered an unrecoverable error.
    """

    OFFLINE = "offline"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TaskStatus(enum.StrEnum):
    """Lifecycle status of a workforce task.

    Attributes:
        PENDING: The task has been created but not yet assigned.
        ASSIGNED: The task has been assigned to a worker.
        IN_PROGRESS: The worker is executing the task.
        IN_REVIEW: The task output is under review.
        APPROVED: The task output was approved.
        REJECTED: The task output was rejected and needs rework.
        COMPLETED: The task is fully completed and accepted.
        FAILED: The task failed and cannot be retried.
        CANCELLED: The task was cancelled by the supervisor.
        BLOCKED: The task is blocked on a dependency.
    """

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class TaskPriority(enum.StrEnum):
    """Priority levels for workforce tasks.

    Attributes:
        LOW: Low priority — schedule when idle.
        NORMAL: Default priority.
        HIGH: High priority — schedule ahead of normal.
        URGENT: Urgent — preempts in-progress tasks.
        CRITICAL: Critical — immediate executive attention.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class MessageKind(enum.StrEnum):
    """Kinds of messages workers exchange.

    Attributes:
        INFO: Informational message.
        REQUEST: A request for information or action.
        RESPONSE: A response to a prior request.
        UPDATE: A status update.
        APPROVAL_REQUEST: A request for approval.
        APPROVAL_GRANTED: An approval was granted.
        APPROVAL_DENIED: An approval was denied.
        ESCALATION: An escalation to a higher authority.
        HANDOFF: A task handoff between workers.
        BROADCAST: A broadcast to all team members.
    """

    INFO = "info"
    REQUEST = "request"
    RESPONSE = "response"
    UPDATE = "update"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    ESCALATION = "escalation"
    HANDOFF = "handoff"
    BROADCAST = "broadcast"


class EscalationLevel(enum.StrEnum):
    """Severity levels for escalations.

    Attributes:
        LOW: Minor issue — supervisor should be informed.
        MEDIUM: Notable issue — supervisor should review.
        HIGH: Serious issue — supervisor should intervene.
        CRITICAL: Critical issue — executive attention required.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConflictKind(enum.StrEnum):
    """Kinds of conflicts the supervisor resolves.

    Attributes:
        RESOURCE: Two workers need the same resource.
        PRIORITY: Two tasks have conflicting priorities.
        APPROACH: Workers disagree on the approach.
        SCOPE: Workers disagree on task scope.
        DEPENDENCY: A dependency cycle or blocking chain.
    """

    RESOURCE = "resource"
    PRIORITY = "priority"
    APPROACH = "approach"
    SCOPE = "scope"
    DEPENDENCY = "dependency"


class ConflictResolution(enum.StrEnum):
    """How a conflict was resolved.

    Attributes:
        MEDIATED: The supervisor mediated a compromise.
        ESCALATED: The conflict was escalated to a higher authority.
        AUTO_RESOLVED: The conflict was auto-resolved by policy.
        DEFERRED: The conflict was deferred for later review.
        SPLIT: The work was split between the conflicting workers.
    """

    MEDIATED = "mediated"
    ESCALATED = "escalated"
    AUTO_RESOLVED = "auto_resolved"
    DEFERRED = "deferred"
    SPLIT = "split"


class ReviewVerdict(enum.StrEnum):
    """Possible verdicts from a quality review.

    Attributes:
        APPROVED: The work meets quality standards.
        REJECTED: The work does not meet standards.
        CHANGES_REQUESTED: Rework is needed before approval.
        DEFERRED: The review is deferred (more info needed).
    """

    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    DEFERRED = "deferred"


class WorkerKind(enum.StrEnum):
    """Whether a worker is permanent or temporary.

    Attributes:
        PERMANENT: A permanent member of the workforce.
        TEMPORARY: A temporary worker created for a specific task/team.
    """

    PERMANENT = "permanent"
    TEMPORARY = "temporary"


class ShiftStatus(enum.StrEnum):
    """Status of a worker's shift.

    Attributes:
        SCHEDULED: The shift is scheduled but not yet started.
        ACTIVE: The shift is currently active.
        COMPLETED: The shift has ended.
        CANCELLED: The shift was cancelled.
    """

    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ===========================================================================
# Priority ranking
# ===========================================================================


_PRIORITY_RANK: dict[str, int] = {
    TaskPriority.CRITICAL.value: 0,
    TaskPriority.URGENT.value: 1,
    TaskPriority.HIGH.value: 2,
    TaskPriority.NORMAL.value: 3,
    TaskPriority.LOW.value: 4,
}


def priority_rank(priority: str) -> int:
    """Return the numeric rank for a :class:`TaskPriority` value.

    Lower numbers represent higher priority. Unknown values rank last.
    """
    return _PRIORITY_RANK.get(priority, 99)


# ===========================================================================
# Core models
# ===========================================================================


@dataclass(frozen=True)
class WorkerSkill:
    """A single skill a worker possesses.

    Parameters:
        name: Skill name (e.g. "python", "design", "research").
        level: Proficiency level (0.0 to 1.0).
        certifications: Tuple of certification names.
    """

    name: str
    level: float = 0.5
    certifications: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerMemory:
    """A worker's personal memory store.

    Workers maintain their own memory separate from the global Atlas
    Memory Engine. This is for short-term, worker-specific context
    (e.g. "I tried X and it didn't work").

    Parameters:
        entries: Tuple of ``(key, value)`` memory entries.
        capacity: Maximum number of entries to retain.
    """

    entries: tuple[tuple[str, str], ...] = ()
    capacity: int = 100

    def get(self, key: str) -> str | None:
        """Return the value for ``key`` or ``None``."""
        for k, v in self.entries:
            if k == key:
                return v
        return None

    def with_entry(self, key: str, value: str) -> WorkerMemory:
        """Return a new :class:`WorkerMemory` with ``key`` set to ``value``."""
        new_entries = [(k, v) for k, v in self.entries if k != key]
        new_entries.append((key, value))
        # Trim to capacity (drop oldest = first)
        if len(new_entries) > self.capacity:
            new_entries = new_entries[-self.capacity :]
        return WorkerMemory(
            entries=tuple(new_entries),
            capacity=self.capacity,
        )

    def forget(self, key: str) -> WorkerMemory:
        """Return a new :class:`WorkerMemory` with ``key`` removed."""
        return WorkerMemory(
            entries=tuple((k, v) for k, v in self.entries if k != key),
            capacity=self.capacity,
        )

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True)
class WorkerState:
    """The immutable state snapshot of a worker.

    Parameters:
        id: Unique worker identifier.
        name: Human-readable display name.
        role: :class:`WorkerRole`.
        kind: :class:`WorkerKind` (permanent or temporary).
        status: :class:`WorkerStatus`.
        skills: Tuple of :class:`WorkerSkill` instances.
        memory: The worker's personal :class:`WorkerMemory`.
        current_task_id: The id of the task currently being executed (or "").
        created_at: When the worker was created.
        last_active_at: When the worker was last active (or None).
        tasks_completed: Total number of tasks completed.
        tasks_failed: Total number of tasks failed.
        metadata: Immutable metadata mapping.
    """

    id: str
    name: str
    role: str
    kind: str = WorkerKind.PERMANENT.value
    status: str = WorkerStatus.OFFLINE.value
    skills: tuple[WorkerSkill, ...] = ()
    memory: WorkerMemory = field(default_factory=WorkerMemory)
    current_task_id: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    last_active_at: datetime | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Tasks
# ===========================================================================


@dataclass(frozen=True)
class TaskArtifact:
    """An artifact produced by a task.

    Parameters:
        id: Unique artifact identifier.
        kind: Artifact kind (e.g. "code", "document", "image").
        name: Display name.
        path: Filesystem path or URL.
        size_bytes: Size in bytes (0 = unknown).
        created_at: When the artifact was created.
    """

    id: str
    kind: str = "file"
    name: str = ""
    path: str = ""
    size_bytes: int = 0
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class Task:
    """A unit of work assigned to a worker.

    Parameters:
        id: Unique task identifier.
        title: Short title.
        description: Longer description of what to do.
        status: :class:`TaskStatus`.
        priority: :class:`TaskPriority`.
        assignee_id: The worker id assigned to this task (or "").
        team_id: The team this task belongs to (or "").
        parent_task_id: Optional parent task (for sub-tasks).
        dependencies: Tuple of task ids this task depends on.
        artifacts: Tuple of :class:`TaskArtifact` produced by this task.
        created_at: When the task was created.
        assigned_at: When the task was assigned (or None).
        started_at: When work started (or None).
        completed_at: When the task completed (or None).
        required_role: Optional :class:`WorkerRole` required for this task.
        required_skills: Tuple of skill names required.
        estimated_duration_minutes: Estimated duration (0 = unknown).
        actual_duration_minutes: Actual duration (0 = not yet completed).
        quality_score: Quality score from review (0.0 to 1.0, or -1 = unreviewed).
        review_notes: Free-form review notes.
        metadata: Immutable metadata mapping.
    """

    id: str
    title: str
    description: str = ""
    status: str = TaskStatus.PENDING.value
    priority: str = TaskPriority.NORMAL.value
    assignee_id: str = ""
    team_id: str = ""
    parent_task_id: str = ""
    dependencies: tuple[str, ...] = ()
    artifacts: tuple[TaskArtifact, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    required_role: str = ""
    required_skills: tuple[str, ...] = ()
    estimated_duration_minutes: float = 0.0
    actual_duration_minutes: float = 0.0
    quality_score: float = -1.0
    review_notes: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Communication
# ===========================================================================


@dataclass(frozen=True)
class Message:
    """A message exchanged between workers.

    Parameters:
        id: Unique message identifier.
        sender_id: The sending worker id.
        recipient_id: The receiving worker id (or "" for broadcast).
        team_id: The team context (or "" for direct messages).
        kind: :class:`MessageKind`.
        subject: Short subject line.
        body: Message body.
        task_id: Optional task this message is about.
        timestamp: When the message was sent.
        read: Whether the message has been read.
        reply_to: Optional message id this is a reply to.
    """

    id: str
    sender_id: str
    recipient_id: str = ""
    team_id: str = ""
    kind: str = MessageKind.INFO.value
    subject: str = ""
    body: str = ""
    task_id: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    read: bool = False
    reply_to: str = ""


# ===========================================================================
# Delegation
# ===========================================================================


@dataclass(frozen=True)
class Delegation:
    """A record of one worker delegating to another.

    Parameters:
        id: Unique delegation identifier.
        from_worker_id: The delegating worker.
        to_worker_id: The receiving worker.
        task_id: The task being delegated.
        reason: Why the delegation was made.
        timestamp: When the delegation occurred.
        accepted: Whether the receiving worker accepted.
        accepted_at: When accepted (or None).
    """

    id: str
    from_worker_id: str
    to_worker_id: str
    task_id: str
    reason: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    accepted: bool = False
    accepted_at: datetime | None = None


# ===========================================================================
# Approvals
# ===========================================================================


@dataclass(frozen=True)
class Approval:
    """A request for and decision on an approval.

    Parameters:
        id: Unique approval identifier.
        requester_id: The worker requesting approval.
        approver_id: The worker granting/denying approval (or "" if pending).
        task_id: The task the approval is for.
        kind: What kind of approval (e.g. "design", "deployment", "merge").
        description: What is being approved.
        requested_at: When the approval was requested.
        decided_at: When the decision was made (or None).
        granted: Whether the approval was granted (None = pending).
        notes: Free-form notes from the approver.
    """

    id: str
    requester_id: str
    approver_id: str = ""
    task_id: str = ""
    kind: str = "general"
    description: str = ""
    requested_at: datetime = field(default_factory=_utcnow)
    decided_at: datetime | None = None
    granted: bool | None = None
    notes: str = ""


# ===========================================================================
# Escalations and conflicts
# ===========================================================================


@dataclass(frozen=True)
class Escalation:
    """An escalation from a worker to the supervisor.

    Parameters:
        id: Unique escalation identifier.
        from_worker_id: The escalating worker.
        supervisor_id: The supervisor handling the escalation (or "").
        task_id: The task that triggered the escalation (or "").
        level: :class:`EscalationLevel`.
        message: The escalation message.
        timestamp: When the escalation was raised.
        resolved: Whether the escalation has been resolved.
        resolved_at: When resolved (or None).
        resolution: Free-form resolution notes.
    """

    id: str
    from_worker_id: str
    supervisor_id: str = ""
    task_id: str = ""
    level: str = EscalationLevel.LOW.value
    message: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    resolved: bool = False
    resolved_at: datetime | None = None
    resolution: str = ""


@dataclass(frozen=True)
class Conflict:
    """A conflict between workers that the supervisor resolves.

    Parameters:
        id: Unique conflict identifier.
        kind: :class:`ConflictKind`.
        worker_ids: Tuple of conflicting worker ids.
        task_ids: Tuple of task ids involved.
        description: What the conflict is about.
        timestamp: When the conflict was detected.
        resolution: :class:`ConflictResolution` (or "" if unresolved).
        resolved: Whether the conflict has been resolved.
        resolved_at: When resolved (or None).
        resolution_notes: Free-form resolution notes.
    """

    id: str
    kind: str = ConflictKind.RESOURCE.value
    worker_ids: tuple[str, ...] = ()
    task_ids: tuple[str, ...] = ()
    description: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    resolution: str = ""
    resolved: bool = False
    resolved_at: datetime | None = None
    resolution_notes: str = ""


# ===========================================================================
# Reviews
# ===========================================================================


@dataclass(frozen=True)
class Review:
    """A quality review of a task's output.

    Parameters:
        id: Unique review identifier.
        task_id: The task being reviewed.
        reviewer_id: The reviewing worker id.
        verdict: :class:`ReviewVerdict`.
        quality_score: Quality score (0.0 to 1.0).
        notes: Free-form review notes.
        timestamp: When the review was performed.
        rework_required: Whether rework is required.
    """

    id: str
    task_id: str
    reviewer_id: str
    verdict: str = ReviewVerdict.APPROVED.value
    quality_score: float = 0.8
    notes: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    rework_required: bool = False


# ===========================================================================
# Shifts
# ===========================================================================


@dataclass(frozen=True)
class Shift:
    """A worker's shift.

    Parameters:
        id: Unique shift identifier.
        worker_id: The worker this shift belongs to.
        start: Shift start time.
        end: Shift end time.
        status: :class:`ShiftStatus`.
        tasks_completed: Number of tasks completed during this shift.
        metadata: Immutable metadata mapping.
    """

    id: str
    worker_id: str
    start: datetime = field(default_factory=_utcnow)
    end: datetime = field(default_factory=_utcnow)
    status: str = ShiftStatus.SCHEDULED.value
    tasks_completed: int = 0
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Teams
# ===========================================================================


@dataclass(frozen=True)
class Team:
    """A team of workers collaborating on a shared goal.

    Parameters:
        id: Unique team identifier.
        name: Team display name.
        goal: The team's goal.
        lead_id: The team lead's worker id (or "").
        member_ids: Tuple of member worker ids.
        created_at: When the team was created.
        disbanded_at: When the team was disbanded (or None).
        kind: :class:`WorkerKind` — permanent or temporary team.
        metadata: Immutable metadata mapping.
    """

    id: str
    name: str
    goal: str = ""
    lead_id: str = ""
    member_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    disbanded_at: datetime | None = None
    kind: str = WorkerKind.PERMANENT.value
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Metrics
# ===========================================================================


@dataclass(frozen=True)
class WorkerMetrics:
    """Productivity metrics for a single worker.

    Parameters:
        worker_id: The worker these metrics describe.
        tasks_assigned: Total tasks assigned.
        tasks_completed: Total tasks completed.
        tasks_failed: Total tasks failed.
        tasks_rejected: Total tasks rejected in review.
        average_quality: Average quality score (0.0 to 1.0).
        average_duration_minutes: Average task duration.
        total_artifacts: Total artifacts produced.
        delegations_made: Total delegations to other workers.
        delegations_received: Total delegations received.
        escalations: Total escalations raised.
        messages_sent: Total messages sent.
        messages_received: Total messages received.
        last_updated: When these metrics were last computed.
    """

    worker_id: str
    tasks_assigned: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_rejected: int = 0
    average_quality: float = 0.0
    average_duration_minutes: float = 0.0
    total_artifacts: int = 0
    delegations_made: int = 0
    delegations_received: int = 0
    escalations: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    last_updated: datetime = field(default_factory=_utcnow)

    def completion_rate(self) -> float:
        """Return the fraction of assigned tasks that completed (0.0 to 1.0)."""
        if self.tasks_assigned == 0:
            return 0.0
        return self.tasks_completed / self.tasks_assigned

    def failure_rate(self) -> float:
        """Return the fraction of assigned tasks that failed (0.0 to 1.0)."""
        if self.tasks_assigned == 0:
            return 0.0
        return self.tasks_failed / self.tasks_assigned


@dataclass(frozen=True)
class TeamMetrics:
    """Aggregate productivity metrics for a team.

    Parameters:
        team_id: The team these metrics describe.
        worker_count: Number of workers on the team.
        tasks_total: Total tasks across the team.
        tasks_completed: Total completed.
        tasks_failed: Total failed.
        average_quality: Team-wide average quality score.
        total_artifacts: Total artifacts produced.
        conflicts: Total conflicts recorded.
        escalations: Total escalations.
        last_updated: When these metrics were last computed.
    """

    team_id: str
    worker_count: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    average_quality: float = 0.0
    total_artifacts: int = 0
    conflicts: int = 0
    escalations: int = 0
    last_updated: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Reports
# ===========================================================================


@dataclass(frozen=True)
class WorkforceReport:
    """A snapshot report of the entire workforce.

    Parameters:
        id: Unique report identifier.
        generated_at: When the report was generated.
        total_workers: Total number of workers.
        active_workers: Number of currently-active workers.
        total_teams: Total number of teams.
        active_teams: Number of active teams.
        total_tasks: Total tasks across all teams.
        completed_tasks: Total completed tasks.
        failed_tasks: Total failed tasks.
        in_progress_tasks: Tasks currently in progress.
        average_quality: Workforce-wide average quality.
        total_artifacts: Total artifacts produced.
        total_delegations: Total delegations.
        total_escalations: Total escalations.
        total_conflicts: Total conflicts.
        worker_metrics: Tuple of per-worker :class:`WorkerMetrics`.
        team_metrics: Tuple of per-team :class:`TeamMetrics`.
        period_start: Start of the reporting period (or None).
        period_end: End of the reporting period (or None).
    """

    id: str
    generated_at: datetime = field(default_factory=_utcnow)
    total_workers: int = 0
    active_workers: int = 0
    total_teams: int = 0
    active_teams: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    in_progress_tasks: int = 0
    average_quality: float = 0.0
    total_artifacts: int = 0
    total_delegations: int = 0
    total_escalations: int = 0
    total_conflicts: int = 0
    worker_metrics: tuple[WorkerMetrics, ...] = ()
    team_metrics: tuple[TeamMetrics, ...] = ()
    period_start: datetime | None = None
    period_end: datetime | None = None


# ===========================================================================
# Callback type aliases (for dependency injection)
# ===========================================================================


#: A callback that "thinks" about a goal — typically delegates to Brain.think().
ThinkFn = Callable[..., Any]

#: A callback that executes a task — typically delegates to ExecutionEngine.run().
ExecuteFn = Callable[..., Any]

#: A callback that generates text — typically delegates to ProviderManager.generate().
GenerateFn = Callable[..., Any]


__all__ = [
    "Approval",
    "Conflict",
    "ConflictKind",
    "ConflictResolution",
    "Delegation",
    "Escalation",
    "EscalationLevel",
    "ExecuteFn",
    "GenerateFn",
    "Message",
    "MessageKind",
    "Review",
    "ReviewVerdict",
    "Shift",
    "ShiftStatus",
    "Task",
    "TaskArtifact",
    "TaskPriority",
    "TaskStatus",
    "Team",
    "TeamMetrics",
    "ThinkFn",
    "WorkerKind",
    "WorkerMemory",
    "WorkerMetrics",
    "WorkerRole",
    "WorkerSkill",
    "WorkerState",
    "WorkerStatus",
    "WorkforceReport",
    "_new_id",
    "_utcnow",
    "priority_rank",
]
