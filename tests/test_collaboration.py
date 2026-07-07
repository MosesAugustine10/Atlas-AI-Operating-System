"""Tests for the Atlas Multi-Agent Collaboration Engine (Phase 6).

Covers every module: models, session, conversation, delegation,
negotiation, consensus, handoff, conflict, coordination, memory,
artifacts, patterns, orchestrator. All tests are deterministic and
headless.
"""

from __future__ import annotations

import pytest

from atlas.collaboration import (
    AgentRef,
    AgentRole,
    ArtifactRegistry,
    CollaborationOrchestrator,
    CollaborationSession,
    Conflict,
    ConflictEngine,
    ConflictKind,
    ConflictResolution,
    Consensus,
    ConsensusEngine,
    ConsensusError,
    ConsensusStatus,
    Conversation,
    ConversationError,
    ConversationManager,
    CoordinationEngine,
    CoordinationError,
    CoordinationPattern,
    Delegation,
    DelegationEngine,
    DelegationError,
    DelegationStatus,
    Handoff,
    HandoffContext,
    HandoffEngine,
    HandoffError,
    HandoffStatus,
    Negotiation,
    NegotiationEngine,
    NegotiationError,
    NegotiationStatus,
    Offer,
    PatternLibrary,
    Pipeline,
    PipelineStep,
    SessionError,
    SessionManager,
    SessionStatus,
    SharedArtifact,
    SharedMemory,
    SharedMemoryEntry,
    Turn,
    TurnKind,
    TurnStatus,
    Vote,
    VoteKind,
    __version__,
)

# ===========================================================================
# Package
# ===========================================================================


class TestPackage:
    def test_version(self) -> None:
        assert __version__ == "1.0.0"

    def test_exports(self) -> None:
        from atlas.collaboration import __all__

        assert "CollaborationOrchestrator" in __all__
        assert "SessionManager" in __all__
        assert "ConversationManager" in __all__
        assert "CoordinationEngine" in __all__
        assert "PatternLibrary" in __all__


# ===========================================================================
# Enums
# ===========================================================================


class TestEnums:
    def test_session_status_count(self) -> None:
        assert len(list(SessionStatus)) == 7

    def test_agent_role_count(self) -> None:
        assert len(list(AgentRole)) == 10

    def test_turn_status_count(self) -> None:
        assert len(list(TurnStatus)) == 6

    def test_turn_kind_count(self) -> None:
        assert len(list(TurnKind)) == 10

    def test_delegation_status_count(self) -> None:
        assert len(list(DelegationStatus)) == 6

    def test_negotiation_status_count(self) -> None:
        assert len(list(NegotiationStatus)) == 6

    def test_vote_kind_count(self) -> None:
        assert len(list(VoteKind)) == 4

    def test_consensus_status_count(self) -> None:
        assert len(list(ConsensusStatus)) == 5

    def test_handoff_status_count(self) -> None:
        assert len(list(HandoffStatus)) == 5

    def test_conflict_kind_count(self) -> None:
        assert len(list(ConflictKind)) == 5

    def test_conflict_resolution_count(self) -> None:
        assert len(list(ConflictResolution)) == 6

    def test_coordination_pattern_count(self) -> None:
        assert len(list(CoordinationPattern)) == 7


# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    def test_agent_ref(self) -> None:
        a = AgentRef(id="a1", name="Alice", role=AgentRole.CODER.value)
        assert a.id == "a1"
        assert a.role == AgentRole.CODER.value

    def test_collaboration_session_default(self) -> None:
        s = CollaborationSession(id="s1")
        assert s.status == SessionStatus.PENDING.value
        assert s.participant_ids == ()

    def test_collaboration_session_frozen(self) -> None:
        s = CollaborationSession(id="s1")
        with pytest.raises(Exception):
            s.status = SessionStatus.ACTIVE.value  # type: ignore[misc]

    def test_turn(self) -> None:
        t = Turn(id="t1", session_id="s1", conversation_id="c1", agent_id="a1")
        assert t.status == TurnStatus.PENDING.value
        assert t.kind == TurnKind.INFO.value

    def test_conversation(self) -> None:
        c = Conversation(id="c1", session_id="s1")
        assert c.turns == ()
        assert c.closed_at is None

    def test_delegation(self) -> None:
        d = Delegation(
            id="d1",
            session_id="s1",
            from_agent_id="a1",
            to_agent_id="a2",
        )
        assert d.status == DelegationStatus.PENDING.value

    def test_offer(self) -> None:
        o = Offer(id="o1", negotiation_id="n1", agent_id="a1")
        assert o.withdrawn is False

    def test_negotiation(self) -> None:
        n = Negotiation(id="n1", session_id="s1")
        assert n.status == NegotiationStatus.OPEN.value

    def test_vote(self) -> None:
        v = Vote(id="v1", consensus_id="c1", voter_id="a1")
        assert v.kind == VoteKind.YES.value

    def test_consensus(self) -> None:
        c = Consensus(id="c1", session_id="s1")
        assert c.status == ConsensusStatus.OPEN.value
        assert c.required_majority == 0.5

    def test_handoff_context(self) -> None:
        ctx = HandoffContext(summary="done", notes="good")
        assert ctx.summary == "done"

    def test_handoff(self) -> None:
        h = Handoff(
            id="h1",
            session_id="s1",
            from_agent_id="a1",
            to_agent_id="a2",
        )
        assert h.status == HandoffStatus.INITIATED.value

    def test_conflict(self) -> None:
        c = Conflict(id="c1", session_id="s1")
        assert c.kind == ConflictKind.DISAGREEMENT.value
        assert c.status == "open"

    def test_shared_artifact(self) -> None:
        a = SharedArtifact(id="a1", session_id="s1", producer_id="p1")
        assert a.kind == "file"
        assert a.consumer_ids == ()

    def test_shared_memory_entry(self) -> None:
        e = SharedMemoryEntry(id="e1", session_id="s1", key="k")
        assert e.value == ""

    def test_pipeline_step(self) -> None:
        s = PipelineStep(id="s1", pipeline_id="p1", agent_id="a1")
        assert s.status == "pending"

    def test_pipeline(self) -> None:
        p = Pipeline(id="p1", session_id="s1")
        assert p.steps == ()
        assert p.status == "pending"


