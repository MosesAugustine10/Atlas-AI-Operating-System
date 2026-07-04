"""Execution executor — runs a single task at a time.

The :class:`ExecutionExecutor` is the third stage of the execution
pipeline. It receives an :class:`atlas.execution.models.ExecutionTask`
plus the dispatcher's :class:`atlas.execution.dispatcher.TaskResolution`
and runs the task to completion (or failure), producing an
:class:`atlas.execution.models.ExecutionResult`.

The executor is **dependency-injected**: it never imports concrete
subsystem implementations. Instead, it accepts optional handles to a
``ProviderManager``, ``ToolManager``, ``WorkflowEngine``,
``SkillManager``, ``MemoryEngine``, and ``KnowledgeEngine``. When a
handle is present, the executor can dispatch the task to that
subsystem; when it is ``None``, the executor falls back to a
deterministic placeholder action registry (built-in actions:
``noop``, ``echo``, ``fail``, ``succeed``).

This keeps the executor fully functional offline (zero external
dependencies) while remaining MCP-ready: a future MCP connector can
be injected as a "tool" and the executor will dispatch to it without
code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.execution.dispatcher import DispatchResult, TaskResolution
from atlas.execution.models import (
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    ExecutionTask,
    RetryPolicy,
)

# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------


Action = Callable[[dict[str, Any], dict[str, Any]], Any]


def _noop_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always succeed and return a sentinel."""
    return "noop"


def _echo_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Succeed and echo the supplied params."""
    return dict(params)


def _fail_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always raise a :class:`RuntimeError`."""
    message = params.get("message", "intentional failure")
    raise RuntimeError(message)


def _succeed_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always succeed and return a success marker."""
    return {"status": "success", "params": dict(params)}


def _research_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for research tasks."""
    topic = params.get("topic") or params.get("goal") or "unknown"
    return {
        "topic": topic,
        "findings": [
            f"Finding 1 about {topic}",
            f"Finding 2 about {topic}",
        ],
        "sources": ["placeholder-source-1", "placeholder-source-2"],
    }


def _generate_code_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for code generation tasks."""
    goal = params.get("goal") or params.get("prompt") or "unknown"
    return {
        "goal": goal,
        "files_created": ["main.py"],
        "code": f"# Auto-generated code for: {goal}\nprint('hello world')\n",
    }


def _generate_assets_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for asset generation tasks."""
    goal = params.get("goal") or "assets"
    return {
        "goal": goal,
        "files_created": ["assets/logo.svg", "assets/hero.png"],
    }


def _run_tests_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for test execution tasks."""
    return {
        "passed": 10,
        "failed": 0,
        "skipped": 0,
        "duration_seconds": 1.5,
    }


def _git_commit_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for git commit tasks."""
    message = params.get("message") or "auto-commit"
    return {
        "commit_hash": "abc123def456",
        "message": message,
        "files_committed": 1,
    }


def _deploy_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for deploy tasks."""
    target = params.get("target") or "production"
    return {
        "target": target,
        "status": "deployed",
        "url": f"https://example.{target}",
    }


def _execute_goal_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Deterministic placeholder for custom goal execution."""
    goal = params.get("goal") or "unknown"
    return {
        "goal": goal,
        "status": "completed",
        "result": f"Executed goal: {goal}",
    }


_BUILTIN_ACTIONS: dict[str, Action] = {
    "noop": _noop_action,
    "echo": _echo_action,
    "fail": _fail_action,
    "succeed": _succeed_action,
    "research": _research_action,
    "generate_code": _generate_code_action,
    "generate_assets": _generate_assets_action,
    "run_tests": _run_tests_action,
    "git_commit": _git_commit_action,
    "deploy": _deploy_action,
    "execute_goal": _execute_goal_action,
}


# ---------------------------------------------------------------------------
# Executor exceptions
# ---------------------------------------------------------------------------


class ExecutorError(RuntimeError):
    """Raised when the executor cannot perform the requested operation."""


# ---------------------------------------------------------------------------
# Base and concrete executor
# ---------------------------------------------------------------------------


