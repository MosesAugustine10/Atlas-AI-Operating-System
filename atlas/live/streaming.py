"""Streaming — real-time progress updates during execution.

The :class:`StreamManager` provides a simple API for emitting progress
updates during execution. Each update is published as a
:class:`StreamProgress` event on the :class:`LiveEventBus` and can be
consumed by WebSocket clients (dashboard) or logged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from atlas.core.logger import get_logger
from atlas.live.event_bus import LiveEventBus


class StreamManager:
    """Manages streaming progress updates.

    Parameters:
        event_bus: The :class:`LiveEventBus` to publish progress on.
    """

    def __init__(self, event_bus: LiveEventBus | None = None) -> None:
        self.event_bus = event_bus if event_bus is not None else LiveEventBus()
        self.logger = get_logger("live.streaming")
        self._listeners: list[Callable[[str, str, float], None]] = []
        self._stages: list[tuple[str, str, float]] = []

    def progress(
        self,
        stage: str,
        message: str = "",
        progress: float = 0.0,
    ) -> None:
        """Emit a progress update.

        Args:
            stage: The execution stage (e.g. ``"planning"``,
                ``"researching"``, ``"writing code"``).
            message: Optional human-readable message.
            progress: 0.0 - 1.0 progress indicator.
        """
        self._stages.append((stage, message, progress))
        self.event_bus.emit_stream_progress(stage, message, progress)
        for listener in self._listeners:
            try:
                listener(stage, message, progress)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Stream listener raised: %s", exc)
        self.logger.info("Progress: %s — %s (%.0f%%)", stage, message, progress * 100)

    def subscribe(self, listener: Callable[[str, str, float], None]) -> None:
        """Subscribe a listener that receives ``(stage, message, progress)``."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, str, float], None]) -> bool:
        """Remove a listener. Return ``True`` if it was registered."""
        try:
            self._listeners.remove(listener)
            return True
        except ValueError:
            return False

    @contextmanager
    def stage(self, name: str, message: str = "") -> Iterator[StreamManager]:
        """Context manager that emits start/end progress for a stage.

        Usage::

            with stream.stage("researching", "Searching the web..."):
                # do research
                pass
        """
        self.progress(name, message, 0.0)
        try:
            yield self
        finally:
            self.progress(name, f"{name} done", 1.0)

    def stages(self) -> list[tuple[str, str, float]]:
        """Return every emitted stage as ``(stage, message, progress)``."""
        return list(self._stages)

    def clear(self) -> None:
        """Clear recorded stages and listeners."""
        self._stages.clear()
        self._listeners.clear()

    def __len__(self) -> int:
        return len(self._stages)

    def __repr__(self) -> str:
        return f"<StreamManager stages={len(self._stages)}>"


def default_progress_stages() -> list[str]:
    """Return the default execution progress stages."""
    return [
        "understanding",
        "searching knowledge",
        "recalling memory",
        "reasoning",
        "planning",
        "choosing agents",
        "choosing providers",
        "choosing tools",
        "executing",
        "reviewing",
        "reflecting",
        "learning",
        "updating memory",
        "done",
    ]


__all__ = ["StreamManager", "default_progress_stages"]
