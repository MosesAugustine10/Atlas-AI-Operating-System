"""Execution strategies for the Atlas Execution Engine.

This module is a *leaf* in the execution package dependency graph: it
depends only on the standard library. It defines the canonical
:class:`ExecutionStrategy` enum and a small set of strategy-related
helpers used by the planner, dispatcher, and executor.

Strategies control *how* the executor walks the plan:

* :attr:`SEQUENTIAL` — execute tasks one at a time, in declaration order.
* :attr:`PARALLEL` — execute independent tasks concurrently (placeholder:
  still sequential under the hood, but flagged for future thread pool).
* :attr:`PRIORITY` — execute tasks in priority order (highest first),
  respecting dependencies.
* :attr:`DEPENDENCY` — execute tasks in dependency order (topological
  sort), running ready tasks as soon as their dependencies complete.
* :attr:`RETRY` — like :attr:`SEQUENTIAL` but with aggressive retry.
* :attr:`FALLBACK` — like :attr:`SEQUENTIAL` but with provider fallback.
* :attr:`MANUAL` — pause before each task and wait for operator approval.
* :attr:`AUTOMATIC` — run end-to-end without pausing (default).

Strategies are intentionally orthogonal to the plan's task list: the
same plan can be executed under different strategies.
"""

from __future__ import annotations

import enum


class ExecutionStrategy(enum.StrEnum):
    """How the executor walks an :class:`atlas.execution.models.ExecutionPlan`.

    Attributes:
        SEQUENTIAL: Execute tasks one at a time, in declaration order.
        PARALLEL: Execute independent tasks concurrently (placeholder).
        PRIORITY: Execute tasks in priority order (highest first).
        DEPENDENCY: Execute tasks in topological (dependency) order.
        RETRY: Like SEQUENTIAL but with aggressive retry.
        FALLBACK: Like SEQUENTIAL but with provider fallback.
        MANUAL: Pause before each task and wait for operator approval.
        AUTOMATIC: Run end-to-end without pausing (default).
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PRIORITY = "priority"
    DEPENDENCY = "dependency"
    RETRY = "retry"
    FALLBACK = "fallback"
    MANUAL = "manual"
    AUTOMATIC = "automatic"


#: Strategies that respect task dependencies (i.e. will not run a task
#: before its dependencies have completed).
DEPENDENCY_AWARE: frozenset[ExecutionStrategy] = frozenset(
    {
        ExecutionStrategy.PARALLEL,
        ExecutionStrategy.PRIORITY,
        ExecutionStrategy.DEPENDENCY,
        ExecutionStrategy.AUTOMATIC,
    }
)

#: Strategies that pause for operator input.
INTERACTIVE: frozenset[ExecutionStrategy] = frozenset({ExecutionStrategy.MANUAL})

#: Strategies that aggressively retry failed tasks.
RETRY_AGGRESSIVE: frozenset[ExecutionStrategy] = frozenset({ExecutionStrategy.RETRY})

#: Strategies that fall back to alternative providers on failure.
FALLBACK_ENABLED: frozenset[ExecutionStrategy] = frozenset({ExecutionStrategy.FALLBACK})


def is_dependency_aware(strategy: ExecutionStrategy) -> bool:
    """Return ``True`` if ``strategy`` respects task dependencies."""
    return strategy in DEPENDENCY_AWARE


def is_interactive(strategy: ExecutionStrategy) -> bool:
    """Return ``True`` if ``strategy`` pauses for operator input."""
    return strategy in INTERACTIVE


def is_retry_aggressive(strategy: ExecutionStrategy) -> bool:
    """Return ``True`` if ``strategy`` aggressively retries failed tasks."""
    return strategy in RETRY_AGGRESSIVE


def is_fallback_enabled(strategy: ExecutionStrategy) -> bool:
    """Return ``True`` if ``strategy`` falls back to alternative providers."""
    return strategy in FALLBACK_ENABLED


def all_strategies() -> tuple[ExecutionStrategy, ...]:
    """Return every strategy in declaration order."""
    return tuple(ExecutionStrategy)


__all__ = [
    "DEPENDENCY_AWARE",
    "ExecutionStrategy",
    "FALLBACK_ENABLED",
    "INTERACTIVE",
    "RETRY_AGGRESSIVE",
    "all_strategies",
    "is_dependency_aware",
    "is_fallback_enabled",
    "is_interactive",
    "is_retry_aggressive",
]
