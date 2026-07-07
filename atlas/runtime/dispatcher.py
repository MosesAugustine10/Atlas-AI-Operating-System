"""Runtime dispatcher — selects the pipeline / executor / handler for a request.

The :class:`Dispatcher` sits between the :class:`ExecutionQueue` and the
:class:`Pipeline`. It pulls :class:`ExecutionRequest` items off the queue,
turns each into a :class:`PipelineContext`, hands the context to a
:class:`Pipeline`, and returns the finished context to the caller.

The dispatcher is intentionally thin: it knows nothing about agents,
providers, tools, or workflows. Those concerns are injected via the
``pipeline_factory`` callable, which maps a :class:`PipelineContext` to a
:class:`Pipeline`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import EventBus, RequestReceived, SessionOpened
from atlas.runtime.pipeline import Pipeline, PipelineContext
from atlas.runtime.queue import ExecutionQueue, ExecutionRequest

PipelineFactory = Callable[[PipelineContext], Pipeline]


class Dispatcher:
    """Pulls requests off the queue and runs them through a pipeline.

    Parameters:
        queue: The :class:`ExecutionQueue` to pull from.
        pipeline_factory: Callable that produces a fresh :class:`Pipeline`
            for each request. Required — the dispatcher does not assume a
            default pipeline.
        bus: Optional event bus for emitting :class:`RequestReceived` and
            :class:`SessionOpened` events.
    """

    def __init__(
        self,
        queue: ExecutionQueue,
        pipeline_factory: PipelineFactory,
        bus: EventBus | None = None,
    ) -> None:
        self.queue = queue
        self.pipeline_factory = pipeline_factory
        self.bus = bus
        self.logger = get_logger("runtime.dispatcher")
        self._processed: int = 0
        self._failed: int = 0

    def dispatch_one(self) -> PipelineContext | None:
        """Pull the next request and run it through its pipeline.

        Returns the finished :class:`PipelineContext`, or ``None`` if the
        queue was empty.
        """
        request = self.queue.dequeue()
        if request is None:
            return None
        return self.dispatch_request(request)

    def dispatch_request(self, request: ExecutionRequest) -> PipelineContext:
        """Run a single :class:`ExecutionRequest` through its pipeline.

        This is the canonical entry point used by both :meth:`dispatch_one`
        and the runtime's synchronous :meth:`Runtime.handle` method.
        """
        self._emit(
            RequestReceived(
                execution_id=None,
                request=request.request,
                payload={"user": request.user, "priority": request.priority},
            )
        )
        context = PipelineContext(
            request=request.request,
            user=request.user,
            metadata=dict(request.metadata),
        )
        self._emit(SessionOpened(execution_id=context.execution_id))
        pipeline = self.pipeline_factory(context)
        pipeline.run(context)
        self._processed += 1
        if context.state.value == "failed":
            self._failed += 1
        self.logger.info(
            "Dispatched execution %s -> %s",
            context.execution_id,
            context.state.value,
        )
        return context

    def drain(self, max_items: int | None = None) -> list[PipelineContext]:
        """Pull and dispatch every pending request.

        Args:
            max_items: Maximum number of requests to process. ``None``
                means drain the queue entirely.
        """
        results: list[PipelineContext] = []
        while True:
            if max_items is not None and len(results) >= max_items:
                break
            context = self.dispatch_one()
            if context is None:
                break
            results.append(context)
        return results

    @property
    def processed_count(self) -> int:
        """Total number of requests that have been dispatched."""
        return self._processed

    @property
    def failed_count(self) -> int:
        """Number of dispatched requests that ended in ``failed`` state."""
        return self._failed

    def reset_counters(self) -> None:
        """Reset processed / failed counters."""
        self._processed = 0
        self._failed = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event: Any) -> None:
        if self.bus is not None:
            self.bus.publish(event)

    def __repr__(self) -> str:
        return (
            f"<Dispatcher processed={self._processed} "
            f"failed={self._failed} queue={len(self.queue)}>"
        )


__all__ = ["Dispatcher", "PipelineFactory"]
