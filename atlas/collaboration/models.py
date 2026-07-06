"""Atlas Multi-Agent Collaboration data models — frozen dataclasses and enums.

This module is a *leaf* in the collaboration package dependency graph.
It defines every value object exchanged between the session,
conversation, delegation, negotiation, consensus, handoff, conflict,
coordination, memory, artifacts, patterns, and orchestrator layers.
Nothing here imports Brain, Workforce, or any other Atlas subsystem —
the models are pure, immutable and dependency-free.

The Collaboration Layer sits ABOVE the Workforce in the Atlas stack:

    User
      ↓
    Collaboration  ← this package
      ↓
    Workforce
      ↓
    Brain
      ↓
    Execution
      ↓
    Runtime
      ↓
    Providers / MCP / Workflows

The collaboration package NEVER imports concrete implementations.
It receives callbacks (e.g. ``think_fn``, ``delegate_fn``) via
dependency injection and calls them. This keeps the package fully
decoupled from every concrete Atlas subsystem.
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


def _new_id(prefix: str = "collab") -> str:
    """Return a new unique identifier prefixed with ``prefix``."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ===========================================================================
# Enumerations
# ===========================================================================


class SessionStatus(enum.StrEnum):
    """Lifecycle status of a collaboration session.

    Attributes:
        PENDING: The session has been created but not started.
        ACTIVE: The session is actively running.
        PAUSED: The session has been paused.
        COMPLETED: The session completed successfully.
        FAILED: The session failed.
        CANCELLED: The session was cancelled.
        ARCHIVED: The session has been archived.
    """

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class AgentRole(enum.StrEnum):
    """Roles an agent can play in a collaboration session.

    Attributes:
        COORDINATOR: The session coordinator — orchestrates the others.
        RESEARCHER: Gathers information and context.
        PLANNER: Decomposes goals into tasks.
        CODER: Writes code.
        REVIEWER: Reviews work.
        DESIGNER: Creates visual assets.
        WRITER: Writes documentation or content.
        TESTER: Tests and validates.
        DEPLOYER: Deploys the result.
        OBSERVER: A silent observer (logs but does not participate).
    """

    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    DESIGNER = "designer"
    WRITER = "writer"
    TESTER = "tester"
    DEPLOYER = "deployer"
    OBSERVER = "observer"


class TurnStatus(enum.StrEnum):
    """Status of a conversation turn.

    Attributes:
        PENDING: The turn has been queued but not started.
        IN_PROGRESS: The agent is generating its response.
        COMPLETED: The turn completed successfully.
        FAILED: The turn failed.
        SKIPPED: The turn was skipped.
        CANCELLED: The turn was cancelled.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TurnKind(enum.StrEnum):
    """Kinds of conversation turns.

    Attributes:
        PROPOSAL: The agent proposes an idea or plan.
        COUNTER: A counter-proposal in response to another proposal.
        QUESTION: The agent asks a question.
        ANSWER: The agent answers a question.
        INFO: Informational message.
        UPDATE: A status update.
        AGREEMENT: The agent agrees with a prior turn.
        DISAGREEMENT: The agent disagrees with a prior turn.
        REQUEST: The agent requests an action.
        RESPONSE: A response to a prior request.
    """

    PROPOSAL = "proposal"
    COUNTER = "counter"
    QUESTION = "question"
    ANSWER = "answer"
    INFO = "info"
    UPDATE = "update"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    REQUEST = "request"
    RESPONSE = "response"


class DelegationStatus(enum.StrEnum):
    """Status of a delegation.

    Attributes:
        PENDING: The delegation has been proposed but not accepted.
        ACCEPTED: The delegatee accepted the delegation.
        REJECTED: The delegatee rejected the delegation.
        COMPLETED: The delegated work was completed.
        FAILED: The delegated work failed.
        CANCELLED: The delegation was cancelled.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NegotiationStatus(enum.StrEnum):
    """Status of a negotiation.

    Attributes:
        OPEN: The negotiation is open (proposals being exchanged).
        COUNTERED: A counter-proposal has been made.
        ACCEPTED: An offer has been accepted.
        REJECTED: The negotiation was rejected.
        EXPIRED: The negotiation expired without resolution.
        WITHDRAWN: The initiator withdrew the negotiation.
    """

    OPEN = "open"
    COUNTERED = "countered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class VoteKind(enum.StrEnum):
    """Kinds of votes in a consensus round.

    Attributes:
        YES: Affirmative vote.
        NO: Negative vote.
        ABSTAIN: The voter abstains.
        VETO: The voter vetoes the proposal.
    """

    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"
    VETO = "veto"


