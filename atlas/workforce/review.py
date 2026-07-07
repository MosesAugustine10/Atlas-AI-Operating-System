"""Review engine — quality review, approvals, and rejections.

The :class:`ReviewEngine` manages the review lifecycle: workers
submit their work for review, reviewers record verdicts (approved,
rejected, changes requested), and tasks transition through the
review states.

The engine also manages :class:`~atlas.workforce.models.Approval`
requests for gated decisions (e.g. deployment approval, design
sign-off).
"""

from __future__ import annotations

import dataclasses

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Approval,
    Review,
    ReviewVerdict,
    Task,
    TaskStatus,
    _new_id,
    _utcnow,
)


class ReviewEngine:
    """Manages quality reviews and approvals."""

    def __init__(self) -> None:
        self._reviews: dict[str, Review] = {}
        self._approvals: dict[str, Approval] = {}
        self.logger = get_logger("workforce.review")

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def submit_review(
        self,
        task_id: str,
        reviewer_id: str,
        verdict: str = ReviewVerdict.APPROVED.value,
        quality_score: float = 0.8,
        notes: str = "",
        rework_required: bool = False,
    ) -> Review:
        """Submit a quality review for ``task_id``."""
        review = Review(
            id=_new_id("review"),
            task_id=task_id,
            reviewer_id=reviewer_id,
            verdict=verdict,
            quality_score=quality_score,
            notes=notes,
            rework_required=rework_required,
        )
        self._reviews[review.id] = review
        self.logger.info(
            "Review %s for task %s: %s (quality=%.2f)",
            review.id,
            task_id,
            verdict,
            quality_score,
        )
        return review

    def get_review(self, review_id: str) -> Review | None:
        """Return the review with ``review_id`` or ``None``."""
        return self._reviews.get(review_id)

    def reviews_for_task(self, task_id: str) -> list[Review]:
        """Return all reviews for ``task_id`` (chronological)."""
        reviews = [r for r in self._reviews.values() if r.task_id == task_id]
        reviews.sort(key=lambda r: r.timestamp)
        return reviews

    def reviews_by(self, reviewer_id: str) -> list[Review]:
        """Return all reviews by ``reviewer_id``."""
        return [r for r in self._reviews.values() if r.reviewer_id == reviewer_id]

    def latest_review(self, task_id: str) -> Review | None:
        """Return the most recent review for ``task_id`` or ``None``."""
        reviews = self.reviews_for_task(task_id)
        return reviews[-1] if reviews else None

    def is_approved(self, task_id: str) -> bool:
        """Return ``True`` if the latest review for ``task_id`` was approved."""
        latest = self.latest_review(task_id)
        return latest is not None and latest.verdict == ReviewVerdict.APPROVED.value

    def is_rejected(self, task_id: str) -> bool:
        """Return ``True`` if the latest review for ``task_id`` was rejected."""
        latest = self.latest_review(task_id)
        return latest is not None and latest.verdict == ReviewVerdict.REJECTED.value

    def needs_rework(self, task_id: str) -> bool:
        """Return ``True`` if the latest review requested changes."""
        latest = self.latest_review(task_id)
        return latest is not None and (
            latest.verdict == ReviewVerdict.CHANGES_REQUESTED.value
            or latest.rework_required
        )

    def average_quality(self, task_id: str | None = None) -> float:
        """Return the average quality score across reviews.

        When ``task_id`` is given, only reviews for that task are counted.
        """
        reviews = (
            self.reviews_for_task(task_id) if task_id else list(self._reviews.values())
        )
        if not reviews:
            return 0.0
        return sum(r.quality_score for r in reviews) / len(reviews)

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def request_approval(
        self,
        requester_id: str,
        task_id: str = "",
        kind: str = "general",
        description: str = "",
    ) -> Approval:
        """Submit a request for approval."""
        approval = Approval(
            id=_new_id("approval"),
            requester_id=requester_id,
            task_id=task_id,
            kind=kind,
            description=description,
        )
        self._approvals[approval.id] = approval
        self.logger.info("Approval %s requested by %s", approval.id, requester_id)
        return approval

    def grant_approval(
        self,
        approval_id: str,
        approver_id: str,
        notes: str = "",
    ) -> Approval:
        """Grant an approval request."""
        approval = self._require_approval(approval_id)
        updated = dataclasses.replace(
            approval,
            approver_id=approver_id,
            granted=True,
            decided_at=_utcnow(),
            notes=notes,
        )
        self._approvals[approval_id] = updated
        return updated

    def deny_approval(
        self,
        approval_id: str,
        approver_id: str,
        notes: str = "",
    ) -> Approval:
        """Deny an approval request."""
        approval = self._require_approval(approval_id)
        updated = dataclasses.replace(
            approval,
            approver_id=approver_id,
            granted=False,
            decided_at=_utcnow(),
            notes=notes,
        )
        self._approvals[approval_id] = updated
        return updated

    def get_approval(self, approval_id: str) -> Approval | None:
        """Return the approval with ``approval_id`` or ``None``."""
        return self._approvals.get(approval_id)

    def pending_approvals(self) -> list[Approval]:
        """Return all approvals that have not been decided."""
        return [a for a in self._approvals.values() if a.granted is None]

    def decided_approvals(self) -> list[Approval]:
        """Return all approvals that have been decided."""
        return [a for a in self._approvals.values() if a.granted is not None]

    def approvals_for_task(self, task_id: str) -> list[Approval]:
        """Return all approvals for ``task_id``."""
        return [a for a in self._approvals.values() if a.task_id == task_id]

    def approval_rate(self) -> float:
        """Return the fraction of decided approvals that were granted."""
        decided = self.decided_approvals()
        if not decided:
            return 0.0
        granted = sum(1 for a in decided if a.granted)
        return granted / len(decided)

    # ------------------------------------------------------------------
    # Task status transitions
    # ------------------------------------------------------------------

    def apply_verdict(self, task: Task, review: Review) -> Task:
        """Apply a review verdict to ``task`` and return the updated task."""
        if review.verdict == ReviewVerdict.APPROVED.value:
            return dataclasses.replace(
                task,
                status=TaskStatus.APPROVED.value,
                quality_score=review.quality_score,
                review_notes=review.notes,
                completed_at=_utcnow(),
            )
        if review.verdict == ReviewVerdict.REJECTED.value:
            return dataclasses.replace(
                task,
                status=TaskStatus.REJECTED.value,
                quality_score=review.quality_score,
                review_notes=review.notes,
            )
        if review.verdict == ReviewVerdict.CHANGES_REQUESTED.value:
            return dataclasses.replace(
                task,
                status=TaskStatus.REJECTED.value,
                quality_score=review.quality_score,
                review_notes=review.notes,
            )
        # DEFERRED — no status change
        return task

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def review_count(self) -> int:
        """Return the total number of reviews."""
        return len(self._reviews)

    def approval_count(self) -> int:
        """Return the total number of approval requests."""
        return len(self._approvals)

    def count_by_verdict(self) -> dict[str, int]:
        """Return a dict of review counts by verdict."""
        counts: dict[str, int] = {}
        for r in self._reviews.values():
            counts[r.verdict] = counts.get(r.verdict, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_approval(self, approval_id: str) -> Approval:
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise KeyError(f"approval {approval_id} not found")
        return approval


__all__ = ["ReviewEngine"]
