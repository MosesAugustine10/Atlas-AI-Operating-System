"""Consensus engine — voting and consensus-building.

The :class:`ConsensusEngine` manages :class:`Consensus` rounds. An
agent proposes a topic, eligible agents cast :class:`Vote` instances,
and the engine tallies the result against a required majority.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    Consensus,
    ConsensusStatus,
    Vote,
    VoteKind,
    _new_id,
    _utcnow,
)


class ConsensusError(RuntimeError):
    """Raised when a consensus operation fails."""


class ConsensusEngine:
    """Manages voting and consensus rounds."""

    def __init__(self) -> None:
        self._rounds: dict[str, Consensus] = {}

    def propose(
        self,
        session_id: str,
        topic: str = "",
        proposal: str = "",
        proposer_id: str = "",
        eligible_voter_ids: tuple[str, ...] = (),
        required_majority: float = 0.5,
    ) -> Consensus:
        """Start a new consensus round."""
        if not 0.0 < required_majority <= 1.0:
            raise ConsensusError("required_majority must be in (0.0, 1.0]")
        consensus = Consensus(
            id=_new_id("consensus"),
            session_id=session_id,
            topic=topic,
            proposal=proposal,
            proposer_id=proposer_id,
            eligible_voter_ids=eligible_voter_ids,
            required_majority=required_majority,
        )
        self._rounds[consensus.id] = consensus
        return consensus

    def vote(
        self,
        consensus_id: str,
        voter_id: str,
        kind: str = VoteKind.YES.value,
        reason: str = "",
    ) -> Vote:
        """Cast a vote in a consensus round."""
        c = self._require(consensus_id)
        if c.status != ConsensusStatus.OPEN.value:
            raise ConsensusError(f"consensus {consensus_id} is {c.status}, cannot vote")
        if c.eligible_voter_ids and voter_id not in c.eligible_voter_ids:
            raise ConsensusError(
                f"voter {voter_id} is not eligible for consensus {consensus_id}"
            )
        # Check if voter already voted — replace existing vote
        votes = [v for v in c.votes if v.voter_id != voter_id]
        vote = Vote(
            id=_new_id("vote"),
            consensus_id=consensus_id,
            voter_id=voter_id,
            kind=kind,
            reason=reason,
        )
        votes.append(vote)
        self._update(consensus_id, votes=tuple(votes))
        return vote

    def close(self, consensus_id: str) -> Consensus:
        """Close a consensus round and compute the result."""
        c = self._require(consensus_id)
        if c.status != ConsensusStatus.OPEN.value:
            return c
        result = self._tally(c)
        return self._update(
            consensus_id,
            status=result,
            closed_at=_utcnow(),
        )

    def expire(self, consensus_id: str) -> Consensus:
        """Mark a consensus round as expired (no quorum)."""
        c = self._require(consensus_id)
        return self._update(
            consensus_id,
            status=ConsensusStatus.EXPIRED.value,
            closed_at=_utcnow(),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, consensus_id: str) -> Consensus | None:
        """Return the consensus round with ``consensus_id`` or ``None``."""
        return self._rounds.get(consensus_id)

    def list_rounds(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[Consensus]:
        """List consensus rounds with optional filters."""
        rounds = list(self._rounds.values())
        if session_id is not None:
            rounds = [c for c in rounds if c.session_id == session_id]
        if status is not None:
            rounds = [c for c in rounds if c.status == status]
        return rounds

    def votes_by(
        self,
        consensus_id: str,
        voter_id: str,
    ) -> list[Vote]:
        """Return votes cast by ``voter_id`` in a consensus round."""
        c = self._require(consensus_id)
        return [v for v in c.votes if v.voter_id == voter_id]

    def vote_count(self, consensus_id: str) -> int:
        """Return the number of votes cast in a consensus round."""
        c = self._rounds.get(consensus_id)
        return len(c.votes) if c else 0

    def tally(self, consensus_id: str) -> dict[str, int]:
        """Return a ``{vote_kind: count}`` dict for a consensus round."""
        c = self._require(consensus_id)
        counts: dict[str, int] = {}
        for v in c.votes:
            counts[v.kind] = counts.get(v.kind, 0) + 1
        return counts

    def open_rounds(self) -> list[Consensus]:
        """Return all open consensus rounds."""
        return self.list_rounds(status=ConsensusStatus.OPEN.value)

    def count(self) -> int:
        """Return the total number of consensus rounds."""
        return len(self._rounds)

    def count_by_status(self) -> dict[str, int]:
        """Return a dict of consensus counts by status."""
        counts: dict[str, int] = {}
        for c in self._rounds.values():
            counts[c.status] = counts.get(c.status, 0) + 1
        return counts

    def consensus_rate(self) -> float:
        """Return the fraction of closed rounds that reached consensus."""
        closed = [
            c
            for c in self._rounds.values()
            if c.status
            in (
                ConsensusStatus.REACHED.value,
                ConsensusStatus.REJECTED.value,
                ConsensusStatus.TIED.value,
            )
        ]
        if not closed:
            return 0.0
        reached = sum(1 for c in closed if c.status == ConsensusStatus.REACHED.value)
        return reached / len(closed)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _tally(c: Consensus) -> str:
        """Compute the result of a consensus round."""
        if not c.votes:
            return ConsensusStatus.EXPIRED.value
        yes = sum(1 for v in c.votes if v.kind == VoteKind.YES.value)
        no = sum(1 for v in c.votes if v.kind == VoteKind.NO.value)
        veto = sum(1 for v in c.votes if v.kind == VoteKind.VETO.value)
        if veto > 0:
            return ConsensusStatus.REJECTED.value
        if yes > no:
            # Check majority
            total = len(c.votes)
            if total == 0:
                return ConsensusStatus.EXPIRED.value
            if yes / total >= c.required_majority:
                return ConsensusStatus.REACHED.value
            return ConsensusStatus.REJECTED.value
        if no > yes:
            return ConsensusStatus.REJECTED.value
        return ConsensusStatus.TIED.value

    def _require(self, consensus_id: str) -> Consensus:
        c = self._rounds.get(consensus_id)
        if c is None:
            raise ConsensusError(f"consensus {consensus_id} not found")
        return c

    def _update(self, consensus_id: str, **changes: Any) -> Consensus:
        c = self._rounds[consensus_id]
        updated = dataclasses.replace(c, **changes)
        self._rounds[consensus_id] = updated
        return updated


__all__ = ["ConsensusEngine", "ConsensusError"]
