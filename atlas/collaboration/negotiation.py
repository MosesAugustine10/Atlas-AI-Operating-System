"""Negotiation engine — propose, counter, accept, reject.

The :class:`NegotiationEngine` manages :class:`Negotiation` instances.
Agents make :class:`Offer` instances; the initiator can accept an
offer (ending the negotiation) or counter with a new offer.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    Negotiation,
    NegotiationStatus,
    Offer,
    _new_id,
    _utcnow,
)


class NegotiationError(RuntimeError):
    """Raised when a negotiation operation fails."""


class NegotiationEngine:
    """Manages negotiations between agents."""

    def __init__(self) -> None:
        self._negotiations: dict[str, Negotiation] = {}

    def start(
        self,
        session_id: str,
        topic: str = "",
        initiator_id: str = "",
        participant_ids: tuple[str, ...] = (),
    ) -> Negotiation:
        """Start a new negotiation."""
        negotiation = Negotiation(
            id=_new_id("negotiation"),
            session_id=session_id,
            topic=topic,
            initiator_id=initiator_id,
            participant_ids=participant_ids,
        )
        self._negotiations[negotiation.id] = negotiation
        return negotiation

    def propose(
        self,
        negotiation_id: str,
        agent_id: str,
        terms: str = "",
    ) -> Offer:
        """Make an offer in a negotiation."""
        n = self._require(negotiation_id)
        if n.status != NegotiationStatus.OPEN.value:
            raise NegotiationError(
                f"negotiation {negotiation_id} is {n.status}, cannot propose"
            )
        offer = Offer(
            id=_new_id("offer"),
            negotiation_id=negotiation_id,
            agent_id=agent_id,
            terms=terms,
        )
        offers = tuple(list(n.offers) + [offer])
        self._update(negotiation_id, offers=offers)
        return offer

    def counter(
        self,
        negotiation_id: str,
        agent_id: str,
        terms: str = "",
    ) -> Offer:
        """Make a counter-offer (sets status to COUNTERED)."""
        n = self._require(negotiation_id)
        if n.status not in (
            NegotiationStatus.OPEN.value,
            NegotiationStatus.COUNTERED.value,
        ):
            raise NegotiationError(
                f"negotiation {negotiation_id} is {n.status}, cannot counter"
            )
        offer = Offer(
            id=_new_id("offer"),
            negotiation_id=negotiation_id,
            agent_id=agent_id,
            terms=terms,
        )
        offers = tuple(list(n.offers) + [offer])
        self._update(
            negotiation_id,
            offers=offers,
            status=NegotiationStatus.COUNTERED.value,
        )
        return offer

    def accept(
        self,
        negotiation_id: str,
        offer_id: str,
    ) -> Negotiation:
        """Accept an offer — ends the negotiation."""
        n = self._require(negotiation_id)
        offer = next((o for o in n.offers if o.id == offer_id), None)
        if offer is None:
            raise NegotiationError(
                f"offer {offer_id} not in negotiation {negotiation_id}"
            )
        if offer.withdrawn:
            raise NegotiationError(f"offer {offer_id} was withdrawn")
        return self._update(
            negotiation_id,
            status=NegotiationStatus.ACCEPTED.value,
            accepted_offer_id=offer_id,
            resolved_at=_utcnow(),
        )

    def reject(self, negotiation_id: str) -> Negotiation:
        """Reject the negotiation."""
        n = self._require(negotiation_id)
        return self._update(
            negotiation_id,
            status=NegotiationStatus.REJECTED.value,
            resolved_at=_utcnow(),
        )

    def withdraw_offer(self, negotiation_id: str, offer_id: str) -> Offer:
        """Withdraw an offer."""
        n = self._require(negotiation_id)
        new_offers: list[Offer] = []
        withdrawn: Offer | None = None
        for o in n.offers:
            if o.id == offer_id:
                withdrawn = dataclasses.replace(o, withdrawn=True)
                new_offers.append(withdrawn)
            else:
                new_offers.append(o)
        if withdrawn is None:
            raise NegotiationError(
                f"offer {offer_id} not in negotiation {negotiation_id}"
            )
        self._update(negotiation_id, offers=tuple(new_offers))
        return withdrawn

    def withdraw(self, negotiation_id: str) -> Negotiation:
        """Withdraw the entire negotiation."""
        n = self._require(negotiation_id)
        return self._update(
            negotiation_id,
            status=NegotiationStatus.WITHDRAWN.value,
            resolved_at=_utcnow(),
        )

    def expire(self, negotiation_id: str) -> Negotiation:
        """Mark a negotiation as expired."""
        n = self._require(negotiation_id)
        return self._update(
            negotiation_id,
            status=NegotiationStatus.EXPIRED.value,
            resolved_at=_utcnow(),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, negotiation_id: str) -> Negotiation | None:
        """Return the negotiation with ``negotiation_id`` or ``None``."""
        return self._negotiations.get(negotiation_id)

    def list_negotiations(
        self,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[Negotiation]:
        """List negotiations with optional filters."""
        negotiations = list(self._negotiations.values())
        if session_id is not None:
            negotiations = [n for n in negotiations if n.session_id == session_id]
        if status is not None:
            negotiations = [n for n in negotiations if n.status == status]
        return negotiations

    def offers(self, negotiation_id: str) -> list[Offer]:
        """Return all offers in a negotiation."""
        n = self._require(negotiation_id)
        return list(n.offers)

    def active_offers(self, negotiation_id: str) -> list[Offer]:
        """Return all non-withdrawn offers."""
        return [o for o in self.offers(negotiation_id) if not o.withdrawn]

    def accepted_offer(self, negotiation_id: str) -> Offer | None:
        """Return the accepted offer, or ``None``."""
        n = self._require(negotiation_id)
        if not n.accepted_offer_id:
            return None
        return next((o for o in n.offers if o.id == n.accepted_offer_id), None)

    def open_negotiations(self) -> list[Negotiation]:
        """Return all open negotiations."""
        return self.list_negotiations(status=NegotiationStatus.OPEN.value)

    def count(self) -> int:
        """Return the total number of negotiations."""
        return len(self._negotiations)

    def count_by_status(self) -> dict[str, int]:
        """Return a dict of negotiation counts by status."""
        counts: dict[str, int] = {}
        for n in self._negotiations.values():
            counts[n.status] = counts.get(n.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, negotiation_id: str) -> Negotiation:
        n = self._negotiations.get(negotiation_id)
        if n is None:
            raise NegotiationError(f"negotiation {negotiation_id} not found")
        return n

    def _update(self, negotiation_id: str, **changes: Any) -> Negotiation:
        n = self._negotiations[negotiation_id]
        updated = dataclasses.replace(n, **changes)
        self._negotiations[negotiation_id] = updated
        return updated


__all__ = ["NegotiationEngine", "NegotiationError"]
