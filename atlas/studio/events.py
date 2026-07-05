"""Event relay — bridges the LiveEventBus to Studio UI callbacks.

The :class:`EventRelay` subscribes to a :class:`~atlas.live.event_bus.LiveEventBus`
on the wildcard topic (``"*"``) so it sees every published runtime event.
Each event is converted to an :class:`~atlas.studio.models.EventEntry`
and stored in a fixed-size ring buffer. Studio UI components register
plain-Python callbacks via :meth:`subscribe` and are notified in
registration order.

The relay has **no Qt dependency** — callbacks are ordinary callables,
which makes the class testable in a headless environment.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from atlas.studio.models.studio_models import EventEntry

if TYPE_CHECKING:
    from atlas.live.event_bus import LiveEventBus


#: Type alias for a relay callback: receives an :class:`EventEntry`.
EventCallback = Callable[[EventEntry], None]

#: Maximum number of events retained in the ring buffer.
DEFAULT_HISTORY_SIZE: int = 1000


class EventRelay:
    """Relay runtime events to Studio UI callbacks.

    Parameters:
        history_size: Maximum number of :class:`EventEntry` items to
            retain. Older events are evicted from the ring buffer.
    """

    def __init__(self, history_size: int = DEFAULT_HISTORY_SIZE) -> None:
        self._buffer: deque[EventEntry] = deque(maxlen=history_size)
        self._callbacks: list[EventCallback] = []
        self._bus: LiveEventBus | None = None
        self._listener: Callable[[Any], None] | None = None
        self._running: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, bus: LiveEventBus) -> EventRelay:
        """Subscribe the relay to ``bus`` on the wildcard topic.

        Calling :meth:`start` while already running first calls
        :meth:`stop` to avoid double subscription. Returns ``self`` for
        chaining.
        """
        if self._running:
            self.stop()
        self._bus = bus
        self._listener = self._on_event
        bus.subscribe("*", self._listener)
        self._running = True
        return self

    def stop(self) -> EventRelay:
        """Unsubscribe the relay from its bus (if any)."""
        if self._bus is not None and self._listener is not None:
            try:
                self._bus.bus.unsubscribe("*", self._listener)
            except Exception:  # noqa: BLE001 — be tolerant on teardown
                pass
        self._bus = None
        self._listener = None
        self._running = False
        return self

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, callback: EventCallback) -> EventRelay:
        """Register ``callback`` to be invoked for every relayed event.

        Callbacks are invoked in registration order. A raising callback
        is logged and skipped (it does not stop dispatch to the others).
        Returns ``self`` for chaining.
        """
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callbacks.append(callback)
        return self

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self, limit: int = 100) -> list[EventEntry]:
        """Return up to ``limit`` most recent events (newest last)."""
        if limit <= 0:
            return []
        items = list(self._buffer)
        return items[-limit:]

    def recent_events(self, limit: int = 100) -> list[EventEntry]:
        """Alias for :meth:`history` — newest events last."""
        return self.history(limit=limit)

    def clear(self) -> EventRelay:
        """Empty the ring buffer. Returns ``self`` for chaining."""
        self._buffer.clear()
        return self

    @property
    def running(self) -> bool:
        """Whether the relay is currently subscribed to a bus."""
        return self._running

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return f"<EventRelay running={self._running} buffered={len(self._buffer)}>"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_event(self, event: Any) -> None:
        """Convert a runtime event to an :class:`EventEntry` and dispatch."""
        entry = self._to_entry(event)
        self._buffer.append(entry)
        for callback in list(self._callbacks):
            try:
                callback(entry)
            except Exception:  # noqa: BLE001 — isolate callbacks
                # A misbehaving callback must not break the relay.
                pass

    @staticmethod
    def _to_entry(event: Any) -> EventEntry:
        """Convert an arbitrary runtime event into an :class:`EventEntry`."""
        event_type = type(event).__name__
        timestamp = getattr(event, "timestamp", None)
        if timestamp is None:
            from datetime import UTC, datetime

            timestamp = datetime.now(UTC)
        # Build a serialisable payload from the event's dataclass fields.
        data: dict[str, Any] = {}
        if dataclasses.is_dataclass(event):
            for field_obj in dataclasses.fields(event):
                try:
                    data[field_obj.name] = _serialise(getattr(event, field_obj.name))
                except Exception:  # noqa: BLE001 — skip unserialisable fields
                    data[field_obj.name] = "<unserialisable>"
        else:
            data["payload"] = _serialise(getattr(event, "payload", None))
        source = (
            data.get("source") or data.get("provider") or data.get("connector") or ""
        )
        if not isinstance(source, str):
            source = str(source)
        return EventEntry(
            type=event_type, source=source, timestamp=timestamp, data=data
        )


def _serialise(value: Any) -> Any:
    """Best-effort conversion of a value to a JSON-friendly form."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple | set):
        return [_serialise(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialise(val) for key, val in value.items()}
    if dataclasses.is_dataclass(value):
        return {
            field_obj.name: _serialise(getattr(value, field_obj.name))
            for field_obj in dataclasses.fields(value)
        }
    return str(value)


__all__ = ["DEFAULT_HISTORY_SIZE", "EventCallback", "EventRelay"]
