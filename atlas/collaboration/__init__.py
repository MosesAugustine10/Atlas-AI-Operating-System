"""Atlas Multi-Agent Collaboration Engine — enterprise-grade collaboration.

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

This package orchestrates multi-agent collaboration through dependency
injection. It NEVER imports concrete implementations — it receives
callbacks (e.g. ``think_fn``) via dependency injection and calls them.

Modules:

* :mod:`atlas.collaboration.models` — frozen dataclasses and enums (leaf).
* :mod:`atlas.collaboration.session` — :class:`SessionManager` for session lifecycle.
* :mod:`atlas.collaboration.conversation` — :class:`ConversationManager` for turns.
* :mod:`atlas.collaboration.delegation` — :class:`DelegationEngine` for task delegation.
* :mod:`atlas.collaboration.negotiation` — :class:`NegotiationEngine` for propose/counter/accept.
* :mod:`atlas.collaboration.consensus` — :class:`ConsensusEngine` for voting.
* :mod:`atlas.collaboration.handoff` — :class:`HandoffEngine` for work handoffs.
* :mod:`atlas.collaboration.conflict` — :class:`ConflictEngine` for conflict resolution.
* :mod:`atlas.collaboration.coordination` — :class:`CoordinationEngine` for patterns.
* :mod:`atlas.collaboration.memory` — :class:`SharedMemory` for session-scoped memory.
* :mod:`atlas.collaboration.artifacts` — :class:`ArtifactRegistry` for shared outputs.
* :mod:`atlas.collaboration.patterns` — :class:`PatternLibrary` for ready-made patterns.
* :mod:`atlas.collaboration.orchestrator` — :class:`CollaborationOrchestrator` top-level facade.

Usage:

    from atlas.collaboration import CollaborationOrchestrator

    orch = CollaborationOrchestrator()
    session = orch.create_session(name="Build app", goal="Hello world")
    orch.start_session(session.id)
    conv = orch.start_conversation(session.id, topic="Planning")
    orch.speak(conv.id, "agent_1", "Let's start with research")
"""

from __future__ import annotations

__version__ = "1.0.0"


# Re-export models (pure Python, always available)
# Re-export engines (pure Python, always available)
from atlas.collaboration.artifacts import ArtifactRegistry  # noqa: E402
from atlas.collaboration.conflict import ConflictEngine, ConflictError  # noqa: E402
from atlas.collaboration.consensus import ConsensusEngine, ConsensusError  # noqa: E402
from atlas.collaboration.conversation import (  # noqa: E402
    ConversationError,
    ConversationManager,
)
from atlas.collaboration.coordination import (  # noqa: E402
    CoordinationEngine,
    CoordinationError,
)
from atlas.collaboration.delegation import (
    DelegationEngine,
    DelegationError,
)  # noqa: E402
from atlas.collaboration.handoff import HandoffEngine, HandoffError  # noqa: E402
from atlas.collaboration.memory import SharedMemory  # noqa: E402
from atlas.collaboration.models import (  # noqa: E402
    AgentRef,
    AgentRole,
    CollaborationSession,
    Conflict,
    ConflictKind,
    ConflictResolution,
    Consensus,
    ConsensusStatus,
    Conversation,
    CoordinationPattern,
    DelegateFn,
    Delegation,
    DelegationStatus,
    GenerateFn,
    Handoff,
    HandoffContext,
    HandoffStatus,
    Negotiation,
    NegotiationStatus,
    Offer,
    Pipeline,
    PipelineStep,
    SessionStatus,
    SharedArtifact,
    SharedMemoryEntry,
    ThinkFn,
    Turn,
    TurnKind,
    TurnStatus,
    Vote,
    VoteKind,
)
from atlas.collaboration.negotiation import (  # noqa: E402
    NegotiationEngine,
    NegotiationError,
)
from atlas.collaboration.orchestrator import CollaborationOrchestrator  # noqa: E402
from atlas.collaboration.patterns import PatternLibrary  # noqa: E402
from atlas.collaboration.session import SessionError, SessionManager  # noqa: E402

__all__ = [
    "__version__",
    # Models
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
    # Engines
    "ArtifactRegistry",
    "ConflictEngine",
    "ConflictError",
    "ConsensusEngine",
    "ConsensusError",
    "ConversationError",
    "ConversationManager",
    "CoordinationEngine",
    "CoordinationError",
    "DelegationEngine",
    "DelegationError",
    "HandoffEngine",
    "HandoffError",
    "NegotiationEngine",
    "NegotiationError",
    "SessionError",
    "SessionManager",
    "SharedMemory",
    "PatternLibrary",
    "CollaborationOrchestrator",
]
