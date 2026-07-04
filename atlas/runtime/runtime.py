"""Atlas Runtime — the execution heart of the Atlas AI Operating System.

The :class:`Runtime` is the single entry point through which the rest of
Atlas submits requests and observes their execution. It owns the
:class:`ExecutionQueue`, :class:`Dispatcher`, :class:`Pipeline`,
:class:`BaseExecutor`, :class:`EventBus`, :class:`HookManager`,
:class:`TelemetryCollector`, :class:`SystemMonitor`,
:class:`RecoveryManager`, and :class:`RuntimeScheduler`. Every
dependency is injectable, with sensible deterministic defaults, so the
runtime can be constructed in one line and exercised end-to-end without
external resources.

Public API surface:

* **Request handling**: :meth:`handle`, :meth:`submit`.
* **Lifecycle**: :meth:`pause`, :meth:`resume`, :meth:`cancel`.
* **Recovery**: :meth:`retry`.
* **Scheduling**: :meth:`register_schedule`, :meth:`tick`.
* **Observability**: :meth:`health`, :meth:`metrics`, :meth:`events`.

The runtime is provider-agnostic, tool-agnostic, agent-agnostic, and
workflow-agnostic: every concrete concern is injected through an
abstract base class. The default configuration uses deterministic
in-memory placeholders so the runtime works out-of-the-box.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.dispatcher import Dispatcher, PipelineFactory
from atlas.runtime.events import (
    EventBus,
    ExecutionCancelled,
    RuntimeEvent,
)
from atlas.runtime.executor import (
    BaseExecutor,
    PlaceholderExecutor,
)
from atlas.runtime.hooks import HookManager
from atlas.runtime.lifecycle import (
    TERMINAL_STATES,
    InvalidRuntimeTransitionError,
    RuntimeState,
    assert_transition,
)
from atlas.runtime.monitor import SystemMonitor
from atlas.runtime.pipeline import (
    Pipeline,
    PipelineContext,
    default_pipeline,
)
from atlas.runtime.queue import ExecutionQueue, ExecutionRequest
from atlas.runtime.recovery import (
    RecoveryManager,
    RecoveryPolicy,
)
from atlas.runtime.scheduler import RuntimeScheduler, ScheduledTask
from atlas.runtime.telemetry import TelemetryCollector


class RuntimeError_(RuntimeError):
    """Raised when the runtime cannot perform the requested operation."""


class Runtime:
    """The execution heart of the Atlas AI Operating System.

    Parameters:
        queue: Execution queue. A new one is created if omitted.
        executor: Step executor. Defaults to :class:`PlaceholderExecutor`.
        bus: Event bus. A new one is created if omitted.
        hooks: Hook manager. A new one is created if omitted.
        telemetry: Telemetry collector. A new one is created if omitted
            and wired to the bus.
        monitor: System monitor. Constructed from ``telemetry`` and
            ``queue`` if omitted.
        recovery: Recovery manager. A new one is created if omitted.
        scheduler: Runtime scheduler. Constructed from ``queue`` if
            omitted.
        pipeline_factory: Callable that produces a fresh
            :class:`Pipeline` for each request. If omitted,
            :func:`default_pipeline` is used with the runtime's executor,
            bus, and hooks.
    """

    def __init__(
        self,
        queue: ExecutionQueue | None = None,
        executor: BaseExecutor | None = None,
        bus: EventBus | None = None,
        hooks: HookManager | None = None,
        telemetry: TelemetryCollector | None = None,
        monitor: SystemMonitor | None = None,
        recovery: RecoveryManager | None = None,
        scheduler: RuntimeScheduler | None = None,
        pipeline_factory: PipelineFactory | None = None,
    ) -> None:
        # NOTE: explicit ``is None`` checks because several dependencies
        # define ``__len__`` and would be falsy when empty.
        self.queue = queue if queue is not None else ExecutionQueue()
        self.bus = bus if bus is not None else EventBus()
        # Wire the bus into the default executor so step events flow
        # through the bus. If the caller supplied an executor, respect
        # its existing bus binding (it may intentionally be None for
        # headless use).
        if executor is None:
            self.executor = PlaceholderExecutor(bus=self.bus)
        else:
            self.executor = executor
        self.hooks = hooks if hooks is not None else HookManager()
        self.telemetry = (
            telemetry if telemetry is not None else TelemetryCollector(self.bus)
        )
        self.monitor = (
            monitor
            if monitor is not None
            else SystemMonitor(self.telemetry, self.queue)
        )
        self.recovery = (
            recovery
            if recovery is not None
            else RecoveryManager(policy=RecoveryPolicy(), bus=self.bus)
        )
        self.scheduler = (
            scheduler if scheduler is not None else RuntimeScheduler(self.queue)
        )
        self.pipeline_factory = (
            pipeline_factory
            if pipeline_factory is not None
            else self._default_pipeline_factory
        )
        self.dispatcher = Dispatcher(
            queue=self.queue,
            pipeline_factory=self.pipeline_factory,
            bus=self.bus,
        )
        self.logger = get_logger("runtime")
        # Live execution state — keyed by execution_id.
        self._live: dict[str, PipelineContext] = {}
        self._paused: set[str] = set()
        self._cancelled: set[str] = set()

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def handle(
        self,
        request: str,
        user: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineContext:
        """Synchronously handle ``request``.

        This is the canonical entry point. The runtime enqueues the
        request and immediately dispatches it, returning the finished
        :class:`PipelineContext`.
        """
        exec_request = ExecutionRequest(
            request=request,
            user=user,
            metadata=dict(metadata or {}),
        )
        self.queue.enqueue(exec_request)
        context = self.dispatcher.dispatch_request(exec_request)
        self._live[context.execution_id] = context
        return context

    def submit(
        self,
        request: str,
        user: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionRequest:
        """Enqueue ``request`` without dispatching it.

        The request will be dispatched when :meth:`drain` is called (or
        when the dispatcher is driven by an external loop).
        """
        exec_request = ExecutionRequest(
            request=request,
            user=user,
            metadata=dict(metadata or {}),
        )
        return self.queue.enqueue(exec_request)

    def drain(self, max_items: int | None = None) -> list[PipelineContext]:
        """Dispatch every pending request."""
        return self.dispatcher.drain(max_items=max_items)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pause(self, execution_id: str) -> PipelineContext:
        """Mark an execution as paused.

        Raises:
            RuntimeError_: If the execution is in a terminal state.
        """
        context = self._get_live(execution_id)
        if context.state in TERMINAL_STATES:
            raise RuntimeError_(
                f"Cannot pause execution in terminal state {context.state.value}"
            )
        try:
            assert_transition(context.state, RuntimeState.PAUSED)
        except InvalidRuntimeTransitionError as exc:
            raise RuntimeError_(str(exc)) from exc
        context.state = RuntimeState.PAUSED
        self._paused.add(execution_id)
        self.logger.info("Paused execution %s", execution_id)
        return context

    def resume(self, execution_id: str) -> PipelineContext:
        """Resume a paused execution.

        Raises:
            RuntimeError_: If the execution is not paused.
        """
        context = self._get_live(execution_id)
        if context.state is not RuntimeState.PAUSED:
            raise RuntimeError_(
                f"Cannot resume execution in state {context.state.value}"
            )
        context.state = RuntimeState.EXECUTING
        self._paused.discard(execution_id)
        self.logger.info("Resumed execution %s", execution_id)
        return context

    def cancel(self, execution_id: str, reason: str = "cancelled") -> PipelineContext:
        """Cancel an execution.

        Raises:
            RuntimeError_: If the execution is already terminal.
        """
        context = self._get_live(execution_id)
        if context.state in TERMINAL_STATES:
            raise RuntimeError_(
                f"Cannot cancel execution in terminal state {context.state.value}"
            )
        context.state = RuntimeState.CANCELLED
        context.error = reason
        context.completed_at = datetime.now(UTC)
        self._cancelled.add(execution_id)
        self.bus.publish(
            ExecutionCancelled(execution_id=execution_id, payload={"reason": reason})
        )
        self.logger.info("Cancelled execution %s: %s", execution_id, reason)
        return context

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def retry(self, execution_id: str) -> PipelineContext:
        """Retry a failed execution by re-running its original request.

        Raises:
            RuntimeError_: If the execution is not in the ``FAILED`` state.
        """
        context = self._get_live(execution_id)
        if context.state is not RuntimeState.FAILED:
            raise RuntimeError_(
                "Cannot retry execution in state "
                f"{context.state.value}; only FAILED can be retried."
            )
        # Reset the context state and re-run through the pipeline.
        context.state = RuntimeState.PENDING
        context.error = None
        context.completed_at = None
        context.started_at = datetime.now(UTC)
        pipeline = self.pipeline_factory(context)
        pipeline.run(context)
        return context

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def register_schedule(self, task: ScheduledTask) -> ScheduledTask:
        """Register a :class:`ScheduledTask` with the runtime scheduler."""
        return self.scheduler.register(task)

    def unregister_schedule(self, task_id: str) -> bool:
        """Remove a schedule by id."""
        return self.scheduler.unregister(task_id)

    def list_schedules(self) -> list[ScheduledTask]:
        """Return every registered schedule."""
        return self.scheduler.all()

    def tick(self, now: datetime | None = None) -> list[PipelineContext]:
        """Fire every due schedule and dispatch the enqueued requests."""
        self.scheduler.tick(now=now)
        return self.drain()

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return the latest health snapshot as a flat dict."""
        return self.monitor.to_dict()

    def metrics(self, execution_id: str) -> Any:
        """Return the :class:`ExecutionMetrics` for ``execution_id``."""
        return self.telemetry.metrics(execution_id)

    def events(self, execution_id: str | None = None) -> list[RuntimeEvent]:
        """Return events from the bus history.

        If ``execution_id`` is supplied, only events for that execution
        are returned.
        """
        if execution_id is None:
            return self.bus.history()
        return self.bus.history_for(execution_id)

    def live_executions(self) -> list[PipelineContext]:
        """Return every execution the runtime is currently tracking."""
        return list(self._live.values())

    def get_execution(self, execution_id: str) -> PipelineContext | None:
        """Return the live :class:`PipelineContext` for ``execution_id``."""
        return self._live.get(execution_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_live(self, execution_id: str) -> PipelineContext:
        context = self._live.get(execution_id)
        if context is None:
            raise RuntimeError_(f"Unknown execution: {execution_id!r}")
        return context

    def _default_pipeline_factory(
        self, context: PipelineContext
    ) -> Pipeline:  # noqa: ARG002
        """Default pipeline factory bound to this runtime's executor."""
        return default_pipeline(
            executor=self.executor,
            bus=self.bus,
            hooks=self.hooks,
        )

    def __repr__(self) -> str:
        return (
            f"<Runtime queue={len(self.queue)} "
            f"live={len(self._live)} schedules={len(self.scheduler)}>"
        )


__all__ = [
    "Runtime",
    "RuntimeError_",
]