# ===========================================================================
# SessionManager
# ===========================================================================


class TestSessionManager:
    def test_create(self) -> None:
        m = SessionManager()
        s = m.create(name="Test", goal="Goal")
        assert s.name == "Test"
        assert s.status == SessionStatus.PENDING.value

    def test_get(self) -> None:
        m = SessionManager()
        s = m.create()
        assert m.get(s.id) is s

    def test_start(self) -> None:
        m = SessionManager()
        s = m.create()
        m.start(s.id)
        assert m.get(s.id).status == SessionStatus.ACTIVE.value

    def test_start_non_pending_raises(self) -> None:
        m = SessionManager()
        s = m.create()
        m.start(s.id)
        with pytest.raises(SessionError):
            m.start(s.id)

    def test_pause_resume(self) -> None:
        m = SessionManager()
        s = m.create()
        m.start(s.id)
        m.pause(s.id)
        assert m.get(s.id).status == SessionStatus.PAUSED.value
        m.resume(s.id)
        assert m.get(s.id).status == SessionStatus.ACTIVE.value

    def test_complete(self) -> None:
        m = SessionManager()
        s = m.create()
        m.complete(s.id)
        assert m.get(s.id).status == SessionStatus.COMPLETED.value

    def test_fail(self) -> None:
        m = SessionManager()
        s = m.create()
        m.fail(s.id)
        assert m.get(s.id).status == SessionStatus.FAILED.value

    def test_cancel(self) -> None:
        m = SessionManager()
        s = m.create()
        m.cancel(s.id)
        assert m.get(s.id).status == SessionStatus.CANCELLED.value

    def test_archive(self) -> None:
        m = SessionManager()
        s = m.create()
        m.archive(s.id)
        assert m.get(s.id).status == SessionStatus.ARCHIVED.value

    def test_join_leave(self) -> None:
        m = SessionManager()
        s = m.create()
        m.join(s.id, "a1")
        assert m.is_participant(s.id, "a1")
        m.leave(s.id, "a1")
        assert not m.is_participant(s.id, "a1")

    def test_join_idempotent(self) -> None:
        m = SessionManager()
        s = m.create()
        m.join(s.id, "a1")
        m.join(s.id, "a1")
        assert len(m.participants(s.id)) == 1

    def test_list_sessions(self) -> None:
        m = SessionManager()
        m.create()
        m.create()
        assert len(m.list_sessions()) == 2

    def test_list_by_status(self) -> None:
        m = SessionManager()
        s = m.create()
        m.start(s.id)
        assert len(m.list_sessions(status=SessionStatus.ACTIVE.value)) == 1

    def test_active_sessions(self) -> None:
        m = SessionManager()
        s = m.create()
        m.start(s.id)
        assert len(m.active_sessions()) == 1

    def test_completed_sessions(self) -> None:
        m = SessionManager()
        s = m.create()
        m.complete(s.id)
        assert len(m.completed_sessions()) == 1

    def test_count(self) -> None:
        m = SessionManager()
        m.create()
        assert m.count() == 1

    def test_count_by_status(self) -> None:
        m = SessionManager()
        s1 = m.create()
        s2 = m.create()
        m.start(s1.id)
        counts = m.count_by_status()
        assert counts[SessionStatus.ACTIVE.value] == 1
        assert counts[SessionStatus.PENDING.value] == 1


# ===========================================================================
# ConversationManager
# ===========================================================================


