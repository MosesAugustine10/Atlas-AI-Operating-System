"""Execution reviewer — evaluates execution outcomes.

The :class:`ExecutionReviewer` is the fourth stage of the execution
pipeline. After the executor has run every task, the reviewer inspects
the results and produces an :class:`ExecutionReview` containing:

* Overall :class:`ExecutionStatus` (completed / failed / partial).
* Per-task warnings (e.g. optional task skipped, retry occurred).
* Missing outputs (tasks that produced no output).
* Retry recommendation (``"none"``, ``"retry_failed"``,
  ``"retry_all"``).
* Quality score (0.0 - 1.0).
* Free-form notes.

The current implementation is deterministic: it scores executions
based on the ratio of completed tasks and flags obvious problems
(missing outputs, retries, optional skips). Future LLM-backed review
can be plugged in by subclassing :class:`BaseReviewer` and overriding
:meth:`review`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from atlas.core.logger import get_logger
from atlas.execution.models import (
    ExecutionContext,
    ExecutionStatus,
)

# ---------------------------------------------------------------------------
# Review result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskReview:
    """The reviewer's evaluation of a single task.

    Attributes:
        task_id: The task this review applies to.
        status: The :class:`ExecutionStatus` of the task.
        warnings: List of human-readable warnings.
        missing_output: ``True`` if the task completed but produced no
            output.
        retry_recommended: ``True`` if the reviewer recommends retrying
            this task.
        quality_score: 0.0 - 1.0 quality score for this task.
        notes: Free-form notes.
    """

    task_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    warnings: list[str] = field(default_factory=list)
    missing_output: bool = False
    retry_recommended: bool = False
    quality_score: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class ExecutionReview:
    """The reviewer's evaluation of an entire execution.

    Attributes:
        execution_id: The execution this review describes.
        overall_status: The roll-up :class:`ExecutionStatus`.
        task_reviews: Mapping of task ID -> :class:`TaskReview`.
        warnings: Aggregated list of human-readable warnings.
        missing_outputs: List of task IDs that produced no output.
        retry_recommendation: ``"none"``, ``"retry_failed"``, or
            ``"retry_all"``.
        quality_score: 0.0 - 1.0 overall quality score.
        notes: Free-form notes.
    """

    execution_id: str
    overall_status: ExecutionStatus = ExecutionStatus.PENDING
    task_reviews: dict[str, TaskReview] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    missing_outputs: list[str] = field(default_factory=list)
    retry_recommendation: str = "none"
    quality_score: float = 0.0
    notes: str = ""


# ---------------------------------------------------------------------------
# Base and concrete reviewer
# ---------------------------------------------------------------------------


class BaseReviewer(ABC):
    """Abstract contract for execution reviewers."""

    @abstractmethod
    def review(self, context: ExecutionContext) -> ExecutionReview:
        """Evaluate ``context`` and return an :class:`ExecutionReview`."""


class ExecutionReviewer(BaseReviewer):
    """Deterministic placeholder reviewer.

    The current implementation scores executions based on the ratio of
    completed tasks and flags obvious problems. Future LLM-backed
    review can be plugged in by subclassing and overriding :meth:`review`.
    """

    def __init__(self) -> None:
        self.logger = get_logger("execution.reviewer")

    def review(self, context: ExecutionContext) -> ExecutionReview:
        """Evaluate ``context`` and return an :class:`ExecutionReview`."""
        if context.plan is None:
            return ExecutionReview(
                execution_id=context.id,
                overall_status=ExecutionStatus.FAILED,
                warnings=["no plan"],
                quality_score=0.0,
                notes="context had no plan",
            )

        task_reviews: dict[str, TaskReview] = {}
        warnings: list[str] = []
        missing_outputs: list[str] = []
        completed = 0
        failed = 0
        skipped = 0
        retried = 0

        for task in context.plan.tasks:
            result = context.results.get(task.id)
            if result is None:
                task_reviews[task.id] = TaskReview(
                    task_id=task.id,
                    status=ExecutionStatus.PENDING,
                    warnings=["not_executed"],
                    retry_recommended=True,
                    quality_score=0.0,
                    notes="task was not executed",
                )
                warnings.append(f"task {task.id} was not executed")
                failed += 1
                continue

            task_warnings: list[str] = []
            missing = False
            retry = False
            score = 1.0 if result.success else 0.0

            if result.status is ExecutionStatus.COMPLETED:
                completed += 1
                if result.output is None:
                    missing = True
                    missing_outputs.append(task.id)
                    task_warnings.append("completed with no output")
                    score = 0.5
                if result.attempts > 1:
                    retried += 1
                    task_warnings.append(f"required {result.attempts} attempts")
                    score = max(0.0, score - 0.1 * (result.attempts - 1))
            elif result.status is ExecutionStatus.FAILED:
                failed += 1
                retry = True
                task_warnings.append(f"failed: {result.error or 'unknown'}")
            elif result.status is ExecutionStatus.SKIPPED:
                skipped += 1
                task_warnings.append("skipped (optional, dependencies failed)")
            elif result.status is ExecutionStatus.CANCELLED:
                task_warnings.append("cancelled")

            task_reviews[task.id] = TaskReview(
                task_id=task.id,
                status=result.status,
                warnings=task_warnings,
                missing_output=missing,
                retry_recommended=retry,
                quality_score=max(0.0, min(1.0, score)),
                notes=f"attempts={result.attempts}",
            )
            warnings.extend(f"task {task.id}: {w}" for w in task_warnings)

        total = len(context.plan.tasks)
        overall = self._overall_status(completed, failed, skipped, total)
        recommendation = self._retry_recommendation(failed, completed, retried)
        quality = self._quality_score(
            completed, failed, skipped, total, missing_outputs
        )

        review = ExecutionReview(
            execution_id=context.id,
            overall_status=overall,
            task_reviews=task_reviews,
            warnings=warnings,
            missing_outputs=missing_outputs,
            retry_recommendation=recommendation,
            quality_score=quality,
            notes=(
                f"completed={completed} failed={failed} skipped={skipped} "
                f"total={total} retried={retried}"
            ),
        )
        self.logger.info(
            "Reviewed execution %s: status=%s quality=%.2f recommendation=%s",
            context.id,
            overall.value,
            quality,
            recommendation,
        )
        return review

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _overall_status(
        completed: int, failed: int, skipped: int, total: int
    ) -> ExecutionStatus:
        """Roll up per-task statuses into an overall status."""
        if total == 0:
            return ExecutionStatus.COMPLETED
        if completed == total:
            return ExecutionStatus.COMPLETED
        # If every task is either completed or skipped (no failures), the
        # execution is considered completed — skipped tasks are optional
        # tasks whose dependencies failed, which is expected behaviour.
        if failed == 0 and completed + skipped == total:
            return ExecutionStatus.COMPLETED
        if completed == 0 and failed > 0:
            return ExecutionStatus.FAILED
        if completed + skipped + failed == total and failed > 0:
            # Some completed, some failed — partial.
            return ExecutionStatus.FAILED
        if completed > 0:
            return ExecutionStatus.COMPLETED
        return ExecutionStatus.FAILED

    @staticmethod
    def _retry_recommendation(failed: int, completed: int, retried: int) -> str:
        """Decide whether to recommend a retry."""
        if failed == 0:
            return "none"
        if retried > 0 and completed == 0:
            return "retry_all"
        if failed > 0:
            return "retry_failed"
        return "none"

    @staticmethod
    def _quality_score(
        completed: int,
        failed: int,
        skipped: int,
        total: int,
        missing_outputs: list[str],
    ) -> float:
        """Compute a 0.0 - 1.0 quality score.

        The score is the ratio of completed tasks to total tasks, with
        a penalty for each missing output.
        """
        if total == 0:
            return 1.0
        base = completed / total
        penalty = 0.05 * len(missing_outputs)
        return max(0.0, min(1.0, base - penalty))


__all__ = [
    "BaseReviewer",
    "ExecutionReview",
    "ExecutionReviewer",
    "TaskReview",
]
