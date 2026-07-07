"""In-process execution queue for the Atlas Runtime.

The :class:`ExecutionQueue` is a FIFO buffer of pending execution
requests. The runtime enqueues requests as they arrive and the dispatcher
dequeues them for processing. The queue is in-process and synchronous;
for cross-process coordination, wrap it in a concrete adapter that
forwards to Redis / Celery / etc.

A queue item is a :class:`ExecutionRequest` — an immutable bundle of the
user request, the requesting user, the priority, and arbitrary metadata.
Items are dequeued in priority order (higher first) and submission order
within the same priority.
"""

from __future__ import annotations

import dataclasses
import heapq
import itertools
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class ExecutionRequest:
    """An immutable request submitted to the runtime.

    Attributes:
        request: The raw user request string.
        user: Optional identifier for the operator issuing the request.
        priority: Higher numbers run first. Defaults to ``0``.
        metadata: Free-form metadata propagated through the pipeline.
        submitted_at: When the request was enqueued.
        id: Unique identifier for this request.
    """

    request: str
    user: str | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    submitted_at: datetime = field(default_factory=_utcnow)
    id: int = 0

    def with_id(self, request_id: int) -> ExecutionRequest:
        """Return a copy of this request with ``id`` set."""
        return dataclasses.replace(self, id=request_id)


class ExecutionQueue:
    """Priority-ordered FIFO queue of :class:`ExecutionRequest` items.

    Items are dequeued in priority order (higher first). Within the same
    priority, items are dequeued in submission order (FIFO).
    """

    def __init__(self, capacity: int = 0) -> None:
        """Construct a new queue.

        Args:
            capacity: Maximum number of items. ``0`` means unbounded.
                When the capacity is reached, :meth:`enqueue` raises
                :class:`QueueFullError`.
        """
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        self.capacity = capacity
        self._counter = itertools.count(1)
        # Heap items: (-priority, sequence, request). We negate priority
        # so that higher priority bubbles to the top of the min-heap.
        self._heap: list[tuple[int, int, ExecutionRequest]] = []
        self._size = 0
        self.logger = get_logger("runtime.queue")

    def enqueue(self, request: ExecutionRequest) -> ExecutionRequest:
        """Add ``request`` to the queue.

        Returns the request with ``id`` assigned.

        Raises:
            QueueFullError: If the queue has a non-zero capacity and is full.
        """
        if self.capacity and self._size >= self.capacity:
            raise QueueFullError(f"Queue is full (capacity={self.capacity})")
        request_id = next(self._counter)
        request = request.with_id(request_id)
        # Sequence breaks priority ties in FIFO order.
        seq = request_id
        heapq.heappush(self._heap, (-request.priority, seq, request))
        self._size += 1
        self.logger.debug(
            "Enqueued request %d (priority=%d): %s",
            request_id,
            request.priority,
            request.request[:60],
        )
        return request

    def dequeue(self) -> ExecutionRequest | None:
        """Remove and return the highest-priority request, or ``None`` if empty."""
        if not self._heap:
            return None
        _, _, request = heapq.heappop(self._heap)
        self._size -= 1
        self.logger.debug("Dequeued request %d", request.id)
        return request

    def peek(self) -> ExecutionRequest | None:
        """Return the highest-priority request without removing it."""
        if not self._heap:
            return None
        return self._heap[0][2]

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __iter__(self) -> Iterator[ExecutionRequest]:
        # Iterate in priority order without mutating the heap.
        return iter(
            request
            for _, _, request in sorted(self._heap, key=lambda item: (item[0], item[1]))
        )

    def clear(self) -> None:
        """Drop every pending request."""
        self._heap.clear()
        self._size = 0

    def __repr__(self) -> str:
        return (
            f"<ExecutionQueue size={self._size} "
            f"capacity={self.capacity or 'unbounded'}>"
        )


class QueueFullError(RuntimeError):
    """Raised when :meth:`ExecutionQueue.enqueue` is called on a full queue."""


__all__ = [
    "ExecutionQueue",
    "ExecutionRequest",
    "QueueFullError",
]