class BaseExecutor(ABC):
    """Abstract contract for execution executors."""

    @abstractmethod
    def execute(
        self,
        task: ExecutionTask,
        resolution: TaskResolution,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Run ``task`` and return an :class:`ExecutionResult`."""


class ExecutionExecutor(BaseExecutor):
    """Dependency-injected task executor.

    Parameters:
        providers: Optional :class:`ProviderManager` (or compatible).
            When present, the executor can call ``providers.generate()``
            for tasks whose action is ``"generate"`` or ``"research"``.
        tools: Optional :class:`ToolManager` (or compatible). When
            present, the executor can call ``tools.execute(name, **kwargs)``
            for tasks whose resolution selects a tool.
        workflows: Optional :class:`WorkflowEngine` (or compatible).
            When present, the executor can drive a workflow run for
            tasks whose resolution selects a workflow.
        skills: Optional :class:`SkillManager` (or compatible). When
            present, the executor can invoke a registered skill.
        memory: Optional :class:`MemoryEngine` (or compatible). When
            present, the executor records every task outcome to memory.
        knowledge: Optional :class:`KnowledgeEngine` (or compatible).
            When present, the executor can call ``knowledge.search()``
            for research tasks.
        actions: Optional mapping of action name -> callable. The
            callable receives ``(params, context_dict)`` and may return
            any object. Raising an exception marks the task failed.
        default_provider: Name of the provider to use when none is
            selected by the dispatcher. Defaults to ``"zai"``.
    """

    def __init__(
        self,
        providers: Any = None,
        tools: Any = None,
        workflows: Any = None,
        skills: Any = None,
        memory: Any = None,
        knowledge: Any = None,
        actions: dict[str, Action] | None = None,
        default_provider: str = "zai",
    ) -> None:
        self.providers = providers
        self.tools = tools
        self.workflows = workflows
        self.skills = skills
        self.memory = memory
        self.knowledge = knowledge
        self.default_provider = default_provider
        self.logger = get_logger("execution.executor")
        self._actions: dict[str, Action] = {}
        for name, fn in (actions or {}).items():
            self.register_action(name, fn)
        for name, fn in _BUILTIN_ACTIONS.items():
            self._actions.setdefault(name, fn)
        # Running counters for the reporter.
        self.tool_calls: int = 0
        self.mcp_calls: int = 0
        self.token_usage: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}
        self.estimated_cost: float = 0.0

    def register_action(self, name: str, fn: Action) -> None:
        """Register or override an action by name."""
        if not name or not name.strip():
            raise ValueError("Action name must be non-empty.")
        if not callable(fn):
            raise TypeError("Action must be callable.")
        self._actions[name] = fn

    def has_action(self, name: str) -> bool:
        """Return ``True`` if ``name`` is a registered action."""
        return name in self._actions

    def known_actions(self) -> list[str]:
        """Return a sorted list of registered action names."""
        return sorted(self._actions)

    def execute(
        self,
        task: ExecutionTask,
        resolution: TaskResolution,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Run ``task`` and return an :class:`ExecutionResult`.

        Honors :attr:`task.retry_policy` — retries up to
        ``max_attempts`` times with exponential backoff (delay is not
        actually slept; the executor is deterministic and offline).
        """
        started = datetime.now(UTC)
        attempts = 0
        last_error: str | None = None
        policy = task.retry_policy

        while attempts < policy.max_attempts:
            attempts += 1
            try:
                output = self._dispatch(task, resolution, context)
                result = ExecutionResult(
                    task_id=task.id,
                    status=ExecutionStatus.COMPLETED,
                    output=output,
                    started_at=started,
                    completed_at=datetime.now(UTC),
                    attempts=attempts,
                    provider=resolution.provider,
                    agent=resolution.agent,
                    tool=resolution.tool,
                    workflow=resolution.workflow,
                    token_usage=dict(self.token_usage),
                    cost=self.estimated_cost,
                    metadata={"resolution_reason": resolution.reason},
                )
                self._record_memory(task, result)
                return result
            except Exception as exc:  # noqa: BLE001 — surface to result
                last_error = f"{type(exc).__name__}: {exc}"
                self.logger.warning(
                    "Task %s attempt %d failed: %s",
                    task.id,
                    attempts,
                    last_error,
                )
                if not self._is_retryable(policy, last_error):
                    break

        result = ExecutionResult(
            task_id=task.id,
            status=ExecutionStatus.FAILED,
            error=last_error,
            started_at=started,
            completed_at=datetime.now(UTC),
            attempts=attempts,
            provider=resolution.provider,
            agent=resolution.agent,
            tool=resolution.tool,
            workflow=resolution.workflow,
            token_usage=dict(self.token_usage),
            cost=self.estimated_cost,
            metadata={"resolution_reason": resolution.reason},
        )
        self._record_memory(task, result)
        return result

    def execute_plan(
        self,
        context: ExecutionContext,
        dispatch: DispatchResult,
    ) -> ExecutionContext:
        """Execute every task in ``context.plan`` using ``dispatch``.

        Tasks are executed in declaration order. Optional tasks whose
        dependencies failed are marked :attr:`ExecutionStatus.SKIPPED`.
        Execution stops after the first non-optional failure, but any
        subsequent optional tasks are still marked SKIPPED so the report
        reflects every task's final state.
        """
        if context.plan is None:
            raise ExecutorError("context has no plan")

        ctx = context
        failed = False
        for task in context.plan.tasks:
            resolution = dispatch.resolutions.get(task.id)
            if resolution is None:
                resolution = TaskResolution(task_id=task.id, action=task.action)

            # If a non-optional task already failed, only process remaining
            # optional tasks (to mark them skipped).
            if failed:
                if task.optional:
                    skipped = ExecutionResult(
                        task_id=task.id,
                        status=ExecutionStatus.SKIPPED,
                        started_at=datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        attempts=0,
                        metadata={"reason": "prior_failure"},
                    )
                    ctx = ctx.with_result(skipped)
                continue

            # Skip optional tasks whose dependencies failed.
            if self._dependencies_failed(task, ctx):
                if task.optional:
                    skipped = ExecutionResult(
                        task_id=task.id,
                        status=ExecutionStatus.SKIPPED,
                        started_at=datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        attempts=0,
                        metadata={"reason": "dependencies_failed"},
                    )
                    ctx = ctx.with_result(skipped)
                    continue
                # Non-optional task with failed dependencies → fail fast.
                failed_result = ExecutionResult(
                    task_id=task.id,
                    status=ExecutionStatus.FAILED,
                    error="dependencies_failed",
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    attempts=0,
                )
                ctx = ctx.with_result(failed_result)
                failed = True
                continue

            result = self.execute(task, resolution, ctx)
            ctx = ctx.with_result(result)
            if result.status is ExecutionStatus.FAILED and not task.optional:
                failed = True

        return ctx

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        task: ExecutionTask,
        resolution: TaskResolution,
        context: ExecutionContext,
    ) -> Any:
        """Dispatch ``task`` to the appropriate subsystem.

        Order of preference:
        1. Tool (if resolution selects one and ``self.tools`` is present).
        2. Workflow (if resolution selects one and ``self.workflows`` is present).
        3. Skill (if resolution selects one and ``self.skills`` is present).
        4. Provider (if ``self.providers`` is present and the action
           looks generative).
        5. Knowledge (for research tasks when ``self.knowledge`` is present).
        6. Built-in action registry.
        """
        ctx_dict = self._build_context_dict(task, context)

        # 1. Tool
        if resolution.tool and self.tools is not None:
            return self._invoke_tool(resolution.tool, resolution.params, ctx_dict)

        # 2. Workflow
        if resolution.workflow and self.workflows is not None:
            return self._invoke_workflow(
                resolution.workflow, resolution.params, ctx_dict
            )

        # 3. Skill
        if resolution.skill and self.skills is not None:
            return self._invoke_skill(resolution.skill, resolution.params, ctx_dict)

        # 4. Provider (generative actions)
        if self.providers is not None and self._is_generative(task, resolution):
            return self._invoke_provider(task, resolution, ctx_dict)

        # 5. Knowledge (research)
        if self.knowledge is not None and task.kind.value == "research":
            return self._invoke_knowledge(resolution.params, ctx_dict)

        # 6. Built-in action registry
        action = self._actions.get(resolution.action)
        if action is None:
            raise ExecutorError(
                f"Unknown action: {resolution.action!r} "
                f"(task={task.id}, kind={task.kind.value})"
            )
        return action(dict(resolution.params), ctx_dict)

    def _build_context_dict(
        self, task: ExecutionTask, context: ExecutionContext
    ) -> dict[str, Any]:
        """Build the dict passed to actions / tools / skills."""
        ctx: dict[str, Any] = {
            "execution_id": context.id,
            "goal": context.goal,
            "task_id": task.id,
            "task_name": task.name,
            "task_kind": task.kind.value,
            "artifacts": dict(context.artifacts),
            "results": {
                tid: r.output for tid, r in context.results.items() if r.success
            },
        }
        return ctx

    def _invoke_tool(
        self, name: str, params: dict[str, Any], ctx: dict[str, Any]
    ) -> Any:
        """Invoke a tool via the injected tool manager."""
        self.tool_calls += 1
        result = self.tools.execute(name, **params)  # type: ignore[union-attr]
        # ToolResult has .success / .output / .error
        if hasattr(result, "is_error") and result.is_error():
            raise ExecutorError(
                f"tool {name!r} failed: {getattr(result, 'error', '?')}"
            )
        return getattr(result, "output", result)

    def _invoke_workflow(
        self, workflow_id: str, params: dict[str, Any], ctx: dict[str, Any]
    ) -> Any:
        """Drive a workflow run via the injected workflow engine."""
        engine = self.workflows  # type: ignore[assignment]
        run = engine.create_run(workflow_id, inputs=dict(params))  # type: ignore[union-attr]
        run = engine.start(run.id)  # type: ignore[union-attr]
        if run.state.value != "completed":
            raise ExecutorError(
                f"workflow {workflow_id!r} ended in state {run.state.value}"
            )
        return run.step_results

    def _invoke_skill(
        self, name: str, params: dict[str, Any], ctx: dict[str, Any]
    ) -> Any:
        """Invoke a skill via the injected skill manager."""
        skill = self.skills.get(name)  # type: ignore[union-attr]
        if skill is None:
            raise ExecutorError(f"skill {name!r} not registered")
        return skill(**params)

    def _invoke_provider(
        self,
        task: ExecutionTask,
        resolution: TaskResolution,
        ctx: dict[str, Any],
    ) -> Any:
        """Generate a response via the injected provider manager."""
        prompt = (
            resolution.params.get("prompt")
            or resolution.params.get("goal")
            or task.description
            or task.name
        )
        provider_name = resolution.provider or self.default_provider
        response = self.providers.generate(  # type: ignore[union-attr]
            prompt,
            provider=provider_name,
        )
        # Update token usage + cost estimates.
        usage = getattr(response, "usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        self.token_usage["prompt"] += prompt_tokens
        self.token_usage["completion"] += completion_tokens
        self.token_usage["total"] += prompt_tokens + completion_tokens
        self.estimated_cost += float(usage.get("estimated_cost", 0.0) or 0.0)
        return getattr(response, "text", str(response))

    def _invoke_knowledge(self, params: dict[str, Any], ctx: dict[str, Any]) -> Any:
        """Search the knowledge engine for research tasks."""
        query = params.get("topic") or params.get("query") or params.get("goal") or ""
        results = self.knowledge.search(query)  # type: ignore[union-attr]
        return [
            {
                "content": getattr(r.chunk, "content", str(r)),
                "score": getattr(r, "score", 0.0),
            }
            for r in results
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_generative(task: ExecutionTask, resolution: TaskResolution) -> bool:
        """Return ``True`` if the task looks generative (worth a provider call)."""
        if task.kind.value in ("generate", "research", "review"):
            return True
        return resolution.action in (
            "generate",
            "generate_code",
            "generate_assets",
            "research",
        )

    @staticmethod
    def _is_retryable(policy: RetryPolicy, error: str | None) -> bool:
        """Return ``True`` if ``error`` is retryable under ``policy``."""
        if not policy.retryable_errors:
            return True
        if error is None:
            return True
        return any(
            substr.lower() in error.lower() for substr in policy.retryable_errors
        )

    @staticmethod
    def _dependencies_failed(task: ExecutionTask, context: ExecutionContext) -> bool:
        """Return ``True`` if any of ``task``'s dependencies failed."""
        for dep_id in task.dependencies:
            dep_result = context.results.get(dep_id)
            if dep_result is None:
                continue  # not yet executed
            if dep_result.status is ExecutionStatus.FAILED:
                return True
        return False

    def _record_memory(self, task: ExecutionTask, result: ExecutionResult) -> None:
        """Record the task outcome to memory (if a memory engine is injected)."""
        if self.memory is None:
            return
        try:
            self.memory.remember(
                content={
                    "task_id": task.id,
                    "task_name": task.name,
                    "action": task.action,
                    "status": result.status.value,
                    "output": result.output,
                    "error": result.error,
                },
                source="execution.executor",
                tags=["execution", task.kind.value, result.status.value],
            )
        except Exception as exc:  # noqa: BLE001 — never fail the task over memory
            self.logger.warning("Failed to record memory for task %s: %s", task.id, exc)

    def __repr__(self) -> str:
        return (
            f"<ExecutionExecutor actions={len(self._actions)} "
            f"tool_calls={self.tool_calls} "
            f"tokens={self.token_usage['total']}>"
        )


__all__ = [
    "Action",
    "BaseExecutor",
    "ExecutionExecutor",
    "ExecutorError",
]
