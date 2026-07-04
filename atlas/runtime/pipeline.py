"""Runtime pipeline — the ordered stages of a single execution.

The :class:`Pipeline` is the runtime's analog of the kernel's
``Planner -> Router -> Agent -> Tool Manager`` chain. It is composed of
:class:`PipelineStage` callables, each of which receives the current
:class:`PipelineContext` and may mutate it. The pipeline runs the stages
in order, emitting lifecycle events at each boundary.

Default stages (in execution order):

1. :class:`PlanningStage` — decomposes the request into an
   :class:`ExecutionPlan`.
2. :class:`DispatchStage` — selects agents / providers / tools (no-op by
   default; populated by injection).
3. :class:`ExecutionStage` — runs the plan via the
   :class:`BaseExecutor`.
4. :class:`ReviewStage` — runs reflection / post-execution review.
5. :class:`CompleteStage` — assembles the final response.

Each stage is a small, replaceable callable. The pipeline never reaches
into global state; every dependency is injected via the
:class:`PipelineContext`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import (
    DispatchCompleted,
    DispatchStarted,
    EventBus,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
    PlanningCompleted,
    PlanningStarted,
    ReviewCompleted,
    ReviewStarted,
)
from atlas.runtime.executor import (
    BaseExecutor,
    ExecutionOutcome,
    ExecutionPlan,
    ExecutionStep,
)
from atlas.runtime.hooks import HookAbort, HookManager
from atlas.runtime.lifecycle import RuntimeState


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "exec") -> str:
    """Generate a new opaque identifier with the given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class PipelineContext:
    """Mutable state carried through every stage of the pipeline.

    Attributes:
        execution_id: Unique identifier for this execution.
        request: The original user request.
        user: Optional operator identifier.
        plan: The :class:`ExecutionPlan` produced by the planning stage.
        outcome: The :class:`ExecutionOutcome` produced by the execution
            stage.
        response: The final response returned to the caller.
        state: The current :class:`RuntimeState`.
        artifacts: Free-form bag for stages to exchange data.
        metadata: Free-form runtime metadata.
        error: Set when an error is raised.
        started_at: When the pipeline started.
        completed_at: When the pipeline reached a terminal state.
    """

    execution_id: str = field(default_factory=lambda: _new_id("exec"))
    request: str = ""
    user: str | None = None
    plan: ExecutionPlan | None = None
    outcome: ExecutionOutcome | None = None
    response: Any = None
    state: RuntimeState = RuntimeState.PENDING
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None

    def is_terminal(self) -> bool:
        """Return ``True`` if the pipeline is in a terminal state."""
        return self.state in (
            RuntimeState.COMPLETED,
            RuntimeState.FAILED,
            RuntimeState.CANCELLED,
        )


Stage = Callable[[PipelineContext], None]


