"""Recovery manager for the Atlas Runtime.

The :class:`RecoveryManager` owns the runtime's retry and compensation
strategy. When an execution fails, the runtime hands the failure to the
recovery manager, which decides:

* Whether to retry the execution automatically.
* How long to wait before retrying (exponential backoff).
* Whether to escalate to a compensating action (e.g. fall back to a
  different provider).

The default :class:`RecoveryPolicy` is a simple deterministic policy:
retry up to ``max_retries`` times with exponential backoff. Compensating
actions are left to the caller via the injected ``compensator`` callable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import (
    EventBus,
    ExecutionFailed,
    ExecutionStarted,
    RuntimeEvent,
)


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class RecoveryDecision:
    """The outcome of consulting the recovery manager.

    Attributes:
        action: One of ``"retry"``, ``"compensate"``, ``"abort"``.
        retry: ``True`` if the execution should be retried.
        wait_until: When the retry should be scheduled. ``None`` for
            immediate retry.
        attempt: The attempt number that produced this decision (1-based).
        reason: Human-readable explanation.
        payload: Free-form compensator payload (for ``"compensate"``).
    """

    action: str
    retry: bool = False
    wait_until: datetime | None = None
    attempt: int = 1
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryPolicy:
    """Configuration for the default :class:`RecoveryManager`.

    Attributes:
        max_retries: Maximum number of automatic retries. ``0`` disables
            retry; the manager will always return ``"abort"``.
        base_delay_seconds: Initial backoff delay. Doubled on each retry.
        max_delay_seconds: Cap on the backoff delay.
        retryable_errors: If non-empty, only errors whose message contains
            one of these substrings are retryable. Empty means everything
            is retryable.
    """

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    retryable_errors: tuple[str, ...] = ()


Compensator = Callable[[ExecutionFailed], dict[str, Any] | None]


class RecoveryManager:
    """Owns the runtime's retry and compensation strategy.

    Parameters:
        policy: The :class:`RecoveryPolicy` to apply. Defaults to a fresh
            policy with 3 retries.
        compensator: Optional callable invoked when the decision is
            ``"compensate"``. Receives the failure event and returns a
            payload dict (or ``None``).
        bus: Optional event bus to subscribe to. The manager listens for
            :class:`ExecutionFailed` events and records them so that
            :meth:`decide` can use the latest failure.
    """

    def __init__(
        self,
        policy: RecoveryPolicy | None = None,
        compensator: Compensator | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.policy = policy if policy is not None else RecoveryPolicy()
        self.compensator = compensator
        self.bus = bus
        self.logger = get_logger("runtime.recovery")
        self._attempts: dict[str, int] = {}
        self._last_failure: dict[str, ExecutionFailed] = {}
        self._recovered: dict[str, bool] = {}
        if bus is not None:
            bus.subscribe(RuntimeEvent, self._on_event)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_start(self, execution_id: str) -> None:
        """Record that an execution has started (or restarted after retry)."""
        self._attempts[execution_id] = self._attempts.get(execution_id, 0) + 1
        self._recovered.pop(execution_id, None)

    def decide(self, failure: ExecutionFailed) -> RecoveryDecision:
        """Decide what to do for a failed execution.

        Args:
            failure: The :class:`ExecutionFailed` event describing the
                failure.

        Returns:
            A :class:`RecoveryDecision` describing the next action.
        """
        eid = failure.execution_id
        if eid is None:
            return RecoveryDecision(
                action="abort",
                reason="failure has no execution_id",
                attempt=1,
            )
        self._last_failure[eid] = failure
        attempt = self._attempts.get(eid, 1)

        if not self._is_retryable(failure):
            return RecoveryDecision(
                action="abort",
                attempt=attempt,
                reason="error is not retryable",
            )

        if attempt > self.policy.max_retries:
            # Out of retries — try compensator before aborting.
            if self.compensator is not None:
                payload = self.compensator(failure)
                if payload is not None:
                    self._recovered[eid] = True
                    return RecoveryDecision(
                        action="compensate",
                        attempt=attempt,
                        reason="max_retries_exceeded_compensated",
                        payload=payload,
                    )
            return RecoveryDecision(
                action="abort",
                attempt=attempt,
                reason="max_retries_exceeded",
            )

        delay = min(
            self.policy.base_delay_seconds * (2 ** (attempt - 1)),
            self.policy.max_delay_seconds,
        )
        wait_until = _utcnow() + timedelta(seconds=delay)
        return RecoveryDecision(
            action="retry",
            retry=True,
            wait_until=wait_until,
            attempt=attempt,
            reason=f"retrying_after_backoff_{delay:.1f}s",
        )

    def mark_recovered(self, execution_id: str) -> None:
        """Mark that an execution has succeeded after retries."""
        self._recovered[execution_id] = True

    def attempts(self, execution_id: str) -> int:
        """Return the number of attempts made for ``execution_id``."""
        return self._attempts.get(execution_id, 0)

    def last_failure(self, execution_id: str) -> ExecutionFailed | None:
        """Return the most recent :class:`ExecutionFailed` for ``execution_id``."""
        return self._last_failure.get(execution_id)

    def recovered(self, execution_id: str) -> bool:
        """Return ``True`` if ``execution_id`` succeeded after retries."""
        return self._recovered.get(execution_id, False)

    def reset(self) -> None:
        """Drop all internal state."""
        self._attempts.clear()
        self._last_failure.clear()
        self._recovered.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_retryable(self, failure: ExecutionFailed) -> bool:
        if not self.policy.retryable_errors:
            return True
        return any(
            substr.lower() in (failure.error or "").lower()
            for substr in self.policy.retryable_errors
        )

    def _on_event(self, event: RuntimeEvent) -> None:
        """Event-bus listener that records starts and failures."""
        if isinstance(event, ExecutionStarted):
            if event.execution_id is not None:
                self.record_start(event.execution_id)
        elif isinstance(event, ExecutionFailed):
            self.decide(event)

    def __repr__(self) -> str:
        return (
            f"<RecoveryManager policy={self.policy} " f"tracked={len(self._attempts)}>"
        )


__all__ = [
    "Compensator",
    "RecoveryDecision",
    "RecoveryManager",
    "RecoveryPolicy",
]