class ConsensusStatus(enum.StrEnum):
    """Status of a consensus round.

    Attributes:
        OPEN: Voting is open.
        REACHED: Consensus was reached (majority YES, no VETO).
        REJECTED: The proposal was rejected (majority NO or any VETO).
        TIED: The vote was tied.
        EXPIRED: The voting period expired without a quorum.
    """

    OPEN = "open"
    REACHED = "reached"
    REJECTED = "rejected"
    TIED = "tied"
    EXPIRED = "expired"


class HandoffStatus(enum.StrEnum):
    """Status of a work handoff.

    Attributes:
        INITIATED: The handoff has been initiated by the sender.
        ACCEPTED: The receiver accepted the handoff.
        REJECTED: The receiver rejected the handoff.
        COMPLETED: The handoff was completed (receiver finished the work).
        FAILED: The handoff failed.
    """

    INITIATED = "initiated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class ConflictKind(enum.StrEnum):
    """Kinds of conflicts between agents.

    Attributes:
        DISAGREEMENT: Agents disagree on an approach.
        RESOURCE: Agents need the same resource.
        PRIORITY: Agents have conflicting priorities.
        SCOPE: Agents disagree on task scope.
        DEADLOCK: A dependency cycle or blocking chain.
    """

    DISAGREEMENT = "disagreement"
    RESOURCE = "resource"
    PRIORITY = "priority"
    SCOPE = "scope"
    DEADLOCK = "deadlock"


class ConflictResolution(enum.StrEnum):
    """How a conflict was resolved.

    Attributes:
        MEDIATED: The coordinator mediated a compromise.
        VOTED: The conflict was put to a vote.
        ESCALATED: The conflict was escalated to a higher authority.
        AUTO_RESOLVED: The conflict was auto-resolved by policy.
        SPLIT: The work was split between the conflicting agents.
        DEFERRED: The conflict was deferred for later review.
    """

    MEDIATED = "mediated"
    VOTED = "voted"
    ESCALATED = "escalated"
    AUTO_RESOLVED = "auto_resolved"
    SPLIT = "split"
    DEFERRED = "deferred"


class CoordinationPattern(enum.StrEnum):
    """Built-in coordination patterns.

    Attributes:
        PIPELINE: Sequential pipeline (A → B → C → ...).
        FAN_OUT: One initiator, many parallel workers.
        FAN_IN: Many workers, one aggregator.
        ROUND_ROBIN: Agents take turns in a round-robin.
        DEBATE: Agents debate a proposal, then vote.
        HIERARCHICAL: Coordinator delegates to sub-coordinators.
        PEER_TO_PEER: Agents collaborate as equals.
    """

    PIPELINE = "pipeline"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"
    ROUND_ROBIN = "round_robin"
    DEBATE = "debate"
    HIERARCHICAL = "hierarchical"
    PEER_TO_PEER = "peer_to_peer"


# ===========================================================================
# Core models
# ===========================================================================


