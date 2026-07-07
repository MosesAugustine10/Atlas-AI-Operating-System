"""The Atlas Execution Engine.

The Execution Engine is the heart of the Atlas AI Operating System. It
converts a natural-language goal into an ordered, executable plan,
dispatches each task to the appropriate agent / provider / tool /
workflow, executes the tasks, reviews the outcomes, and produces a
professional execution report.

The engine is **personal** (optimized for one operator), **provider-
agnostic**, **agent-agnostic**, **tool-agnostic**, **workflow-agnostic**,
**MCP-ready**, and **fully offline compatible**. Every concrete concern
is injected; the defaults are deterministic placeholders.

Pipeline:

    Goal → Planner → Dispatcher → Executor → Reviewer → Reporter → Report

Dependency graph (acyclic):

* ``models`` — leaf (frozen dataclasses + enums).
* ``strategy`` — leaf (execution strategy enum).
* ``planner`` — depends on ``models``, ``strategy``.
* ``dispatcher`` — depends on ``models``, ``strategy``.
* ``executor`` — depends on ``models``, ``dispatcher``.
* ``reviewer`` — depends on ``models``.
* ``reporter`` — depends on ``models``, ``reviewer``.
* ``engine`` — depends on all of the above.
"""

from __future__ import annotations

from atlas.execution.dispatcher import (
    BaseDispatcher,
    DispatchResult,
    ExecutionDispatcher,
    TaskResolution,
)
from atlas.execution.engine import ExecutionEngine, ExecutionEngineError
from atlas.execution.executor import (
    Action,
    BaseExecutor,
    ExecutionExecutor,
    ExecutorError,
)
from atlas.execution.models import (
    TERMINAL_STATUSES,
    ExecutionContext,
    ExecutionHistory,
    ExecutionHistoryEntry,
    ExecutionMetrics,
    ExecutionPlan,
    ExecutionReport,
    ExecutionResult,
    ExecutionStatus,
    ExecutionSummary,
    ExecutionTask,
    Priority,
    RetryPolicy,
    TaskKind,
)
from atlas.execution.planner import BasePlanner, ExecutionPlanner
from atlas.execution.reporter import BaseReporter, ExecutionReporter
from atlas.execution.reviewer import (
    BaseReviewer,
    ExecutionReview,
    ExecutionReviewer,
    TaskReview,
)
from atlas.execution.strategy import (
    DEPENDENCY_AWARE,
    FALLBACK_ENABLED,
    INTERACTIVE,
    RETRY_AGGRESSIVE,
    ExecutionStrategy,
    all_strategies,
    is_dependency_aware,
    is_fallback_enabled,
    is_interactive,
    is_retry_aggressive,
)

__all__ = [
    "Action",
    "BaseDispatcher",
    "BaseExecutor",
    "BasePlanner",
    "BaseReporter",
    "BaseReviewer",
    "DEPENDENCY_AWARE",
    "DispatchResult",
    "ExecutionContext",
    "ExecutionDispatcher",
    "ExecutionEngine",
    "ExecutionEngineError",
    "ExecutionExecutor",
    "ExecutionHistory",
    "ExecutionHistoryEntry",
    "ExecutionMetrics",
    "ExecutionPlan",
    "ExecutionPlanner",
    "ExecutionReport",
    "ExecutionReporter",
    "ExecutionResult",
    "ExecutionReview",
    "ExecutionReviewer",
    "ExecutionStatus",
    "ExecutionStrategy",
    "ExecutionSummary",
    "ExecutionTask",
    "ExecutorError",
    "FALLBACK_ENABLED",
    "INTERACTIVE",
    "Priority",
    "RETRY_AGGRESSIVE",
    "RetryPolicy",
    "TERMINAL_STATUSES",
    "TaskKind",
    "TaskResolution",
    "TaskReview",
    "all_strategies",
    "is_dependency_aware",
    "is_fallback_enabled",
    "is_interactive",
    "is_retry_aggressive",
]
