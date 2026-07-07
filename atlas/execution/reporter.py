"""Execution reporter — generates professional execution reports.

The :class:`ExecutionReporter` is the fifth and final stage of the
execution pipeline. It receives the :class:`ExecutionContext` (with
every task's result) and the :class:`ExecutionReview` (from the
reviewer) and assembles a single :class:`ExecutionReport` that
captures everything an operator needs to understand what happened:

* execution id, goal, status, duration
* per-task results
* aggregate metrics (task counts, attempts, tokens, cost)
* providers / agents / tools / workflows used
* memory usage, knowledge hits
* files created / modified, git commits, tool calls, MCP calls
* warnings, errors
* token usage, estimated cost
* quality score, retry recommendation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.execution.models import (
    ExecutionContext,
    ExecutionMetrics,
    ExecutionReport,
    ExecutionResult,
    ExecutionStatus,
    ExecutionSummary,
)
from atlas.execution.reviewer import ExecutionReview


class BaseReporter(ABC):
    """Abstract contract for execution reporters."""

    @abstractmethod
    def report(
        self,
        context: ExecutionContext,
        review: ExecutionReview,
        executor: Any = None,
    ) -> ExecutionReport:
        """Assemble an :class:`ExecutionReport` from ``context`` and ``review``."""


class ExecutionReporter(BaseReporter):
    """Assembles professional :class:`ExecutionReport` instances.

    Parameters:
        memory: Optional :class:`MemoryEngine` (or compatible). When
            present, the reporter pulls memory statistics for the report.
        knowledge: Optional :class:`KnowledgeEngine` (or compatible).
            When present, the reporter pulls knowledge statistics.
    """

    def __init__(
        self,
        memory: Any = None,
        knowledge: Any = None,
    ) -> None:
        self.memory = memory
        self.knowledge = knowledge
        self.logger = get_logger("execution.reporter")

    def report(
        self,
        context: ExecutionContext,
        review: ExecutionReview,
        executor: Any = None,
    ) -> ExecutionReport:
        """Assemble an :class:`ExecutionReport`."""
        completed_at = self._latest_completion(context) or datetime.now(UTC)
        duration = (completed_at - context.started_at).total_seconds()
        results = dict(context.results)
        metrics = self._build_metrics(results, duration)
        summary = self._build_summary(context, review, duration)
        providers = self._collect(results, "provider")
        agents = self._collect(results, "agent")
        tools = self._collect(results, "tool")
        workflows = self._collect(results, "workflow")
        memory_usage = self._memory_usage()
        knowledge_hits = self._knowledge_hits(results)
        files_created = self._collect_metadata(results, "files_created")
        files_modified = self._collect_metadata(results, "files_modified")
        git_commits = self._collect_metadata(results, "git_commits")
        tool_calls = getattr(executor, "tool_calls", 0) if executor else 0
        mcp_calls = getattr(executor, "mcp_calls", 0) if executor else 0
        token_usage = self._merge_token_usage(results, executor)
        estimated_cost = self._sum_cost(results, executor)
        warnings = list(review.warnings)
        errors = self._collect_errors(results)
        report = ExecutionReport(
            execution_id=context.id,
            goal=context.goal,
            status=review.overall_status,
            started_at=context.started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            plan_id=context.plan.id if context.plan else None,
            strategy=context.plan.strategy if context.plan else "sequential",
            results=results,
            metrics=metrics,
            summary=summary,
            providers_used=providers,
            agents_used=agents,
            tools_used=tools,
            workflows_used=workflows,
            memory_usage=memory_usage,
            knowledge_hits=knowledge_hits,
            files_created=files_created,
            files_modified=files_modified,
            git_commits=git_commits,
            tool_calls=tool_calls,
            mcp_calls=mcp_calls,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
            warnings=warnings,
            errors=errors,
            quality_score=review.quality_score,
            retry_recommendation=review.retry_recommendation,
            metadata=dict(context.metadata),
        )
        self.logger.info(
            "Reported execution %s: status=%s duration=%.2fs quality=%.2f",
            context.id,
            report.status.value,
            duration,
            review.quality_score,
        )
        return report

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    @staticmethod
    def _latest_completion(context: ExecutionContext) -> datetime | None:
        """Return the latest ``completed_at`` across every task result."""
        completions = [
            r.completed_at
            for r in context.results.values()
            if r.completed_at is not None
        ]
        return max(completions) if completions else None

    @staticmethod
    def _build_metrics(
        results: dict[str, ExecutionResult], duration: float
    ) -> ExecutionMetrics:
        """Build :class:`ExecutionMetrics` from per-task results."""
        completed = sum(
            1 for r in results.values() if r.status is ExecutionStatus.COMPLETED
        )
        failed = sum(1 for r in results.values() if r.status is ExecutionStatus.FAILED)
        skipped = sum(
            1 for r in results.values() if r.status is ExecutionStatus.SKIPPED
        )
        cancelled = sum(
            1 for r in results.values() if r.status is ExecutionStatus.CANCELLED
        )
        total_attempts = sum(r.attempts for r in results.values())
        total_tokens = sum(
            r.token_usage.get("total", 0)
            or (r.token_usage.get("prompt", 0) + r.token_usage.get("completion", 0))
            for r in results.values()
        )
        total_cost = sum(r.cost for r in results.values())
        providers = frozenset(r.provider for r in results.values() if r.provider)
        tools = frozenset(r.tool for r in results.values() if r.tool)
        agents = frozenset(r.agent for r in results.values() if r.agent)
        workflows = frozenset(r.workflow for r in results.values() if r.workflow)
        return ExecutionMetrics(
            total_tasks=len(results),
            completed_tasks=completed,
            failed_tasks=failed,
            skipped_tasks=skipped,
            cancelled_tasks=cancelled,
            total_attempts=total_attempts,
            total_duration_seconds=duration,
            total_tokens=total_tokens,
            total_cost=total_cost,
            providers_used=providers,
            tools_used=tools,
            agents_used=agents,
            workflows_used=workflows,
        )

    @staticmethod
    def _build_summary(
        context: ExecutionContext,
        review: ExecutionReview,
        duration: float,
    ) -> ExecutionSummary:
        """Build a short :class:`ExecutionSummary`."""
        completed = sum(
            1 for r in context.results.values() if r.status is ExecutionStatus.COMPLETED
        )
        failed = sum(
            1 for r in context.results.values() if r.status is ExecutionStatus.FAILED
        )
        total = len(context.plan.tasks) if context.plan else 0
        return ExecutionSummary(
            execution_id=context.id,
            goal=context.goal,
            status=review.overall_status,
            duration_seconds=duration,
            completed_tasks=completed,
            failed_tasks=failed,
            total_tasks=total,
            overall_quality_score=review.quality_score,
        )

    @staticmethod
    def _collect(results: dict[str, ExecutionResult], attr: str) -> list[str]:
        """Collect sorted non-``None`` values of ``attr`` from every result."""
        values = {getattr(r, attr) for r in results.values() if getattr(r, attr)}
        return sorted(values)

    @staticmethod
    def _collect_metadata(results: dict[str, ExecutionResult], key: str) -> list[str]:
        """Collect list values for ``key`` from every result's metadata."""
        out: list[str] = []
        for r in results.values():
            value = r.metadata.get(key)
            if isinstance(value, list):
                out.extend(str(v) for v in value)
            elif isinstance(value, str):
                out.append(value)
        return out

    @staticmethod
    def _collect_errors(results: dict[str, ExecutionResult]) -> list[str]:
        """Collect non-``None`` error messages from every failed result."""
        return [f"{r.task_id}: {r.error}" for r in results.values() if r.error]

    @staticmethod
    def _merge_token_usage(
        results: dict[str, ExecutionResult], executor: Any
    ) -> dict[str, int]:
        """Merge token usage from results + executor."""
        prompt = 0
        completion = 0
        for r in results.values():
            prompt += int(r.token_usage.get("prompt", 0) or 0)
            completion += int(r.token_usage.get("completion", 0) or 0)
        if executor is not None:
            exec_tokens = getattr(executor, "token_usage", {}) or {}
            prompt = max(prompt, int(exec_tokens.get("prompt", 0) or 0))
            completion = max(completion, int(exec_tokens.get("completion", 0) or 0))
        return {
            "prompt": prompt,
            "completion": completion,
            "total": prompt + completion,
        }

    @staticmethod
    def _sum_cost(results: dict[str, ExecutionResult], executor: Any) -> float:
        """Sum cost from results; fall back to executor's running total."""
        results_cost = sum(r.cost for r in results.values())
        if results_cost > 0:
            return results_cost
        if executor is not None:
            return float(getattr(executor, "estimated_cost", 0.0) or 0.0)
        return 0.0

    def _memory_usage(self) -> dict[str, Any]:
        """Pull memory statistics from the injected memory engine."""
        if self.memory is None:
            return {}
        try:
            stats: dict[str, Any] = {"stores": {}}
            for attr in (
                "working",
                "episodic",
                "semantic",
                "procedural",
                "reflection",
            ):
                store = getattr(self.memory, attr, None)
                if store is None:
                    continue
                count = len(store) if hasattr(store, "__len__") else 0
                stats["stores"][attr] = count
            return stats
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to pull memory stats: %s", exc)
            return {}

    def _knowledge_hits(self, results: dict[str, ExecutionResult]) -> int:
        """Count knowledge search hits across every result."""
        if self.knowledge is None:
            return 0
        hits = 0
        for r in results.values():
            output = r.output
            if isinstance(output, list):
                hits += len(output)
            elif isinstance(output, dict) and "results" in output:
                hits += len(output["results"])
        return hits


__all__ = ["BaseReporter", "ExecutionReporter"]