class Pipeline:
    """Ordered sequence of :class:`Stage` callables driven by the runtime.

    Parameters:
        stages: Ordered list of stages to run.
        bus: Optional event bus to publish lifecycle events.
        hooks: Optional hook manager. If supplied, hooks are run around
            every stage.
    """

    def __init__(
        self,
        stages: list[Stage] | None = None,
        bus: EventBus | None = None,
        hooks: HookManager | None = None,
    ) -> None:
        self.stages: list[Stage] = list(stages or [])
        self.bus = bus
        self.hooks = hooks if hooks is not None else HookManager()
        self.logger = get_logger("runtime.pipeline")

    def add_stage(self, stage: Stage) -> Pipeline:
        """Append ``stage`` to the pipeline. Returns self for chaining."""
        self.stages.append(stage)
        return self

    def run(self, context: PipelineContext) -> PipelineContext:
        """Run every stage in order against ``context``.

        Stages run sequentially. A stage may set ``context.error`` and
        return early to short-circuit; the pipeline then publishes an
        :class:`ExecutionFailed` event and returns. Hooks may also
        short-circuit by raising :class:`HookAbort`.
        """
        self._emit(ExecutionStarted(execution_id=context.execution_id))
        context.state = RuntimeState.EXECUTING
        for stage in self.stages:
            stage_name = getattr(stage, "__name__", repr(stage))
            try:
                self.hooks.run(
                    "before_execute",
                    context={
                        "stage": stage_name,
                        "execution_id": context.execution_id,
                    },
                )
            except HookAbort as abort:
                context.error = abort.reason
                context.state = RuntimeState.FAILED
                self._emit(
                    ExecutionFailed(
                        execution_id=context.execution_id,
                        error=abort.reason,
                    )
                )
                context.completed_at = _utcnow()
                return context

            try:
                stage(context)
            except Exception as exc:  # noqa: BLE001 — capture all stage errors
                context.error = f"{type(exc).__name__}: {exc}"
                context.state = RuntimeState.FAILED
                self._emit(
                    ExecutionFailed(
                        execution_id=context.execution_id,
                        error=context.error or "",
                    )
                )
                context.completed_at = _utcnow()
                return context

            if context.error is not None:
                context.state = RuntimeState.FAILED
                self._emit(
                    ExecutionFailed(
                        execution_id=context.execution_id,
                        error=context.error,
                    )
                )
                context.completed_at = _utcnow()
                return context

            try:
                self.hooks.run(
                    "after_execute",
                    context={
                        "stage": stage_name,
                        "execution_id": context.execution_id,
                    },
                )
            except HookAbort as abort:
                context.error = abort.reason
                context.state = RuntimeState.FAILED
                self._emit(
                    ExecutionFailed(
                        execution_id=context.execution_id,
                        error=abort.reason,
                    )
                )
                context.completed_at = _utcnow()
                return context

        context.state = RuntimeState.COMPLETED
        context.completed_at = _utcnow()
        self._emit(
            ExecutionCompleted(
                execution_id=context.execution_id,
                response=context.response,
            )
        )
        return context

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event: Any) -> None:
        """Publish ``event`` on the bus (if one is attached)."""
        if self.bus is not None:
            self.bus.publish(event)

    def __repr__(self) -> str:
        return f"<Pipeline stages={len(self.stages)}>"


# ---------------------------------------------------------------------------
# Default stages
# ---------------------------------------------------------------------------