@dataclass(frozen=True)
class AgentRef:
    """A reference to an agent participating in a collaboration.

    The collaboration package never imports the :class:`Worker` class
    directly — it references agents by id and role. This keeps the
    package decoupled from the workforce package.

    Parameters:
        id: The agent's unique identifier.
        name: Human-readable display name.
        role: :class:`AgentRole` in this session.
        capabilities: Tuple of capability strings (e.g. "code", "research").
        metadata: Immutable metadata mapping.
    """

    id: str
    name: str = ""
    role: str = AgentRole.OBSERVER.value
    capabilities: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CollaborationSession:
    """A collaboration session — the top-level container.

    Parameters:
        id: Unique session identifier.
        name: Session display name.
        goal: The high-level goal of the session.
        status: :class:`SessionStatus`.
        coordinator_id: The coordinating agent's id.
        participant_ids: Tuple of participant agent ids.
        created_at: When the session was created.
        started_at: When the session started (or None).
        completed_at: When the session completed (or None).
        metadata: Immutable metadata mapping.
    """

    id: str
    name: str = ""
    goal: str = ""
    status: str = SessionStatus.PENDING.value
    coordinator_id: str = ""
    participant_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Turn:
    """A single turn in a conversation.

    Parameters:
        id: Unique turn identifier.
        session_id: The session this turn belongs to.
        conversation_id: The conversation this turn belongs to.
        agent_id: The agent who produced this turn.
        kind: :class:`TurnKind`.
        content: The turn's text content.
        status: :class:`TurnStatus`.
        reply_to: Optional turn id this is a reply to.
        created_at: When the turn was created.
        completed_at: When the turn completed (or None).
        artifacts: Tuple of artifact ids produced by this turn.
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    conversation_id: str
    agent_id: str
    kind: str = TurnKind.INFO.value
    content: str = ""
    status: str = TurnStatus.PENDING.value
    reply_to: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    artifacts: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Conversation:
    """A conversation thread within a session.

    Parameters:
        id: Unique conversation identifier.
        session_id: The session this conversation belongs to.
        topic: Short topic description.
        participant_ids: Tuple of participating agent ids.
        turns: Tuple of :class:`Turn` instances.
        created_at: When the conversation was created.
        closed_at: When the conversation was closed (or None).
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    topic: str = ""
    participant_ids: tuple[str, ...] = ()
    turns: tuple[Turn, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    closed_at: datetime | None = None
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Delegation
# ===========================================================================


@dataclass(frozen=True)
class Delegation:
    """A delegation of work from one agent to another.

    Parameters:
        id: Unique delegation identifier.
        session_id: The session this delegation belongs to.
        from_agent_id: The delegating agent.
        to_agent_id: The receiving agent.
        task_description: What is being delegated.
        status: :class:`DelegationStatus`.
        reason: Why the delegation was made.
        created_at: When the delegation was created.
        decided_at: When the delegatee accepted/rejected (or None).
        completed_at: When the delegated work completed (or None).
        result: The result of the delegated work (or "").
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    from_agent_id: str
    to_agent_id: str
    task_description: str = ""
    status: str = DelegationStatus.PENDING.value
    reason: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    decided_at: datetime | None = None
    completed_at: datetime | None = None
    result: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Negotiation
# ===========================================================================


@dataclass(frozen=True)
class Offer:
    """A single offer in a negotiation.

    Parameters:
        id: Unique offer identifier.
        negotiation_id: The negotiation this offer belongs to.
        agent_id: The agent making the offer.
        terms: The terms being offered (free-form text).
        created_at: When the offer was made.
        withdrawn: Whether the offer was withdrawn.
    """

    id: str
    negotiation_id: str
    agent_id: str
    terms: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    withdrawn: bool = False


@dataclass(frozen=True)
class Negotiation:
    """A negotiation between agents.

    Parameters:
        id: Unique negotiation identifier.
        session_id: The session this negotiation belongs to.
        topic: What is being negotiated.
        initiator_id: The agent who started the negotiation.
        participant_ids: Tuple of participating agent ids.
        status: :class:`NegotiationStatus`.
        offers: Tuple of :class:`Offer` instances.
        created_at: When the negotiation was created.
        resolved_at: When the negotiation was resolved (or None).
        accepted_offer_id: The id of the accepted offer (or "").
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    topic: str = ""
    initiator_id: str = ""
    participant_ids: tuple[str, ...] = ()
    status: str = NegotiationStatus.OPEN.value
    offers: tuple[Offer, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    accepted_offer_id: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Consensus / Voting
# ===========================================================================


@dataclass(frozen=True)
class Vote:
    """A single vote in a consensus round.

    Parameters:
        id: Unique vote identifier.
        consensus_id: The consensus round this vote belongs to.
        voter_id: The agent casting the vote.
        kind: :class:`VoteKind`.
        reason: Optional reason for the vote.
        timestamp: When the vote was cast.
    """

    id: str
    consensus_id: str
    voter_id: str
    kind: str = VoteKind.YES.value
    reason: str = ""
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class Consensus:
    """A consensus (voting) round.

    Parameters:
        id: Unique consensus identifier.
        session_id: The session this consensus belongs to.
        topic: What is being voted on.
        proposal: The text of the proposal.
        proposer_id: The agent who proposed the topic.
        eligible_voter_ids: Tuple of agent ids eligible to vote.
        votes: Tuple of :class:`Vote` instances.
        status: :class:`ConsensusStatus`.
        required_majority: Fraction of YES votes required (0.0 to 1.0).
        created_at: When the consensus round was created.
        closed_at: When the round was closed (or None).
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    topic: str = ""
    proposal: str = ""
    proposer_id: str = ""
    eligible_voter_ids: tuple[str, ...] = ()
    votes: tuple[Vote, ...] = ()
    status: str = ConsensusStatus.OPEN.value
    required_majority: float = 0.5
    created_at: datetime = field(default_factory=_utcnow)
    closed_at: datetime | None = None
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Handoffs
# ===========================================================================


@dataclass(frozen=True)
class HandoffContext:
    """Context transferred during a handoff.

    Parameters:
        summary: A summary of the work done so far.
        artifacts: Tuple of artifact ids being handed off.
        notes: Free-form notes for the receiver.
        state: Immutable state mapping (e.g. progress, blockers).
    """

    summary: str = ""
    artifacts: tuple[str, ...] = ()
    notes: str = ""
    state: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Handoff:
    """A work handoff between agents.

    Parameters:
        id: Unique handoff identifier.
        session_id: The session this handoff belongs to.
        from_agent_id: The handing-off agent.
        to_agent_id: The receiving agent.
        task_description: What is being handed off.
        context: :class:`HandoffContext` transferred.
        status: :class:`HandoffStatus`.
        created_at: When the handoff was initiated.
        decided_at: When the receiver accepted/rejected (or None).
        completed_at: When the work was completed (or None).
        result: The result of the handed-off work (or "").
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    from_agent_id: str
    to_agent_id: str
    task_description: str = ""
    context: HandoffContext = field(default_factory=HandoffContext)
    status: str = HandoffStatus.INITIATED.value
    created_at: datetime = field(default_factory=_utcnow)
    decided_at: datetime | None = None
    completed_at: datetime | None = None
    result: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Conflicts
# ===========================================================================


@dataclass(frozen=True)
class Conflict:
    """A conflict between agents.

    Parameters:
        id: Unique conflict identifier.
        session_id: The session this conflict belongs to.
        kind: :class:`ConflictKind`.
        agent_ids: Tuple of conflicting agent ids.
        description: What the conflict is about.
        status: "open" or "resolved".
        resolution: :class:`ConflictResolution` (or "" if unresolved).
        created_at: When the conflict was detected.
        resolved_at: When the conflict was resolved (or None).
        resolution_notes: Free-form resolution notes.
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    kind: str = ConflictKind.DISAGREEMENT.value
    agent_ids: tuple[str, ...] = ()
    description: str = ""
    status: str = "open"
    resolution: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    resolution_notes: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Shared artifacts
# ===========================================================================


@dataclass(frozen=True)
class SharedArtifact:
    """An artifact shared between agents.

    Parameters:
        id: Unique artifact identifier.
        session_id: The session this artifact belongs to.
        producer_id: The agent who produced the artifact.
        kind: Artifact kind (e.g. "code", "document", "image").
        name: Display name.
        content: The artifact's content (text or base64).
        path: Optional filesystem path.
        tags: Tuple of tags.
        created_at: When the artifact was produced.
        consumer_ids: Tuple of agent ids who have consumed the artifact.
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    producer_id: str
    kind: str = "file"
    name: str = ""
    content: str = ""
    path: str = ""
    tags: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    consumer_ids: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Shared memory
# ===========================================================================


@dataclass(frozen=True)
class SharedMemoryEntry:
    """A single entry in the shared collaboration memory.

    Parameters:
        id: Unique entry identifier.
        session_id: The session this entry belongs to.
        key: The memory key.
        value: The memory value.
        author_id: The agent who wrote the entry.
        created_at: When the entry was written.
        tags: Tuple of tags.
    """

    id: str
    session_id: str
    key: str
    value: str = ""
    author_id: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    tags: tuple[str, ...] = ()


# ===========================================================================
# Coordination patterns
# ===========================================================================


@dataclass(frozen=True)
class PipelineStep:
    """A single step in a pipeline coordination pattern.

    Parameters:
        id: Unique step identifier.
        pipeline_id: The pipeline this step belongs to.
        agent_id: The agent executing this step.
        role: :class:`AgentRole` for this step.
        order: 0-based ordering within the pipeline.
        input_artifact_ids: Tuple of artifact ids consumed by this step.
        output_artifact_ids: Tuple of artifact ids produced by this step.
        status: Step status ("pending", "in_progress", "completed", "failed").
        started_at: When the step started (or None).
        completed_at: When the step completed (or None).
        result: The step's result (or "").
    """

    id: str
    pipeline_id: str
    agent_id: str
    role: str = AgentRole.CODER.value
    order: int = 0
    input_artifact_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str = ""


@dataclass(frozen=True)
class Pipeline:
    """A pipeline coordination pattern.

    Parameters:
        id: Unique pipeline identifier.
        session_id: The session this pipeline belongs to.
        name: Pipeline display name.
        steps: Tuple of :class:`PipelineStep` instances.
        status: Pipeline status.
        created_at: When the pipeline was created.
        completed_at: When the pipeline completed (or None).
        metadata: Immutable metadata mapping.
    """

    id: str
    session_id: str
    name: str = ""
    steps: tuple[PipelineStep, ...] = ()
    status: str = "pending"
    created_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Callback type aliases (for dependency injection)
# ===========================================================================


#: A callback that "thinks" about a goal — typically Brain.think or Worker.execute_task.
ThinkFn = Callable[..., Any]

#: A callback that delegates work to an agent.
DelegateFn = Callable[..., Any]

#: A callback that generates text for an agent.
GenerateFn = Callable[..., Any]


__all__ = [
    "AgentRef",
    "AgentRole",
    "CollaborationSession",
    "Conflict",
    "ConflictKind",
    "ConflictResolution",
    "Consensus",
    "ConsensusStatus",
    "Conversation",
    "CoordinationPattern",
    "DelegateFn",
    "Delegation",
    "DelegationStatus",
    "GenerateFn",
    "Handoff",
    "HandoffContext",
    "HandoffStatus",
    "Negotiation",
    "NegotiationStatus",
    "Offer",
    "Pipeline",
    "PipelineStep",
    "SessionStatus",
    "SharedArtifact",
    "SharedMemoryEntry",
    "ThinkFn",
    "Turn",
    "TurnKind",
    "TurnStatus",
    "Vote",
    "VoteKind",
    "_new_id",
    "_utcnow",
]