class TestConversationManager:
    def test_create(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1", topic="Planning")
        assert c.topic == "Planning"

    def test_get(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        assert m.get(c.id) is c

    def test_list_conversations(self) -> None:
        m = ConversationManager()
        m.create(session_id="s1")
        m.create(session_id="s1")
        assert len(m.list_conversations()) == 2

    def test_list_by_session(self) -> None:
        m = ConversationManager()
        m.create(session_id="s1")
        m.create(session_id="s2")
        assert len(m.list_conversations(session_id="s1")) == 1

    def test_add_turn(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        t = m.add_turn(c.id, "a1", "Hello")
        assert t.content == "Hello"
        assert t.agent_id == "a1"

    def test_list_turns(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "A")
        m.add_turn(c.id, "a2", "B")
        assert len(m.list_turns(c.id)) == 2

    def test_list_turns_by_kind(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "Q", kind=TurnKind.QUESTION.value)
        m.add_turn(c.id, "a2", "A", kind=TurnKind.ANSWER.value)
        assert len(m.list_turns(c.id, kind=TurnKind.QUESTION.value)) == 1

    def test_list_turns_by_agent(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "A")
        m.add_turn(c.id, "a2", "B")
        assert len(m.list_turns(c.id, agent_id="a1")) == 1

    def test_turn_count(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "A")
        assert m.turn_count(c.id) == 1

    def test_last_turn(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "First")
        t2 = m.add_turn(c.id, "a2", "Second")
        assert m.last_turn(c.id).id == t2.id

    def test_last_turn_none(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        assert m.last_turn(c.id) is None

    def test_replies(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        t1 = m.add_turn(c.id, "a1", "Original")
        t2 = m.add_turn(c.id, "a2", "Reply", reply_to=t1.id)
        replies = m.replies(t1.id)
        assert len(replies) == 1
        assert replies[0].id == t2.id

    def test_thread(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        t1 = m.add_turn(c.id, "a1", "Root")
        t2 = m.add_turn(c.id, "a2", "Reply 1", reply_to=t1.id)
        t3 = m.add_turn(c.id, "a1", "Reply 2", reply_to=t2.id)
        thread = m.thread(t1.id)
        assert len(thread) == 3

    def test_close(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.close(c.id)
        assert m.get(c.id).closed_at is not None

    def test_turns_by_agent(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "A")
        m.add_turn(c.id, "a1", "B")
        m.add_turn(c.id, "a2", "C")
        counts = m.turns_by_agent(c.id)
        assert counts["a1"] == 2
        assert counts["a2"] == 1

    def test_count_by_kind(self) -> None:
        m = ConversationManager()
        c = m.create(session_id="s1")
        m.add_turn(c.id, "a1", "A", kind=TurnKind.INFO.value)
        m.add_turn(c.id, "a2", "B", kind=TurnKind.QUESTION.value)
        counts = m.count_by_kind(c.id)
        assert counts[TurnKind.INFO.value] == 1

    def test_conversation_count(self) -> None:
        m = ConversationManager()
        m.create(session_id="s1")
        assert m.conversation_count() == 1

    def test_unknown_conversation_raises(self) -> None:
        m = ConversationManager()
        with pytest.raises(ConversationError):
            m.add_turn("missing", "a1", "x")


# ===========================================================================
# DelegationEngine
# ===========================================================================


class TestDelegationEngine:
    def test_delegate(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2", "Do work")
        assert d.from_agent_id == "a1"
        assert d.status == DelegationStatus.PENDING.value

    def test_delegate_self_raises(self) -> None:
        e = DelegationEngine()
        with pytest.raises(DelegationError):
            e.delegate("s1", "a1", "a1")

    def test_accept(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2")
        e.accept(d.id)
        assert e.get(d.id).status == DelegationStatus.ACCEPTED.value

    def test_reject(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2")
        e.reject(d.id)
        assert e.get(d.id).status == DelegationStatus.REJECTED.value

    def test_complete(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2")
        e.complete(d.id, result="done")
        assert e.get(d.id).status == DelegationStatus.COMPLETED.value
        assert e.get(d.id).result == "done"

    def test_fail(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2")
        e.fail(d.id, error="boom")
        assert e.get(d.id).status == DelegationStatus.FAILED.value

    def test_cancel(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2")
        e.cancel(d.id)
        assert e.get(d.id).status == DelegationStatus.CANCELLED.value

    def test_by_delegator(self) -> None:
        e = DelegationEngine()
        e.delegate("s1", "a1", "a2")
        e.delegate("s1", "a1", "a3")
        assert len(e.by_delegator("a1")) == 2

    def test_by_delegatee(self) -> None:
        e = DelegationEngine()
        e.delegate("s1", "a1", "a2")
        e.delegate("s1", "a3", "a2")
        assert len(e.by_delegatee("a2")) == 2

    def test_pending(self) -> None:
        e = DelegationEngine()
        e.delegate("s1", "a1", "a2")
        assert len(e.pending()) == 1

    def test_completed(self) -> None:
        e = DelegationEngine()
        d = e.delegate("s1", "a1", "a2")
        e.complete(d.id)
        assert len(e.completed()) == 1

    def test_count(self) -> None:
        e = DelegationEngine()
        e.delegate("s1", "a1", "a2")
        assert e.count() == 1

    def test_acceptance_rate(self) -> None:
        e = DelegationEngine()
        d1 = e.delegate("s1", "a1", "a2")
        d2 = e.delegate("s1", "a1", "a3")
        e.accept(d1.id)
        e.reject(d2.id)
        assert e.acceptance_rate() == 0.5

    def test_acceptance_rate_no_decisions(self) -> None:
        e = DelegationEngine()
        assert e.acceptance_rate() == 0.0


# ===========================================================================
# NegotiationEngine
# ===========================================================================


class TestNegotiationEngine:
    def test_start(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        assert n.status == NegotiationStatus.OPEN.value

    def test_propose(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        o = e.propose(n.id, "a1", terms="100 dollars")
        assert o.terms == "100 dollars"

    def test_counter(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        e.propose(n.id, "a1", terms="100")
        e.counter(n.id, "a2", terms="80")
        assert e.get(n.id).status == NegotiationStatus.COUNTERED.value

    def test_accept(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        o = e.propose(n.id, "a1", terms="100")
        e.accept(n.id, o.id)
        assert e.get(n.id).status == NegotiationStatus.ACCEPTED.value

    def test_reject(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        e.reject(n.id)
        assert e.get(n.id).status == NegotiationStatus.REJECTED.value

    def test_withdraw_offer(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        o = e.propose(n.id, "a1", terms="100")
        e.withdraw_offer(n.id, o.id)
        assert e.get(n.id).offers[0].withdrawn is True

    def test_withdraw(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        e.withdraw(n.id)
        assert e.get(n.id).status == NegotiationStatus.WITHDRAWN.value

    def test_expire(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        e.expire(n.id)
        assert e.get(n.id).status == NegotiationStatus.EXPIRED.value

    def test_accept_unknown_offer_raises(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        with pytest.raises(NegotiationError):
            e.accept(n.id, "missing")

    def test_accept_withdrawn_offer_raises(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        o = e.propose(n.id, "a1", terms="100")
        e.withdraw_offer(n.id, o.id)
        with pytest.raises(NegotiationError):
            e.accept(n.id, o.id)

    def test_offers(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        e.propose(n.id, "a1", terms="100")
        e.propose(n.id, "a2", terms="80")
        assert len(e.offers(n.id)) == 2

    def test_active_offers(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        o1 = e.propose(n.id, "a1", terms="100")
        e.propose(n.id, "a2", terms="80")
        e.withdraw_offer(n.id, o1.id)
        assert len(e.active_offers(n.id)) == 1

    def test_accepted_offer(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="Price", initiator_id="a1")
        o = e.propose(n.id, "a1", terms="100")
        e.accept(n.id, o.id)
        assert e.accepted_offer(n.id).id == o.id

    def test_open_negotiations(self) -> None:
        e = NegotiationEngine()
        e.start("s1", topic="A", initiator_id="a1")
        assert len(e.open_negotiations()) == 1

    def test_count(self) -> None:
        e = NegotiationEngine()
        e.start("s1", topic="A", initiator_id="a1")
        assert e.count() == 1

    def test_count_by_status(self) -> None:
        e = NegotiationEngine()
        n = e.start("s1", topic="A", initiator_id="a1")
        e.reject(n.id)
        counts = e.count_by_status()
        assert counts[NegotiationStatus.REJECTED.value] == 1


# ===========================================================================
# ConsensusEngine
# ===========================================================================


class TestConsensusEngine:
    def test_propose(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", topic="Deploy?", proposal="Yes", proposer_id="a1")
        assert c.status == ConsensusStatus.OPEN.value

    def test_invalid_majority_raises(self) -> None:
        e = ConsensusEngine()
        with pytest.raises(ConsensusError):
            e.propose("s1", required_majority=0.0)

    def test_vote(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1", "a2"))
        v = e.vote(c.id, "a1", kind=VoteKind.YES.value)
        assert v.kind == VoteKind.YES.value

    def test_vote_replaces_existing(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1",))
        e.vote(c.id, "a1", kind=VoteKind.YES.value)
        e.vote(c.id, "a1", kind=VoteKind.NO.value)
        assert e.vote_count(c.id) == 1

    def test_vote_ineligible_raises(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1",))
        with pytest.raises(ConsensusError):
            e.vote(c.id, "a2")

    def test_vote_closed_raises(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1",))
        e.close(c.id)
        with pytest.raises(ConsensusError):
            e.vote(c.id, "a1")

    def test_close_reached(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1", "a2", "a3"))
        e.vote(c.id, "a1", kind=VoteKind.YES.value)
        e.vote(c.id, "a2", kind=VoteKind.YES.value)
        e.vote(c.id, "a3", kind=VoteKind.NO.value)
        e.close(c.id)
        assert e.get(c.id).status == ConsensusStatus.REACHED.value

    def test_close_rejected(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1", "a2", "a3"))
        e.vote(c.id, "a1", kind=VoteKind.NO.value)
        e.vote(c.id, "a2", kind=VoteKind.NO.value)
        e.vote(c.id, "a3", kind=VoteKind.YES.value)
        e.close(c.id)
        assert e.get(c.id).status == ConsensusStatus.REJECTED.value

    def test_close_veto_rejects(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1", "a2"))
        e.vote(c.id, "a1", kind=VoteKind.YES.value)
        e.vote(c.id, "a2", kind=VoteKind.VETO.value)
        e.close(c.id)
        assert e.get(c.id).status == ConsensusStatus.REJECTED.value

    def test_close_tied(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1", "a2"))
        e.vote(c.id, "a1", kind=VoteKind.YES.value)
        e.vote(c.id, "a2", kind=VoteKind.NO.value)
        e.close(c.id)
        assert e.get(c.id).status == ConsensusStatus.TIED.value

    def test_close_no_votes_expired(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1",))
        e.close(c.id)
        assert e.get(c.id).status == ConsensusStatus.EXPIRED.value

    def test_expire(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1")
        e.expire(c.id)
        assert e.get(c.id).status == ConsensusStatus.EXPIRED.value

    def test_tally(self) -> None:
        e = ConsensusEngine()
        c = e.propose("s1", eligible_voter_ids=("a1", "a2"))
        e.vote(c.id, "a1", kind=VoteKind.YES.value)
        e.vote(c.id, "a2", kind=VoteKind.NO.value)
        tally = e.tally(c.id)
        assert tally[VoteKind.YES.value] == 1
        assert tally[VoteKind.NO.value] == 1

    def test_open_rounds(self) -> None:
        e = ConsensusEngine()
        e.propose("s1")
        assert len(e.open_rounds()) == 1

    def test_count(self) -> None:
        e = ConsensusEngine()
        e.propose("s1")
        assert e.count() == 1

    def test_consensus_rate(self) -> None:
        e = ConsensusEngine()
        c1 = e.propose("s1", eligible_voter_ids=("a1",))
        e.vote(c1.id, "a1", kind=VoteKind.YES.value)
        e.close(c1.id)
        c2 = e.propose("s1", eligible_voter_ids=("a1",))
        e.vote(c2.id, "a1", kind=VoteKind.NO.value)
        e.close(c2.id)
        assert e.consensus_rate() == 0.5


# ===========================================================================
# HandoffEngine
# ===========================================================================


class TestHandoffEngine:
    def test_initiate(self) -> None:
        e = HandoffEngine()
        h = e.initiate("s1", "a1", "a2", "Do work")
        assert h.status == HandoffStatus.INITIATED.value

    def test_initiate_self_raises(self) -> None:
        e = HandoffEngine()
        with pytest.raises(HandoffError):
            e.initiate("s1", "a1", "a1")

    def test_accept(self) -> None:
        e = HandoffEngine()
        h = e.initiate("s1", "a1", "a2")
        e.accept(h.id)
        assert e.get(h.id).status == HandoffStatus.ACCEPTED.value

    def test_reject(self) -> None:
        e = HandoffEngine()
        h = e.initiate("s1", "a1", "a2")
        e.reject(h.id)
        assert e.get(h.id).status == HandoffStatus.REJECTED.value

    def test_complete(self) -> None:
        e = HandoffEngine()
        h = e.initiate("s1", "a1", "a2")
        e.complete(h.id, result="done")
        assert e.get(h.id).status == HandoffStatus.COMPLETED.value

    def test_fail(self) -> None:
        e = HandoffEngine()
        h = e.initiate("s1", "a1", "a2")
        e.fail(h.id)
        assert e.get(h.id).status == HandoffStatus.FAILED.value

    def test_by_sender(self) -> None:
        e = HandoffEngine()
        e.initiate("s1", "a1", "a2")
        assert len(e.by_sender("a1")) == 1

    def test_by_receiver(self) -> None:
        e = HandoffEngine()
        e.initiate("s1", "a1", "a2")
        assert len(e.by_receiver("a2")) == 1

    def test_pending(self) -> None:
        e = HandoffEngine()
        e.initiate("s1", "a1", "a2")
        assert len(e.pending()) == 1

    def test_count(self) -> None:
        e = HandoffEngine()
        e.initiate("s1", "a1", "a2")
        assert e.count() == 1

    def test_acceptance_rate(self) -> None:
        e = HandoffEngine()
        h1 = e.initiate("s1", "a1", "a2")
        h2 = e.initiate("s1", "a1", "a3")
        e.accept(h1.id)
        e.reject(h2.id)
        assert e.acceptance_rate() == 0.5

    def test_with_context(self) -> None:
        e = HandoffEngine()
        ctx = HandoffContext(summary="half done", notes="continue from here")
        h = e.initiate("s1", "a1", "a2", context=ctx)
        assert h.context.summary == "half done"


# ===========================================================================
# ConflictEngine
# ===========================================================================


class TestConflictEngine:
    def test_report(self) -> None:
        e = ConflictEngine()
        c = e.report("s1", agent_ids=("a1", "a2"), description="Disagree")
        assert c.status == "open"

    def test_resolve(self) -> None:
        e = ConflictEngine()
        c = e.report("s1", agent_ids=("a1", "a2"))
        e.resolve(c.id, resolution=ConflictResolution.MEDIATED.value)
        assert e.get(c.id).status == "resolved"

    def test_open_conflicts(self) -> None:
        e = ConflictEngine()
        e.report("s1", agent_ids=("a1", "a2"))
        assert len(e.open_conflicts()) == 1

    def test_resolved_conflicts(self) -> None:
        e = ConflictEngine()
        c = e.report("s1", agent_ids=("a1", "a2"))
        e.resolve(c.id)
        assert len(e.resolved_conflicts()) == 1

    def test_conflicts_involving(self) -> None:
        e = ConflictEngine()
        e.report("s1", agent_ids=("a1", "a2"))
        e.report("s1", agent_ids=("a1", "a3"))
        assert len(e.conflicts_involving("a1")) == 2

    def test_count(self) -> None:
        e = ConflictEngine()
        e.report("s1", agent_ids=("a1", "a2"))
        assert e.count() == 1

    def test_open_count(self) -> None:
        e = ConflictEngine()
        e.report("s1", agent_ids=("a1", "a2"))
        assert e.open_count() == 1

    def test_count_by_kind(self) -> None:
        e = ConflictEngine()
        e.report("s1", kind=ConflictKind.RESOURCE.value)
        e.report("s1", kind=ConflictKind.PRIORITY.value)
        counts = e.count_by_kind()
        assert counts[ConflictKind.RESOURCE.value] == 1

    def test_count_by_resolution(self) -> None:
        e = ConflictEngine()
        c = e.report("s1")
        e.resolve(c.id, resolution=ConflictResolution.MEDIATED.value)
        counts = e.count_by_resolution()
        assert counts[ConflictResolution.MEDIATED.value] == 1


# ===========================================================================
# CoordinationEngine
# ===========================================================================


class TestCoordinationEngine:
    def test_build_pipeline(self) -> None:
        e = CoordinationEngine()
        p = e.build_pipeline("s1", [("a1", "coder"), ("a2", "reviewer")])
        assert len(p.steps) == 2

    def test_build_fan_out(self) -> None:
        e = CoordinationEngine()
        p = e.build_fan_out("s1", "c1", ["w1", "w2", "w3"])
        assert len(p.steps) == 4  # initiator + 3 workers

    def test_build_fan_in(self) -> None:
        e = CoordinationEngine()
        p = e.build_fan_in("s1", ["w1", "w2"], "agg1")
        assert len(p.steps) == 3  # 2 workers + aggregator

    def test_build_round_robin(self) -> None:
        e = CoordinationEngine()
        p = e.build_round_robin("s1", ["a1", "a2"], rounds=2)
        assert len(p.steps) == 4  # 2 agents × 2 rounds

    def test_build_debate(self) -> None:
        e = CoordinationEngine()
        p = e.build_debate("s1", ["p1", "p2"], ["v1", "v2"])
        assert len(p.steps) == 4  # 2 proposers + 2 voters

    def test_execute_no_fn(self) -> None:
        e = CoordinationEngine()
        p = e.build_pipeline("s1", [("a1", "coder"), ("a2", "reviewer")])
        result = e.execute(p.id)
        assert result.status == "completed"
        assert all(s.status == "completed" for s in result.steps)

    def test_execute_with_fn(self) -> None:
        calls: list[str] = []

        def fake_think(**kwargs: object) -> str:
            calls.append(str(kwargs.get("agent_id", "")))
            return "result"

        e = CoordinationEngine(think_fn=fake_think)
        p = e.build_pipeline("s1", [("a1", "coder"), ("a2", "reviewer")])
        e.execute(p.id)
        assert len(calls) == 2

    def test_step_count(self) -> None:
        e = CoordinationEngine()
        p = e.build_pipeline("s1", [("a1", "coder"), ("a2", "reviewer")])
        assert e.step_count(p.id) == 2

    def test_completed_steps(self) -> None:
        e = CoordinationEngine()
        p = e.build_pipeline("s1", [("a1", "coder"), ("a2", "reviewer")])
        e.execute(p.id)
        assert e.completed_steps(p.id) == 2

    def test_progress(self) -> None:
        e = CoordinationEngine()
        p = e.build_pipeline("s1", [("a1", "coder"), ("a2", "reviewer")])
        e.execute(p.id)
        assert e.progress(p.id) == 1.0

    def test_count(self) -> None:
        e = CoordinationEngine()
        e.build_pipeline("s1", [("a1", "coder")])
        assert e.count() == 1

    def test_unknown_pipeline_raises(self) -> None:
        e = CoordinationEngine()
        with pytest.raises(CoordinationError):
            e.execute("missing")


# ===========================================================================
# SharedMemory
# ===========================================================================


class TestSharedMemory:
    def test_write_read(self) -> None:
        m = SharedMemory()
        m.write("s1", "key", "value")
        assert m.read("s1", "key") == "value"

    def test_read_missing(self) -> None:
        m = SharedMemory()
        assert m.read("s1", "key") is None

    def test_overwrite(self) -> None:
        m = SharedMemory()
        m.write("s1", "key", "v1")
        m.write("s1", "key", "v2")
        assert m.read("s1", "key") == "v2"

    def test_delete(self) -> None:
        m = SharedMemory()
        m.write("s1", "key", "value")
        assert m.delete("s1", "key") is True
        assert m.read("s1", "key") is None

    def test_delete_missing(self) -> None:
        m = SharedMemory()
        assert m.delete("s1", "key") is False

    def test_keys(self) -> None:
        m = SharedMemory()
        m.write("s1", "k1", "v1")
        m.write("s1", "k2", "v2")
        assert set(m.keys("s1")) == {"k1", "k2"}

    def test_entries(self) -> None:
        m = SharedMemory()
        m.write("s1", "k1", "v1")
        m.write("s1", "k2", "v2")
        assert len(m.entries("s1")) == 2

    def test_search(self) -> None:
        m = SharedMemory()
        m.write("s1", "hello", "world")
        m.write("s1", "other", "value")
        results = m.search("s1", "hello")
        assert len(results) == 1

    def test_by_tag(self) -> None:
        m = SharedMemory()
        m.write("s1", "k1", "v1", tags=("important",))
        m.write("s1", "k2", "v2", tags=("trivial",))
        assert len(m.by_tag("s1", "important")) == 1

    def test_count(self) -> None:
        m = SharedMemory()
        m.write("s1", "k1", "v1")
        assert m.count() == 1

    def test_count_per_session(self) -> None:
        m = SharedMemory()
        m.write("s1", "k1", "v1")
        m.write("s2", "k1", "v2")
        assert m.count("s1") == 1

    def test_clear(self) -> None:
        m = SharedMemory()
        m.write("s1", "k1", "v1")
        m.write("s1", "k2", "v2")
        assert m.clear("s1") == 2
        assert m.count("s1") == 0

    def test_session_isolation(self) -> None:
        m = SharedMemory()
        m.write("s1", "key", "v1")
        m.write("s2", "key", "v2")
        assert m.read("s1", "key") == "v1"
        assert m.read("s2", "key") == "v2"


# ===========================================================================
# ArtifactRegistry
# ===========================================================================


class TestArtifactRegistry:
    def test_produce(self) -> None:
        r = ArtifactRegistry()
        a = r.produce("s1", "p1", name="output.txt")
        assert a.name == "output.txt"

    def test_get(self) -> None:
        r = ArtifactRegistry()
        a = r.produce("s1", "p1")
        assert r.get(a.id) is a

    def test_consume(self) -> None:
        r = ArtifactRegistry()
        a = r.produce("s1", "p1")
        r.consume(a.id, "c1")
        assert "c1" in r.get(a.id).consumer_ids

    def test_consume_idempotent(self) -> None:
        r = ArtifactRegistry()
        a = r.produce("s1", "p1")
        r.consume(a.id, "c1")
        r.consume(a.id, "c1")
        assert r.get(a.id).consumer_ids.count("c1") == 1

    def test_list_artifacts(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1")
        r.produce("s1", "p2")
        assert len(r.list_artifacts()) == 2

    def test_list_by_session(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1")
        r.produce("s2", "p2")
        assert len(r.list_artifacts(session_id="s1")) == 1

    def test_list_by_kind(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1", kind="code")
        r.produce("s1", "p2", kind="doc")
        assert len(r.list_artifacts(kind="code")) == 1

    def test_list_by_producer(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1")
        r.produce("s1", "p2")
        assert len(r.list_artifacts(producer_id="p1")) == 1

    def test_by_producer(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1")
        r.produce("s1", "p2")
        assert len(r.by_producer("p1")) == 1

    def test_consumed_by(self) -> None:
        r = ArtifactRegistry()
        a = r.produce("s1", "p1")
        r.consume(a.id, "c1")
        assert len(r.consumed_by("c1")) == 1

    def test_search(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1", name="hello.txt")
        r.produce("s1", "p2", name="other.txt")
        assert len(r.search("hello")) == 1

    def test_count(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1")
        assert r.count() == 1

    def test_count_by_kind(self) -> None:
        r = ArtifactRegistry()
        r.produce("s1", "p1", kind="code")
        r.produce("s1", "p2", kind="code")
        r.produce("s1", "p3", kind="doc")
        counts = r.count_by_kind()
        assert counts["code"] == 2

    def test_delete(self) -> None:
        r = ArtifactRegistry()
        a = r.produce("s1", "p1")
        assert r.delete(a.id) is True


# ===========================================================================
# PatternLibrary
# ===========================================================================


class TestPatternLibrary:
    def test_research_plan_code_review(self) -> None:
        lib = PatternLibrary()
        p = lib.research_plan_code_review("s1", "r1", "p1", "c1", "rv1")
        assert len(p.steps) == 4

    def test_code_review_deploy(self) -> None:
        lib = PatternLibrary()
        p = lib.code_review_deploy("s1", "c1", "r1", "d1")
        assert len(p.steps) == 3

    def test_research_write_review_publish(self) -> None:
        lib = PatternLibrary()
        p = lib.research_write_review_publish("s1", "r1", "w1", "rv1", "d1")
        assert len(p.steps) == 4

    def test_design_review_iterate(self) -> None:
        lib = PatternLibrary()
        p = lib.design_review_iterate("s1", "d1", "r1", rounds=3)
        assert len(p.steps) == 6  # 3 rounds × 2 steps

    def test_parallel_research_synthesize(self) -> None:
        lib = PatternLibrary()
        p = lib.parallel_research_synthesize("s1", "c1", ["r1", "r2", "r3"])
        assert len(p.steps) == 4  # coordinator + 3 researchers

    def test_parallel_coding_integrate(self) -> None:
        lib = PatternLibrary()
        p = lib.parallel_coding_integrate("s1", ["c1", "c2"], "i1")
        assert len(p.steps) == 3  # 2 coders + integrator

    def test_debate_and_vote(self) -> None:
        lib = PatternLibrary()
        p = lib.debate_and_vote("s1", ["p1", "p2"], ["v1", "v2"])
        assert len(p.steps) == 4

    def test_round_robin_review(self) -> None:
        lib = PatternLibrary()
        p = lib.round_robin_review("s1", ["r1", "r2"], rounds=2)
        assert len(p.steps) == 4

    def test_full_software_lifecycle(self) -> None:
        lib = PatternLibrary()
        p = lib.full_software_lifecycle("s1", "r1", "p1", "c1", "t1", "rv1", "d1")
        assert len(p.steps) == 6

    def test_pattern_names(self) -> None:
        lib = PatternLibrary()
        names = lib.pattern_names()
        assert "research_plan_code_review" in names
        assert "full_software_lifecycle" in names

    def test_build_by_name(self) -> None:
        lib = PatternLibrary()
        p = lib.build(
            "research_plan_code_review",
            "s1",
            {
                "researcher": "r1",
                "planner": "p1",
                "coder": "c1",
                "reviewer": "rv1",
            },
        )
        assert len(p.steps) == 4

    def test_build_unknown_pattern(self) -> None:
        lib = PatternLibrary()
        with pytest.raises(ValueError):
            lib.build("bogus", "s1", {})


# ===========================================================================
# CollaborationOrchestrator
# ===========================================================================


class TestOrchestrator:
    def test_construct(self) -> None:
        o = CollaborationOrchestrator()
        assert o is not None

    def test_create_session(self) -> None:
        o = CollaborationOrchestrator()
        s = o.create_session(name="Test", goal="Goal")
        assert s.name == "Test"

    def test_start_session(self) -> None:
        o = CollaborationOrchestrator()
        s = o.create_session()
        o.start_session(s.id)
        assert o.get_session(s.id).status == SessionStatus.ACTIVE.value

    def test_complete_session(self) -> None:
        o = CollaborationOrchestrator()
        s = o.create_session()
        o.complete_session(s.id)
        assert o.get_session(s.id).status == SessionStatus.COMPLETED.value

    def test_start_conversation(self) -> None:
        o = CollaborationOrchestrator()
        c = o.start_conversation("s1", topic="Planning")
        assert c.topic == "Planning"

    def test_speak(self) -> None:
        o = CollaborationOrchestrator()
        c = o.start_conversation("s1")
        t = o.speak(c.id, "a1", "Hello")
        assert t.content == "Hello"

    def test_delegate(self) -> None:
        o = CollaborationOrchestrator()
        d = o.delegate("s1", "a1", "a2", "Do work")
        assert d.from_agent_id == "a1"

    def test_negotiate(self) -> None:
        o = CollaborationOrchestrator()
        n = o.negotiate("s1", "Price", "a1")
        assert n.topic == "Price"

    def test_propose_vote(self) -> None:
        o = CollaborationOrchestrator()
        c = o.propose_vote("s1", "Deploy?", "Yes", "a1")
        assert c.topic == "Deploy?"

    def test_handoff(self) -> None:
        o = CollaborationOrchestrator()
        h = o.handoff("s1", "a1", "a2", "Continue work")
        assert h.from_agent_id == "a1"

    def test_report_conflict(self) -> None:
        o = CollaborationOrchestrator()
        c = o.report_conflict("s1", ("a1", "a2"), "Disagree")
        assert c.status == "open"

    def test_remember_recall(self) -> None:
        o = CollaborationOrchestrator()
        o.remember("s1", "key", "value")
        assert o.recall("s1", "key") == "value"

    def test_produce_artifact(self) -> None:
        o = CollaborationOrchestrator()
        a = o.produce_artifact("s1", "p1", name="output.txt")
        assert a.name == "output.txt"

    def test_run_pattern(self) -> None:
        o = CollaborationOrchestrator()
        p = o.run_pattern(
            "research_plan_code_review",
            "s1",
            {
                "researcher": "r1",
                "planner": "p1",
                "coder": "c1",
                "reviewer": "rv1",
            },
        )
        assert len(p.steps) == 4

    def test_execute_pipeline(self) -> None:
        o = CollaborationOrchestrator()
        p = o.run_pattern(
            "code_review_deploy",
            "s1",
            {"coder": "c1", "reviewer": "r1", "deployer": "d1"},
        )
        result = o.execute_pipeline(p.id)
        assert result.status == "completed"

    def test_status(self) -> None:
        o = CollaborationOrchestrator()
        o.create_session()
        o.start_conversation("s1")
        status = o.status()
        assert status["sessions"] == 1
        assert status["conversations"] == 1

    def test_engines_present(self) -> None:
        o = CollaborationOrchestrator()
        assert o.sessions is not None
        assert o.conversations is not None
        assert o.delegations is not None
        assert o.negotiations is not None
        assert o.consensus is not None
        assert o.handoffs is not None
        assert o.conflicts is not None
        assert o.coordination is not None
        assert o.memory is not None
        assert o.artifacts is not None
        assert o.patterns is not None


# ===========================================================================
# No circular imports / no subsystem imports
# ===========================================================================


class TestNoSubsystemImports:
    def test_collaboration_does_not_import_subsystems(self) -> None:
        """The collaboration package must not import any Atlas subsystem."""
        import os
        import re

        import atlas.collaboration

        root = os.path.dirname(atlas.collaboration.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|providers|mcp|memory|knowledge|workflows|tools|integration|agents|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline|workforce)\b"
        )
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path, encoding='utf-8') as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert (
            not offenders
        ), "atlas.collaboration imports other Atlas subsystems:\n" + "\n".join(
            offenders
        )

    def test_reload(self) -> None:
        import importlib

        import atlas.collaboration

        importlib.reload(atlas.collaboration)
        assert atlas.collaboration.__version__ == "1.0.0"


# ===========================================================================
# End-to-end integration
# ===========================================================================


class TestIntegration:
    def test_full_collaboration_scenario(self) -> None:
        """End-to-end: session → conversation → delegation → handoff → artifact."""
        o = CollaborationOrchestrator()
        # Create session
        session = o.create_session(
            name="Build feature",
            goal="Implement user auth",
            coordinator_id="c1",
            participant_ids=("c1", "r1", "p1", "cod1"),
        )
        o.start_session(session.id)

        # Conversation
        conv = o.start_conversation(
            session.id, topic="Planning", participant_ids=("c1", "r1")
        )
        o.speak(conv.id, "c1", "Let's plan the auth feature")
        o.speak(conv.id, "r1", "I'll research best practices")

        # Delegation
        d = o.delegate(session.id, "c1", "r1", "Research auth patterns")
        o.delegations.accept(d.id)

        # Handoff
        h = o.handoff(session.id, "r1", "p1", "Research complete, plan it")
        o.handoffs.accept(h.id)

        # Artifact
        a = o.produce_artifact(
            session.id, "r1", name="research.md", content="Auth patterns..."
        )

        # Shared memory
        o.remember(session.id, "decision", "Use JWT", author_id="c1")

        # Complete
        o.complete_session(session.id)

        assert o.get_session(session.id).status == SessionStatus.COMPLETED.value
        assert o.status()["conversations"] == 1
        assert o.status()["delegations"] == 1
        assert o.status()["handoffs"] == 1
        assert o.status()["artifacts"] == 1

    def test_pipeline_execution_scenario(self) -> None:
        """Build and execute a research→plan→code→review pipeline."""
        calls: list[str] = []

        def fake_think(**kwargs: object) -> str:
            agent_id = str(kwargs.get("agent_id", ""))
            calls.append(agent_id)
            return f"output from {agent_id}"

        o = CollaborationOrchestrator(think_fn=fake_think)
        session = o.create_session(name="Pipeline test", goal="Build X")
        o.start_session(session.id)

        p = o.run_pattern(
            "research_plan_code_review",
            session.id,
            {
                "researcher": "r1",
                "planner": "p1",
                "coder": "cod1",
                "reviewer": "rv1",
            },
        )
        result = o.execute_pipeline(p.id)
        assert result.status == "completed"
        assert len(calls) == 4

    def test_consensus_scenario(self) -> None:
        """Propose a vote, agents vote, consensus is reached."""
        o = CollaborationOrchestrator()
        session = o.create_session(name="Vote", goal="Decide")
        o.start_session(session.id)

        c = o.propose_vote(
            session.id,
            topic="Use Python?",
            proposal="Yes, use Python",
            proposer_id="a1",
            eligible_voter_ids=("a1", "a2", "a3"),
        )
        o.consensus.vote(c.id, "a1", kind=VoteKind.YES.value)
        o.consensus.vote(c.id, "a2", kind=VoteKind.YES.value)
        o.consensus.vote(c.id, "a3", kind=VoteKind.NO.value)
        o.consensus.close(c.id)
        assert o.consensus.get(c.id).status == ConsensusStatus.REACHED.value

    def test_negotiation_scenario(self) -> None:
        """Two agents negotiate, one accepts the other's offer."""
        o = CollaborationOrchestrator()
        session = o.create_session(name="Negotiate", goal="Agree on price")
        o.start_session(session.id)

        n = o.negotiate(session.id, "Price", "a1", participant_ids=("a1", "a2"))
        o.negotiations.propose(n.id, "a1", terms="100 dollars")
        offer2 = o.negotiations.counter(n.id, "a2", terms="80 dollars")
        o.negotiations.accept(n.id, offer2.id)
        assert o.negotiations.get(n.id).status == NegotiationStatus.ACCEPTED.value

    def test_conflict_resolution_scenario(self) -> None:
        """Two agents conflict, coordinator mediates."""
        o = CollaborationOrchestrator()
        session = o.create_session(name="Conflict", goal="Resolve")
        o.start_session(session.id)

        c = o.report_conflict(
            session.id,
            ("a1", "a2"),
            "Both want the same resource",
            kind=ConflictKind.RESOURCE.value,
        )
        o.conflicts.resolve(
            c.id, resolution=ConflictResolution.MEDIATED.value, notes="Split time"
        )
        assert o.conflicts.get(c.id).status == "resolved"
