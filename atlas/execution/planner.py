"""Execution planner — converts a goal into an ordered execution plan.

The :class:`ExecutionPlanner` is the first stage of the execution
pipeline. It receives a natural-language goal and produces an
:class:`atlas.execution.models.ExecutionPlan` — an immutable, ordered
list of :class:`atlas.execution.models.ExecutionTask` items.

The current implementation is a **deterministic placeholder**: it
recognises a small set of goal templates (``"create website"``,
``"research"``, ``"generate code"``, etc.) and produces a fixed plan
for each. This keeps the engine fully testable offline while leaving
the door open for future AI-driven planning — replace
:meth:`ExecutionPlanner.plan` with an LLM-backed implementation and
the rest of the engine is unchanged.

Supported goal templates (case-insensitive substring match):

* ``"create website"`` → research → generate_code → generate_assets →
  run_tests → git_commit → deploy
* ``"research"`` → research
* ``"generate code"`` → research → generate_code → run_tests
* ``"deploy"`` → run_tests → git_commit → deploy
* Anything else → a single ``custom`` task carrying the goal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger
from atlas.execution.models import (
    ExecutionPlan,
    ExecutionTask,
    Priority,
    RetryPolicy,
    TaskKind,
)
from atlas.execution.strategy import ExecutionStrategy


class BasePlanner(ABC):
    """Abstract contract for execution planners."""

    @abstractmethod
    def plan(
        self,
        goal: str,
        strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC,
        **kwargs: Any,
    ) -> ExecutionPlan:
        """Produce an :class:`ExecutionPlan` for ``goal``."""


class ExecutionPlanner(BasePlanner):
    """Deterministic placeholder planner.

    Parameters:
        default_strategy: The strategy to assign to plans when the
            caller does not specify one. Defaults to
            :attr:`ExecutionStrategy.AUTOMATIC`.
        default_retry_policy: The retry policy to assign to every task.
            Defaults to ``RetryPolicy()`` (3 attempts, 1s backoff).
    """

    def __init__(
        self,
        default_strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC,
        default_retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.default_strategy = default_strategy
        self.default_retry_policy = (
            default_retry_policy if default_retry_policy is not None else RetryPolicy()
        )
        self.logger = get_logger("execution.planner")

    def plan(
        self,
        goal: str,
        strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC,
        **kwargs: Any,  # noqa: ARG002
    ) -> ExecutionPlan:
        """Produce an :class:`ExecutionPlan` for ``goal``.

        The current implementation is deterministic: it matches the goal
        against a small set of templates and returns a fixed plan.
        Future versions will delegate to an LLM.
        """
        if not goal or not goal.strip():
            raise ValueError("goal must be non-empty")

        goal_lower = goal.lower()
        tasks: list[ExecutionTask]

        if "create website" in goal_lower:
            tasks = self._website_plan(goal)
        elif "research" in goal_lower:
            tasks = self._research_plan(goal)
        elif "generate code" in goal_lower or "write code" in goal_lower:
            tasks = self._code_plan(goal)
        elif "deploy" in goal_lower:
            tasks = self._deploy_plan(goal)
        else:
            tasks = self._custom_plan(goal)

        plan = ExecutionPlan(
            goal=goal,
            tasks=tasks,
            strategy=strategy.value,
            metadata={
                "planner": "deterministic",
                "template": self._template_name(goal_lower),
            },
        )
        self.logger.info(
            "Planned %d task(s) for goal %r (template=%s)",
            len(tasks),
            goal[:60],
            plan.metadata["template"],
        )
        return plan

    # ------------------------------------------------------------------
    # Goal templates
    # ------------------------------------------------------------------

    def _website_plan(self, goal: str) -> list[ExecutionTask]:
        """Plan: research, generate_code, generate_assets, tests, commit, deploy."""
        research = self._task(
            name="Research",
            kind=TaskKind.RESEARCH,
            action="research",
            params={"topic": goal},
            priority=Priority.HIGH,
        )
        generate_code = self._task(
            name="Generate Code",
            kind=TaskKind.GENERATE,
            action="generate_code",
            params={"goal": goal},
            dependencies=[research.id],
            priority=Priority.HIGH,
        )
        generate_assets = self._task(
            name="Generate Assets",
            kind=TaskKind.GENERATE,
            action="generate_assets",
            params={"goal": goal},
            dependencies=[research.id],
            priority=Priority.NORMAL,
            optional=True,
        )
        run_tests = self._task(
            name="Run Tests",
            kind=TaskKind.TEST,
            action="run_tests",
            params={},
            dependencies=[generate_code.id],
            priority=Priority.NORMAL,
        )
        git_commit = self._task(
            name="Git Commit",
            kind=TaskKind.GIT,
            action="git_commit",
            params={"message": f"feat: {goal[:50]}"},
            dependencies=[run_tests.id, generate_assets.id],
            priority=Priority.LOW,
        )
        deploy = self._task(
            name="Deploy",
            kind=TaskKind.DEPLOY,
            action="deploy",
            params={"target": "production"},
            dependencies=[git_commit.id],
            priority=Priority.LOW,
        )
        return [research, generate_code, generate_assets, run_tests, git_commit, deploy]

    def _research_plan(self, goal: str) -> list[ExecutionTask]:
        """Plan: research."""
        return [
            self._task(
                name="Research",
                kind=TaskKind.RESEARCH,
                action="research",
                params={"topic": goal},
                priority=Priority.HIGH,
            )
        ]

    def _code_plan(self, goal: str) -> list[ExecutionTask]:
        """Plan: research → generate_code → run_tests."""
        research = self._task(
            name="Research",
            kind=TaskKind.RESEARCH,
            action="research",
            params={"topic": goal},
            priority=Priority.HIGH,
        )
        generate_code = self._task(
            name="Generate Code",
            kind=TaskKind.GENERATE,
            action="generate_code",
            params={"goal": goal},
            dependencies=[research.id],
            priority=Priority.HIGH,
        )
        run_tests = self._task(
            name="Run Tests",
            kind=TaskKind.TEST,
            action="run_tests",
            params={},
            dependencies=[generate_code.id],
            priority=Priority.NORMAL,
        )
        return [research, generate_code, run_tests]

    def _deploy_plan(self, goal: str) -> list[ExecutionTask]:
        """Plan: run_tests → git_commit → deploy."""
        run_tests = self._task(
            name="Run Tests",
            kind=TaskKind.TEST,
            action="run_tests",
            params={},
            priority=Priority.HIGH,
        )
        git_commit = self._task(
            name="Git Commit",
            kind=TaskKind.GIT,
            action="git_commit",
            params={"message": f"chore: {goal[:50]}"},
            dependencies=[run_tests.id],
            priority=Priority.NORMAL,
        )
        deploy = self._task(
            name="Deploy",
            kind=TaskKind.DEPLOY,
            action="deploy",
            params={"target": "production"},
            dependencies=[git_commit.id],
            priority=Priority.LOW,
        )
        return [run_tests, git_commit, deploy]

    def _custom_plan(self, goal: str) -> list[ExecutionTask]:
        """Plan: a single custom task carrying the goal."""
        return [
            self._task(
                name="Execute Goal",
                kind=TaskKind.CUSTOM,
                action="execute_goal",
                params={"goal": goal},
                priority=Priority.NORMAL,
            )
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _task(
        self,
        name: str,
        kind: TaskKind,
        action: str,
        params: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        priority: Priority = Priority.NORMAL,
        optional: bool = False,
        retry_policy: RetryPolicy | None = None,
    ) -> ExecutionTask:
        """Build an :class:`ExecutionTask` with the planner's defaults."""
        return ExecutionTask(
            name=name,
            kind=kind,
            action=action,
            params=dict(params or {}),
            dependencies=list(dependencies or []),
            priority=priority,
            optional=optional,
            retry_policy=(
                retry_policy if retry_policy is not None else self.default_retry_policy
            ),
        )

    @staticmethod
    def _template_name(goal_lower: str) -> str:
        if "create website" in goal_lower:
            return "website"
        if "research" in goal_lower:
            return "research"
        if "generate code" in goal_lower or "write code" in goal_lower:
            return "code"
        if "deploy" in goal_lower:
            return "deploy"
        return "custom"


__all__ = ["BasePlanner", "ExecutionPlanner"]
