"""Execution engine — the top-level pipeline orchestrator.

The :class:`ExecutionEngine` is the heart of the Atlas Execution
Engine. It wires together the five pipeline stages:

    Goal → Planner → Dispatcher → Executor → Reviewer → Reporter → Report

Every stage is dependency-injected. The engine never imports concrete
subsystem implementations; it accepts handles to a ``ProviderManager``,
``ToolManager``, ``WorkflowEngine``, ``SkillManager``,
``MemoryEngine``, and ``KnowledgeEngine`` and passes them through to
the executor.

The engine is **personal**: it is optimized for a single operator and
makes no multi-tenant assumptions. It is **MCP-ready**: an MCP
connector can be injected as a tool and the executor will dispatch to
it without code changes. It is **fully offline**: every default is
deterministic and in-memory.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.execution.dispatcher import (
    BaseDispatcher,
    DispatchResult,
    ExecutionDispatcher,
)
from atlas.execution.executor import (
    BaseExecutor,
    ExecutionExecutor,
    ExecutorError,
)
from atlas.execution.models import (
    ExecutionContext,
    ExecutionHistory,
    ExecutionHistoryEntry,
    ExecutionReport,
)
from atlas.execution.planner import (
    BasePlanner,
    ExecutionPlanner,
)
from atlas.execution.reporter import (
    BaseReporter,
    ExecutionReporter,
)
from atlas.execution.reviewer import (
    BaseReviewer,
    ExecutionReview,
    ExecutionReviewer,
)
from atlas.execution.strategy import ExecutionStrategy


class ExecutionEngineError(RuntimeError):
    """Raised when the engine cannot perform the requested operation."""


class ExecutionEngine:
    """Top-level execution pipeline orchestrator.

    Parameters:
        planner: The :class:`BasePlanner` to use. Defaults to
            :class:`ExecutionPlanner`.
        dispatcher: The :class:`BaseDispatcher` to use. Defaults to
            :class:`ExecutionDispatcher`.
        executor: The :class:`BaseExecutor` to use. Defaults to
            :class:`ExecutionExecutor`.
        reviewer: The :class:`BaseReviewer` to use. Defaults to
            :class:`ExecutionReviewer`.
        reporter: The :class:`BaseReporter` to use. Defaults to
            :class:`ExecutionReporter`.
        history: Optional :class:`ExecutionHistory` for recording runs.
            A fresh one is created if omitted.
        providers: Optional provider manager (passed to the executor).
        tools: Optional tool manager (passed to the executor).
        workflows: Optional workflow engine (passed to the executor).
        skills: Optional skill manager (passed to the executor).
        memory: Optional memory engine (passed to the executor and
            reporter).
        knowledge: Optional knowledge engine (passed to the executor
            and reporter).
        default_strategy: The :class:`ExecutionStrategy` to use when
            the caller does not specify one. Defaults to
            :attr:`ExecutionStrategy.AUTOMATIC`.
    """

    def __init__(
        self,
        planner: BasePlanner | None = None,
        dispatcher: BaseDispatcher | None = None,
        executor: BaseExecutor | None = None,
        reviewer: BaseReviewer | None = None,
        reporter: BaseReporter | None = None,
        history: ExecutionHistory | None = None,
        providers: Any = None,
        tools: Any = None,
        workflows: Any = None,
        skills: Any = None,
        memory: Any = None,
        knowledge: Any = None,
        default_strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC,
    ) -> None:
        self.memory = memory
        self.knowledge = knowledge
        self.providers = providers
        self.tools = tools
        self.workflows = workflows
        self.skills = skills
        self.default_strategy = default_strategy
        self.planner = planner if planner is not None else ExecutionPlanner()
        self.dispatcher = (
            dispatcher
            if dispatcher is not None
            else ExecutionDispatcher(
                agents=None,
                providers=self._registry(providers),
                tools=self._registry(tools),
                workflows=self._registry(workflows),
                skills=skills,
            )
        )
        self.executor = (
            executor
            if executor is not None
            else ExecutionExecutor(
                providers=providers,
                tools=tools,
                workflows=workflows,
                skills=skills,
                memory=memory,
                knowledge=knowledge,
            )
        )
        self.reviewer = reviewer if reviewer is not None else ExecutionReviewer()
        self.reporter = (
            reporter
            if reporter is not None
            else ExecutionReporter(memory=memory, knowledge=knowledge)
        )
        self.history = history if history is not None else ExecutionHistory()
        self.logger = get_logger("execution.engine")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        goal: str,
        strategy: ExecutionStrategy | None = None,
        user: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionReport:
        """Execute ``goal`` end-to-end and return an :class:`ExecutionReport`.

        This is the canonical entry point. The pipeline is:

        1. :meth:`_plan` — produce an :class:`ExecutionPlan`.
        2. :meth:`_dispatch` — resolve every task to a
           :class:`atlas.execution.dispatcher.TaskResolution`.
        3. :meth:`_execute` — run every task.
        4. :meth:`_review` — evaluate the results.
        5. :meth:`_report` — assemble the :class:`ExecutionReport`.
        """
        strat = strategy if strategy is not None else self.default_strategy
        self.logger.info("Running goal: %r (strategy=%s)", goal[:60], strat.value)

        context = ExecutionContext(goal=goal, user=user, metadata=dict(metadata or {}))

        context = self._plan(context, strat)
        dispatch = self._dispatch(context, strat)
        context = self._execute(context, dispatch)
        review = self._review(context)
        report = self._report(context, review)

        self._record_history(report)
        self.logger.info(
            "Execution %s finished: status=%s duration=%.2fs tasks=%d",
            context.id,
            report.status.value,
            report.duration_seconds,
            len(report.results),
        )
        return report

    def execute_goal(
        self,
        goal: str,
        strategy: ExecutionStrategy | None = None,
    ) -> ExecutionReport:
        """Alias for :meth:`run`."""
        return self.run(goal, strategy=strategy)

    def get_history(self) -> ExecutionHistory:
        """Return the execution history."""
        return self.history

    def status(self) -> dict[str, Any]:
        """Return a brief status summary of the engine."""
        return {
            "history_entries": len(self.history),
            "default_strategy": self.default_strategy.value,
            "has_providers": self.providers is not None,
            "has_tools": self.tools is not None,
            "has_workflows": self.workflows is not None,
            "has_skills": self.skills is not None,
            "has_memory": self.memory is not None,
            "has_knowledge": self.knowledge is not None,
        }

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _plan(
        self, context: ExecutionContext, strategy: ExecutionStrategy
    ) -> ExecutionContext:
        """Stage 1: produce an :class:`ExecutionPlan`."""
        plan = self.planner.plan(context.goal, strategy=strategy)
        return context.with_plan(plan)

    def _dispatch(
        self, context: ExecutionContext, strategy: ExecutionStrategy
    ) -> DispatchResult:
        """Stage 2: resolve every task to a :class:`TaskResolution`."""
        if context.plan is None:
            raise ExecutionEngineError("context has no plan")
        return self.dispatcher.dispatch(context.plan, strategy=strategy)

    def _execute(
        self, context: ExecutionContext, dispatch: DispatchResult
    ) -> ExecutionContext:
        """Stage 3: run every task via the executor."""
        if context.plan is None:
            raise ExecutionEngineError("context has no plan")
        try:
            return self.executor.execute_plan(context, dispatch)  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise ExecutionEngineError(
                "executor does not implement execute_plan"
            ) from exc
        except ExecutorError as exc:
            raise ExecutionEngineError(str(exc)) from exc

    def _review(self, context: ExecutionContext) -> ExecutionReview:
        """Stage 4: evaluate the results."""
        return self.reviewer.review(context)

    def _report(
        self, context: ExecutionContext, review: ExecutionReview
    ) -> ExecutionReport:
        """Stage 5: assemble the :class:`ExecutionReport`."""
        return self.reporter.report(context, review, executor=self.executor)

    def _record_history(self, report: ExecutionReport) -> None:
        """Record the report in :attr:`history`."""
        entry = ExecutionHistoryEntry(
            execution_id=report.execution_id,
            goal=report.goal,
            status=report.status,
            started_at=report.started_at,
            completed_at=report.completed_at,
            duration_seconds=report.duration_seconds,
            task_count=report.metrics.total_tasks,
            completed_tasks=report.metrics.completed_tasks,
            failed_tasks=report.metrics.failed_tasks,
            quality_score=report.quality_score,
            report=report,
        )
        self.history.record(entry)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _registry(manager: Any) -> Any:
        """Return the ``.registry`` attribute of ``manager`` if present."""
        if manager is None:
            return None
        return getattr(manager, "registry", manager)

    def __repr__(self) -> str:
        return (
            f"<ExecutionEngine history={len(self.history)} "
            f"strategy={self.default_strategy.value}>"
        )


__all__ = ["ExecutionEngine", "ExecutionEngineError"]
