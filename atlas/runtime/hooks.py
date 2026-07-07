"""Pre/post execution hooks for the Atlas Runtime.

Hooks are user-supplied callables that run *around* runtime phases. Unlike
event-bus listeners (which are passive observers), hooks can short-circuit
the pipeline: a ``before`` hook may return a non-``None`` value to skip the
phase and use that value as the phase's result, and any hook may raise a
:class:`HookAbort` exception to abort the entire execution.

Supported hook points (in execution order):

* ``before_planning`` / ``after_planning``
* ``before_dispatch`` / ``after_dispatch``
* ``before_execute`` / ``after_execute``
* ``before_review`` / ``after_review``
* ``before_complete`` / ``after_complete``
* ``on_failure`` / ``on_cancel``

The :class:`HookManager` registers and dispatches hooks. It is the single
point through which the runtime invokes hooks; phases never call user code
directly.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from atlas.core.logger import get_logger
from atlas.runtime.events import RuntimeEvent


class HookAbort(RuntimeError):
    """Raised by a hook to abort the execution immediately."""

    def __init__(self, reason: str = "hook_abort", result: Any = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.result = result


#: Hook phase identifiers. Kept as plain strings so external code can
#: register against them without importing symbols.
BEFORE_PLANNING = "before_planning"
AFTER_PLANNING = "after_planning"
BEFORE_DISPATCH = "before_dispatch"
AFTER_DISPATCH = "after_dispatch"
BEFORE_EXECUTE = "before_execute"
AFTER_EXECUTE = "after_execute"
BEFORE_REVIEW = "before_review"
AFTER_REVIEW = "after_review"
BEFORE_COMPLETE = "before_complete"
AFTER_COMPLETE = "after_complete"
ON_FAILURE = "on_failure"
ON_CANCEL = "on_cancel"

ALL_PHASES: tuple[str, ...] = (
    BEFORE_PLANNING,
    AFTER_PLANNING,
    BEFORE_DISPATCH,
    AFTER_DISPATCH,
    BEFORE_EXECUTE,
    AFTER_EXECUTE,
    BEFORE_REVIEW,
    AFTER_REVIEW,
    BEFORE_COMPLETE,
    AFTER_COMPLETE,
    ON_FAILURE,
    ON_CANCEL,
)

#: A hook is a callable that receives the current context dict and an
#: optional event payload. It may return ``None`` (continue normally), a
#: non-``None`` value (for ``before_*`` phases only — short-circuits the
#: phase), or raise :class:`HookAbort`.
Hook = Callable[..., Any]


@dataclass
class HookRegistration:
    """A registered hook and the phase it applies to.

    Attributes:
        phase: One of the ``ALL_PHASES`` constants.
        hook: The callable to invoke.
        priority: Lower numbers run first. Defaults to ``0``.
        name: Optional human-readable label for diagnostics.
    """

    phase: str
    hook: Hook
    priority: int = 0
    name: str = ""


class HookManager:
    """Registry and dispatcher for runtime hooks.

    Hooks are grouped by phase and invoked in priority order (ascending).
    A ``before_*`` hook that returns a non-``None`` value short-circuits
    the corresponding phase and the value is used as the phase's result.
    Any hook that raises :class:`HookAbort` aborts the runtime.
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookRegistration]] = {
            phase: [] for phase in ALL_PHASES
        }
        self.logger = get_logger("runtime.hooks")

    def register(
        self,
        phase: str,
        hook: Hook,
        priority: int = 0,
        name: str = "",
    ) -> HookRegistration:
        """Register ``hook`` to run at ``phase``.

        Raises:
            ValueError: If ``phase`` is not a known phase.
            TypeError: If ``hook`` is not callable.
        """
        if phase not in self._hooks:
            raise ValueError(f"Unknown hook phase: {phase!r}")
        if not callable(hook):
            raise TypeError("hook must be callable")
        registration = HookRegistration(
            phase=phase, hook=hook, priority=priority, name=name
        )
        self._hooks[phase].append(registration)
        # Keep stable order by (priority, registration order).
        self._hooks[phase].sort(key=lambda r: r.priority)
        return registration

    def unregister(self, registration: HookRegistration) -> bool:
        """Remove a previously-registered hook. Return ``True`` if removed."""
        bucket = self._hooks.get(registration.phase, [])
        try:
            bucket.remove(registration)
        except ValueError:
            return False
        return True

    def hooks_for(self, phase: str) -> list[HookRegistration]:
        """Return every hook registered for ``phase`` (in invocation order)."""
        return list(self._hooks.get(phase, []))

    def clear(self, phase: str | None = None) -> None:
        """Drop hooks. If ``phase`` is given, only that phase is cleared."""
        if phase is None:
            for key in list(self._hooks):
                self._hooks[key] = []
        else:
            if phase in self._hooks:
                self._hooks[phase] = []

    def run(
        self,
        phase: str,
        context: dict[str, Any] | None = None,
        event: RuntimeEvent | None = None,
    ) -> Any:
        """Run every hook at ``phase`` in order.

        Returns the first non-``None`` value returned by a ``before_*``
        hook, or ``None`` if every hook returned ``None``. ``after_*`` and
        ``on_*`` hooks' return values are ignored.

        Raises:
            HookAbort: If any hook raises :class:`HookAbort`.
        """
        ctx = context if context is not None else {}
        short_circuit: Any = None
        for registration in self.hooks_for(phase):
            try:
                result = registration.hook(ctx, event)
            except HookAbort:
                raise
            except Exception as exc:  # noqa: BLE001 — isolate hooks
                self.logger.warning(
                    "Hook %s at phase %s raised: %s",
                    registration.name or registration.hook.__name__,
                    phase,
                    exc,
                )
                continue
            if phase.startswith("before_") and result is not None:
                short_circuit = result
                self.logger.debug(
                    "Hook %s short-circuited phase %s",
                    registration.name or registration.hook.__name__,
                    phase,
                )
                break
        return short_circuit

    def hook_count(self, phase: str | None = None) -> int:
        """Return the number of registered hooks."""
        if phase is None:
            return sum(len(v) for v in self._hooks.values())
        return len(self._hooks.get(phase, []))

    def phases(self) -> Iterable[str]:
        """Return every phase that has at least one hook."""
        return tuple(p for p, bucket in self._hooks.items() if bucket)

    def __repr__(self) -> str:
        return f"<HookManager hooks={self.hook_count()}>"


__all__ = [
    "AFTER_COMPLETE",
    "AFTER_DISPATCH",
    "AFTER_EXECUTE",
    "AFTER_PLANNING",
    "AFTER_REVIEW",
    "ALL_PHASES",
    "BEFORE_COMPLETE",
    "BEFORE_DISPATCH",
    "BEFORE_EXECUTE",
    "BEFORE_PLANNING",
    "BEFORE_REVIEW",
    "Hook",
    "HookAbort",
    "HookManager",
    "HookRegistration",
    "ON_CANCEL",
    "ON_FAILURE",
]
