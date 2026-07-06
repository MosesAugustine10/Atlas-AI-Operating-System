"""Automation rules (IF -> THEN workflows)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from atlas.business.models import (
    AutomationAction,
    AutomationRule,
    AutomationTrigger,
    _new_id,
    _utcnow,
)


class AutomationManager:
    def __init__(self, execute_fn: Callable[..., Any] | None = None) -> None:
        self._rules: dict[str, AutomationRule] = {}
        self._execution_log: list[dict[str, Any]] = []
        self._execute_fn = execute_fn

    def create(
        self,
        name: str,
        trigger: str = AutomationTrigger.MANUAL.value,
        conditions: tuple[tuple[str, str], ...] = (),
        action: str = AutomationAction.NOTIFY.value,
        action_params: tuple[tuple[str, str], ...] = (),
    ) -> AutomationRule:
        r = AutomationRule(
            id=_new_id("rule"),
            name=name,
            trigger=trigger,
            conditions=conditions,
            action=action,
            action_params=action_params,
        )
        self._rules[r.id] = r
        return r

    def get(self, rid: str) -> AutomationRule | None:
        return self._rules.get(rid)

    def list(self, enabled_only: bool = False) -> list[AutomationRule]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def enable(self, rid: str) -> AutomationRule | None:
        r = self._rules.get(rid)
        if r is None:
            return None
        updated = dataclasses.replace(r, enabled=True)
        self._rules[rid] = updated
        return updated

    def disable(self, rid: str) -> AutomationRule | None:
        r = self._rules.get(rid)
        if r is None:
            return None
        updated = dataclasses.replace(r, enabled=False)
        self._rules[rid] = updated
        return updated

    def fire(self, rid: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        r = self._rules.get(rid)
        if r is None:
            return {"fired": False, "reason": "rule not found"}
        if not r.enabled:
            return {"fired": False, "reason": "rule disabled"}
        # Check conditions
        ctx = context or {}
        for key, expected in r.conditions:
            if str(ctx.get(key, "")) != expected:
                return {"fired": False, "reason": f"condition {key}={expected} not met"}
        # Execute action
        result: dict[str, Any] = {
            "fired": True,
            "action": r.action,
            "params": dict(r.action_params),
        }
        if self._execute_fn is not None:
            try:
                result["output"] = self._execute_fn(
                    action=r.action, params=dict(r.action_params), context=ctx
                )
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)
        # Update fire count
        updated = dataclasses.replace(
            r, fire_count=r.fire_count + 1, last_fired=_utcnow()
        )
        self._rules[rid] = updated
        self._execution_log.append(
            {"rule_id": rid, "timestamp": _utcnow().isoformat(), "result": result}
        )
        return result

    def fire_by_trigger(
        self, trigger: str, context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._rules.values():
            if r.enabled and r.trigger == trigger:
                results.append(self.fire(r.id, context))
        return results

    def execution_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._execution_log[-limit:]))

    def count(self) -> int:
        return len(self._rules)

    def enabled_count(self) -> int:
        return sum(1 for r in self._rules.values() if r.enabled)


__all__ = ["AutomationManager"]
