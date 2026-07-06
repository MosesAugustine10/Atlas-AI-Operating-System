"""Collaboration orchestrator — the top-level facade.

The :class:`CollaborationOrchestrator` wires together every
collaboration engine (session, conversation, delegation, negotiation,
consensus, handoff, conflict, coordination, memory, artifacts,
patterns) into a single facade. It is the entry point for
multi-agent collaboration.

The orchestrator never imports Brain, Workforce, or any Atlas
subsystem directly — it receives a ``think_fn`` callback that
coordination pipelines call to produce outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.collaboration.artifacts import ArtifactRegistry
from atlas.collaboration.conflict import ConflictEngine
from atlas.collaboration.consensus import ConsensusEngine
from atlas.collaboration.conversation import ConversationManager
from atlas.collaboration.coordination import CoordinationEngine
from atlas.collaboration.delegation import DelegationEngine
from atlas.collaboration.handoff import HandoffEngine
from atlas.collaboration.memory import SharedMemory
from atlas.collaboration.models import (
    CollaborationSession,
)
from atlas.collaboration.negotiation import NegotiationEngine
from atlas.collaboration.patterns import PatternLibrary
from atlas.collaboration.session import SessionManager


class CollaborationOrchestrator:
    """Top-level orchestrator for multi-agent collaboration.

    Parameters:
        think_fn: Optional callback passed to the :class:`CoordinationEngine`
            for pipeline step execution.
    """

    def __init__(
        self,
        think_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.sessions = SessionManager()
        self.conversations = ConversationManager()
        self.delegations = DelegationEngine()
        self.negotiations = NegotiationEngine()
        self.consensus = ConsensusEngine()
        self.handoffs = HandoffEngine()
        self.conflicts = ConflictEngine()
        self.coordination = CoordinationEngine(think_fn=think_fn)
        self.memory = SharedMemory()
        self.artifacts = ArtifactRegistry()
        self.patterns = PatternLibrary(engine=self.coordination)
        self._think_fn = think_fn

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        name: str = "",
        goal: str = "",
        coordinator_id: str = "",
        participant_ids: tuple[str, ...] = (),
    ) -> CollaborationSession:
        """Create a new collaboration session."""
        session = self.sessions.create(
            name=name,
            goal=goal,
            coordinator_id=coordinator_id,
            participant_ids=participant_ids,
        )
        return session

    def start_session(self, session_id: str) -> CollaborationSession:
        """Start a session."""
        return self.sessions.start(session_id)

    def complete_session(self, session_id: str) -> CollaborationSession:
        """Mark a session as completed."""
        return self.sessions.complete(session_id)

    def get_session(self, session_id: str) -> CollaborationSession | None:
        """Return the session with ``session_id`` or ``None``."""
        return self.sessions.get(session_id)

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    def start_conversation(
        self,
        session_id: str,
        topic: str = "",
        participant_ids: tuple[str, ...] = (),
    ):
        """Start a new conversation in a session."""
        return self.conversations.create(
            session_id=session_id,
            topic=topic,
            participant_ids=participant_ids,
        )

    def speak(
        self,
        conversation_id: str,
        agent_id: str,
        content: str,
        kind: str = "info",
        reply_to: str = "",
    ):
        """Add a turn to a conversation."""
        return self.conversations.add_turn(
            conversation_id=conversation_id,
            agent_id=agent_id,
            content=content,
            kind=kind,
            reply_to=reply_to,
        )

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    def delegate(
        self,
        session_id: str,
        from_agent_id: str,
        to_agent_id: str,
        task_description: str = "",
        reason: str = "",
    ):
        """Delegate work from one agent to another."""
        return self.delegations.delegate(
            session_id=session_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task_description=task_description,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Negotiation
    # ------------------------------------------------------------------

    def negotiate(
        self,
        session_id: str,
        topic: str,
        initiator_id: str,
        participant_ids: tuple[str, ...] = (),
    ):
        """Start a negotiation."""
        return self.negotiations.start(
            session_id=session_id,
            topic=topic,
            initiator_id=initiator_id,
            participant_ids=participant_ids,
        )

    # ------------------------------------------------------------------
    # Consensus
    # ------------------------------------------------------------------

    def propose_vote(
        self,
        session_id: str,
        topic: str,
        proposal: str,
        proposer_id: str,
        eligible_voter_ids: tuple[str, ...] = (),
        required_majority: float = 0.5,
    ):
        """Start a consensus round."""
        return self.consensus.propose(
            session_id=session_id,
            topic=topic,
            proposal=proposal,
            proposer_id=proposer_id,
            eligible_voter_ids=eligible_voter_ids,
            required_majority=required_majority,
        )

    # ------------------------------------------------------------------
    # Handoff
    # ------------------------------------------------------------------

    def handoff(
        self,
        session_id: str,
        from_agent_id: str,
        to_agent_id: str,
        task_description: str = "",
    ):
        """Initiate a work handoff."""
        return self.handoffs.initiate(
            session_id=session_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task_description=task_description,
        )

    # ------------------------------------------------------------------
    # Conflict
    # ------------------------------------------------------------------

    def report_conflict(
        self,
        session_id: str,
        agent_ids: tuple[str, ...],
        description: str = "",
        kind: str = "disagreement",
    ):
        """Report a conflict."""
        return self.conflicts.report(
            session_id=session_id,
            kind=kind,
            agent_ids=agent_ids,
            description=description,
        )

    # ------------------------------------------------------------------
    # Shared memory
    # ------------------------------------------------------------------

    def remember(self, session_id: str, key: str, value: str, author_id: str = ""):
        """Write to the shared session memory."""
        return self.memory.write(
            session_id=session_id,
            key=key,
            value=value,
            author_id=author_id,
        )

    def recall(self, session_id: str, key: str) -> str | None:
        """Read from the shared session memory."""
        return self.memory.read(session_id=session_id, key=key)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def produce_artifact(
        self,
        session_id: str,
        producer_id: str,
        name: str = "",
        content: str = "",
        kind: str = "file",
    ):
        """Produce a shared artifact."""
        return self.artifacts.produce(
            session_id=session_id,
            producer_id=producer_id,
            kind=kind,
            name=name,
            content=content,
        )

    # ------------------------------------------------------------------
    # Patterns
    # ------------------------------------------------------------------

    def run_pattern(
        self,
        pattern_name: str,
        session_id: str,
        agent_ids: dict[str, Any],
    ):
        """Build and return a collaboration pattern by name."""
        return self.patterns.build(
            pattern_name=pattern_name,
            session_id=session_id,
            agent_ids=agent_ids,
        )

    def execute_pipeline(self, pipeline_id: str, initial_input: str = ""):
        """Execute a coordination pipeline."""
        return self.coordination.execute(pipeline_id, initial_input=initial_input)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return a summary of the orchestrator's state."""
        return {
            "sessions": self.sessions.count(),
            "active_sessions": len(self.sessions.active_sessions()),
            "conversations": self.conversations.conversation_count(),
            "delegations": self.delegations.count(),
            "negotiations": self.negotiations.count(),
            "consensus_rounds": self.consensus.count(),
            "handoffs": self.handoffs.count(),
            "conflicts": self.conflicts.count(),
            "open_conflicts": self.conflicts.open_count(),
            "pipelines": self.coordination.count(),
            "memory_entries": self.memory.count(),
            "artifacts": self.artifacts.count(),
            "patterns": len(self.patterns.pattern_names()),
        }


__all__ = ["CollaborationOrchestrator"]
