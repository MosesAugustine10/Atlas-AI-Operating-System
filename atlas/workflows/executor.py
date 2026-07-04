"""Deterministic placeholder workflow executor.

The :class:`PlaceholderExecutor` is the default :class:`BaseExecutor`
implementation. It resolves step ``action`` strings through a small injected
action registry and returns a deterministic :class:`StepResult` for each
call. The executor is deliberately side-effect free (apart from writing to
the supplied ``context``) so that workflow behaviour is fully reproducible
in tests.

Built-in actions (overridable):

* ``noop`` — always succeeds; writes ``{step_id: "noop"}`` to the context.
* ``echo`` — succeeds; writes ``{step_id: <params>}`` to the context.
* ``fail`` — always fails with the message supplied in ``params.message``.
* ``wait`` — succeeds; signals that the run should enter the ``WAITING``
  state via the special :class:`WaitSignal` output.
* ``sleep`` — succeeds; records the requested duration in the output.

Custom actions can be registered through :meth:`register_action` or injected
via the constructor's ``actions`` argument. Any callable
``(params: dict, context: dict) -> Any`` is accepted; if it raises, the step
is marked failed with the exception message.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from atlas.workflows.base import BaseExecutor
from atlas.workflows.models import StepResult, WorkflowStep


class WaitSignal:
    """Marker type indicating that a step is requesting a WAIT transition.

    The executor wraps a :class:`WaitSignal` in a successful
    :class:`StepResult`; the engine inspects the output and, if it sees a
    :class:`WaitSignal`, transitions the run to the ``WAITING`` state.
    """

    def __init__(self, reason: str = "wait_requested", **payload: Any) -> None:
        self.reason = reason
        self.payload: dict[str, Any] = dict(payload)

    def __repr__(self) -> str:
        return f"<WaitSignal reason={self.reason!r} payload={self.payload!r}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WaitSignal):
            return NotImplemented
        return self.reason == other.reason and self.payload == other.payload


Action = Callable[[dict[str, Any], dict[str, Any]], Any]


class PlaceholderExecutor(BaseExecutor):
    """Deterministic placeholder executor.

    Parameters:
        actions: Optional mapping of action name -> callable. The callable
            receives ``(params, context)`` and may return any object. A
            returned :class:`WaitSignal` triggers a WAIT transition; any
            other return value is recorded as the step output. Raising an
            exception marks the step failed.
        name: Identifier for this executor.
    """

    def __init__(
        self,
        actions: dict[str, Action] | None = None,
        name: str = "placeholder",
    ) -> None:
        super().__init__(name=name)
        self._actions: dict[str, Action] = {}
        for action_name, fn in (actions or {}).items():
            self.register_action(action_name, fn)
        # Register built-ins only if not overridden by the caller.
        for action_name, fn in _BUILTIN_ACTIONS.items():
            self._actions.setdefault(action_name, fn)

    def register_action(self, name: str, fn: Action) -> None:
        """Register or override an action by name."""
        if not name or not name.strip():
            raise ValueError("Action name must be non-empty.")
        self._actions[name] = fn

    def has_action(self, name: str) -> bool:
        """Return ``True`` if ``name`` is a registered action."""
        return name in self._actions

    def known_actions(self) -> list[str]:
        """Return a sorted list of registered action names."""
        return sorted(self._actions)

    def execute_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute ``step`` and return a deterministic :class:`StepResult`."""
        started = datetime.now(UTC)
        action = self._actions.get(step.action)
        if action is None:
            return StepResult(
                step_id=step.id,
                success=False,
                error=f"Unknown action: {step.action!r}",
                started_at=started,
                completed_at=datetime.now(UTC),
            )

        try:
            output = action(dict(step.params), context)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the run
            return StepResult(
                step_id=step.id,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                started_at=started,
                completed_at=datetime.now(UTC),
            )

        # Side effect: persist a context entry so later steps can observe it.
        context[step.id] = output

        return StepResult(
            step_id=step.id,
            success=True,
            output=output,
            started_at=started,
            completed_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Built-in actions
# ---------------------------------------------------------------------------


def _noop_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always succeed; write a sentinel value."""
    return "noop"


def _echo_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Succeed and echo the supplied params as the output."""
    return dict(params)


def _fail_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Always raise a :class:`RuntimeError` with the supplied message."""
    message = params.get("message", "intentional failure")
    raise RuntimeError(message)


def _wait_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Return a :class:`WaitSignal` so the engine transitions to WAITING."""
    reason = params.get("reason", "wait_requested")
    payload = {k: v for k, v in params.items() if k != "reason"}
    return WaitSignal(reason=reason, **payload)


def _sleep_action(
    params: dict[str, Any], context: dict[str, Any]
) -> Any:  # noqa: ARG001
    """Succeed and record the requested duration (no actual sleeping)."""
    return {"slept_seconds": params.get("seconds", 0)}


_BUILTIN_ACTIONS: dict[str, Action] = {
    "noop": _noop_action,
    "echo": _echo_action,
    "fail": _fail_action,
    "wait": _wait_action,
    "sleep": _sleep_action,
}


__all__ = ["Action", "PlaceholderExecutor", "WaitSignal"]