class PlanningStage:
    """Decomposes the request into an :class:`ExecutionPlan`.

    Parameters:
        planner: Optional callable that maps ``(request, context)`` to an
            :class:`ExecutionPlan`. If omitted, a deterministic planner
            is used that produces a single ``noop`` step carrying the
            request as a param.
        bus: Optional event bus for emitting :class:`PlanningStarted` /
            :class:`PlanningCompleted` events.
    """

    def __init__(
        self,
        planner: Callable[[str, PipelineContext], ExecutionPlan] | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.planner = planner if planner is not None else _default_planner
        self.bus = bus
        self.logger = get_logger("runtime.pipeline.planning")

    def __call__(self, context: PipelineContext) -> None:
        if self.bus is not None:
            self.bus.publish(PlanningStarted(execution_id=context.execution_id))
        context.state = RuntimeState.PLANNING
        plan = self.planner(context.request, context)
        context.plan = plan
        context.state = RuntimeState.DISPATCHING
        if self.bus is not None:
            self.bus.publish(
                PlanningCompleted(
                    execution_id=context.execution_id,
                    task_count=len(plan.steps),
                )
            )


class DispatchStage:
    """Selects agents / providers / tools.

    The default dispatcher is a no-op: it simply advances the state to
    :attr:`RuntimeState.EXECUTING`. Inject a custom ``dispatcher``
    callable to populate ``context.artifacts`` with selected agents,
    providers, and tools.
    """

    def __init__(
        self,
        dispatcher: Callable[[PipelineContext], None] | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.dispatcher = dispatcher if dispatcher is not None else _default_dispatcher
        self.bus = bus
        self.logger = get_logger("runtime.pipeline.dispatch")

    def __call__(self, context: PipelineContext) -> None:
        if self.bus is not None:
            self.bus.publish(DispatchStarted(execution_id=context.execution_id))
        context.state = RuntimeState.DISPATCHING
        self.dispatcher(context)
        context.state = RuntimeState.EXECUTING
        if self.bus is not None:
            self.bus.publish(DispatchCompleted(execution_id=context.execution_id))


class ExecutionStage:
    """Runs the planned :class:`ExecutionPlan` via the executor.

    Parameters:
        executor: The :class:`BaseExecutor` to dispatch to.
        bus: Optional event bus.
    """

    def __init__(
        self,
        executor: BaseExecutor,
        bus: EventBus | None = None,
    ) -> None:
        self.executor = executor
        self.bus = bus
        self.logger = get_logger("runtime.pipeline.execution")

    def __call__(self, context: PipelineContext) -> None:
        if context.plan is None:
            context.error = "no execution plan"
            return
        context.state = RuntimeState.EXECUTING
        outcome = self.executor.execute_plan(
            context.plan,
            execution_id=context.execution_id,
            context=dict(context.artifacts),
        )
        context.outcome = outcome
        if not outcome.success:
            context.error = outcome.error or "execution failed"


class ReviewStage:
    """Runs post-execution review / reflection.

    The default reviewer is a no-op: it simply advances the state to
    :attr:`RuntimeState.REVIEWING` and then back to
    :attr:`RuntimeState.EXECUTING` for the completion stage. Inject a
    custom ``reviewer`` callable to perform reflection.
    """

    def __init__(
        self,
        reviewer: Callable[[PipelineContext], None] | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.reviewer = reviewer if reviewer is not None else _default_reviewer
        self.bus = bus
        self.logger = get_logger("runtime.pipeline.review")

    def __call__(self, context: PipelineContext) -> None:
        if self.bus is not None:
            self.bus.publish(ReviewStarted(execution_id=context.execution_id))
        context.state = RuntimeState.REVIEWING
        self.reviewer(context)
        if self.bus is not None:
            self.bus.publish(ReviewCompleted(execution_id=context.execution_id))


class CompleteStage:
    """Assembles the final response from the execution outcome.

    Parameters:
        assembler: Optional callable that maps the
            :class:`PipelineContext` to a response. If omitted, the
            ``final_output`` of the execution outcome is used.
    """

    def __init__(
        self,
        assembler: Callable[[PipelineContext], Any] | None = None,
    ) -> None:
        self.assembler = assembler if assembler is not None else _default_assembler
        self.logger = get_logger("runtime.pipeline.complete")

    def __call__(self, context: PipelineContext) -> None:
        context.response = self.assembler(context)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def _default_planner(
    request: str, context: PipelineContext
) -> ExecutionPlan:  # noqa: ARG001
    """Produce a single-step plan that carries the request as a param."""
    return ExecutionPlan(
        steps=[
            ExecutionStep(
                id="plan",
                action="noop",
                params={"request": request},
            )
        ],
        inputs={"request": request},
    )


def _default_dispatcher(context: PipelineContext) -> None:
    """No-op dispatcher: simply record that dispatch occurred."""
    context.artifacts["dispatched"] = True


def _default_reviewer(context: PipelineContext) -> None:
    """No-op reviewer: simply record that review occurred."""
    context.artifacts["reviewed"] = True


def _default_assembler(context: PipelineContext) -> Any:
    """Use the execution outcome's final output as the response."""
    if context.outcome is not None:
        return context.outcome.final_output
    return None


def default_pipeline(
    executor: BaseExecutor,
    bus: EventBus | None = None,
    hooks: HookManager | None = None,
    planner: Callable[[str, PipelineContext], ExecutionPlan] | None = None,
    dispatcher: Callable[[PipelineContext], None] | None = None,
    reviewer: Callable[[PipelineContext], None] | None = None,
    assembler: Callable[[PipelineContext], Any] | None = None,
) -> Pipeline:
    """Assemble the default :class:`Pipeline` from the supplied components."""
    return Pipeline(
        stages=[
            PlanningStage(planner=planner, bus=bus),
            DispatchStage(dispatcher=dispatcher, bus=bus),
            ExecutionStage(executor=executor, bus=bus),
            ReviewStage(reviewer=reviewer, bus=bus),
            CompleteStage(assembler=assembler),
        ],
        bus=bus,
        hooks=hooks,
    )


__all__ = [
    "CompleteStage",
    "DispatchStage",
    "ExecutionStage",
    "Pipeline",
    "PipelineContext",
    "PlanningStage",
    "ReviewStage",
    "Stage",
    "default_pipeline",
]
