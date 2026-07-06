"""Approval engine — multi-stage approvals with timeout and escalation."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

from atlas.enterprise.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResult,
    ApprovalType,
    Escalation,
    _new_id,
    _utcnow,
)


class ApprovalEngine:
    """Manages approval requests with timeout, escalation, and multi-stage support."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._results: dict[str, ApprovalResult] = {}
        self._escalations: dict[str, Escalation] = {}

    def request(
        self,
        title: str,
        description: str = "",
        type: str = ApprovalType.MANAGER.value,
        requester: str = "",
        approver: str = "",
        timeout_minutes: int = 1440,
    ) -> ApprovalRequest:
        r = ApprovalRequest(
            id=_new_id("appr"),
            title=title,
            description=description,
            type=type,
            requester=requester,
            approver=approver,
            timeout_minutes=timeout_minutes,
        )
        self._requests[r.id] = r
        return r

    def get(self, rid: str) -> ApprovalRequest | None:
        return self._requests.get(rid)

    def list(
        self, decision: str | None = None, type: str | None = None
    ) -> list[ApprovalRequest]:
        rs = list(self._requests.values())
        if decision is not None:
            rs = [r for r in rs if r.decision == decision]
        if type is not None:
            rs = [r for r in rs if r.type == type]
        return sorted(rs, key=lambda r: r.created_at, reverse=True)

    def approve(self, rid: str, approver: str = "", reason: str = "") -> ApprovalResult:
        r = self._require(rid)
        updated = dataclasses.replace(
            r,
            decision=ApprovalDecision.APPROVED.value,
            approver=approver,
            decided_at=_utcnow(),
            reason=reason,
        )
        self._requests[rid] = updated
        result = ApprovalResult(
            id=_new_id("res"),
            request_id=rid,
            decision=ApprovalDecision.APPROVED.value,
            approver=approver,
            reason=reason,
        )
        self._results[result.id] = result
        return result

    def reject(self, rid: str, approver: str = "", reason: str = "") -> ApprovalResult:
        r = self._require(rid)
        updated = dataclasses.replace(
            r,
            decision=ApprovalDecision.REJECTED.value,
            approver=approver,
            decided_at=_utcnow(),
            reason=reason,
        )
        self._requests[rid] = updated
        result = ApprovalResult(
            id=_new_id("res"),
            request_id=rid,
            decision=ApprovalDecision.REJECTED.value,
            approver=approver,
            reason=reason,
        )
        self._results[result.id] = result
        return result

    def escalate(
        self,
        rid: str,
        from_level: str = "manager",
        to_level: str = "ceo",
        reason: str = "",
    ) -> Escalation:
        r = self._require(rid)
        updated = dataclasses.replace(r, decision=ApprovalDecision.ESCALATED.value)
        self._requests[rid] = updated
        esc = Escalation(
            id=_new_id("esc"),
            request_id=rid,
            from_level=from_level,
            to_level=to_level,
            reason=reason,
        )
        self._escalations[esc.id] = esc
        return esc

    def check_timeouts(self) -> list[str]:
        """Return IDs of requests that have timed out and mark them expired."""
        now = _utcnow()
        expired: list[str] = []
        for rid, r in self._requests.items():
            if r.decision == ApprovalDecision.PENDING.value:
                elapsed = now - r.created_at
                if elapsed > timedelta(minutes=r.timeout_minutes):
                    updated = dataclasses.replace(
                        r, decision=ApprovalDecision.EXPIRED.value, decided_at=now
                    )
                    self._requests[rid] = updated
                    expired.append(rid)
        return expired

    def auto_approve(self, rid: str) -> ApprovalResult | None:
        """Automatically approve a request (for low-risk, policy-allowed requests)."""
        r = self._requests.get(rid)
        if r is None or r.decision != ApprovalDecision.PENDING.value:
            return None
        return self.approve(rid, approver="system", reason="Automatic approval")

    def pending(self) -> list[ApprovalRequest]:
        return self.list(decision=ApprovalDecision.PENDING.value)

    def count(self) -> int:
        return len(self._requests)

    def count_by_decision(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._requests.values():
            counts[r.decision] = counts.get(r.decision, 0) + 1
        return counts

    def escalation_count(self) -> int:
        return len(self._escalations)

    def _require(self, rid: str) -> ApprovalRequest:
        r = self._requests.get(rid)
        if r is None:
            raise KeyError(f"approval {rid} not found")
        return r


__all__ = ["ApprovalEngine"]
