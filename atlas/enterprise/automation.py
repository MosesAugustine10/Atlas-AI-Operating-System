"""Automation engine — runs complete business automations."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from atlas.enterprise.models import (
    Automation,
    AutomationAction,
    AutomationCondition,
    AutomationRun,
    AutomationStatus,
    AutomationTrigger,
    ConditionOperator,
    LogicalOperator,
    _new_id,
    _utcnow,
)


class AutomationEngine:
    """Runs business automations with condition evaluation and action execution."""

    def __init__(self, execute_fn: Callable[..., Any] | None = None) -> None:
        self._automations: dict[str, Automation] = {}
        self._runs: dict[str, AutomationRun] = {}
        self._schedules: dict[str, list[Any]] = {}
        self._execute_fn = execute_fn

    def create(
        self,
        name: str,
        description: str = "",
        trigger: AutomationTrigger | None = None,
        conditions: tuple[AutomationCondition, ...] = (),
        actions: tuple[AutomationAction, ...] = (),
        priority: int = 0,
    ) -> Automation:
        a = Automation(
            id=_new_id("auto"),
            name=name,
            description=description,
            trigger=trigger,
            conditions=conditions,
            actions=actions,
            priority=priority,
        )
        self._automations[a.id] = a
        return a

    def get(self, aid: str) -> Automation | None:
        return self._automations.get(aid)

    def list(self, enabled_only: bool = False) -> list[Automation]:
        autos = list(self._automations.values())
        if enabled_only:
            autos = [a for a in autos if a.enabled]
        return sorted(autos, key=lambda a: a.priority, reverse=True)

    def enable(self, aid: str) -> Automation | None:
        a = self._automations.get(aid)
        if a is None:
            return None
        updated = dataclasses.replace(a, enabled=True)
        self._automations[aid] = updated
        return updated

    def disable(self, aid: str) -> Automation | None:
        a = self._automations.get(aid)
        if a is None:
            return None
        updated = dataclasses.replace(a, enabled=False)
        self._automations[aid] = updated
        return updated

    def delete(self, aid: str) -> bool:
        return self._automations.pop(aid, None) is not None

    def run(self, aid: str, context: dict[str, Any] | None = None) -> AutomationRun:
        a = self._require(aid)
        ctx = context or {}
        run = AutomationRun(
            id=_new_id("run"),
            automation_id=aid,
            status=AutomationStatus.RUNNING.value,
            trigger_data=tuple(sorted(ctx.items())),
        )
        self._runs[run.id] = run
        # Check conditions
        if not self._evaluate_conditions(a.conditions, ctx):
            completed = dataclasses.replace(
                run,
                status=AutomationStatus.COMPLETED.value,
                completed_at=_utcnow(),
                results=(("skipped", "conditions not met"),),
            )
            self._runs[run.id] = completed
            self._increment_run_count(aid)
            return completed
        # Execute actions
        results: list[tuple[str, str]] = []
        try:
            for action in a.actions:
                result = self._execute_action(action, ctx)
                results.append((action.type, str(result)))
            completed = dataclasses.replace(
                run,
                status=AutomationStatus.COMPLETED.value,
                completed_at=_utcnow(),
                results=tuple(results),
            )
        except Exception as exc:  # noqa: BLE001
            completed = dataclasses.replace(
                run,
                status=AutomationStatus.FAILED.value,
                completed_at=_utcnow(),
                error=str(exc),
                results=tuple(results),
            )
        self._runs[run.id] = completed
        self._increment_run_count(aid)
        return completed

    def fire_by_trigger(
        self, trigger_type: str, context: dict[str, Any] | None = None
    ) -> list[AutomationRun]:
        runs: list[AutomationRun] = []
        for a in self._automations.values():
            if a.enabled and a.trigger and a.trigger.type == trigger_type:
                runs.append(self.run(a.id, context))
        return runs

    def get_run(self, run_id: str) -> AutomationRun | None:
        return self._runs.get(run_id)

    def list_runs(self, automation_id: str | None = None) -> list[AutomationRun]:
        runs = list(self._runs.values())
        if automation_id is not None:
            runs = [r for r in runs if r.automation_id == automation_id]
        return sorted(runs, key=lambda r: r.started_at, reverse=True)

    def statistics(self) -> dict[str, Any]:
        total_runs = len(self._runs)
        successful = sum(
            1
            for r in self._runs.values()
            if r.status == AutomationStatus.COMPLETED.value
        )
        failed = sum(
            1 for r in self._runs.values() if r.status == AutomationStatus.FAILED.value
        )
        durations = [
            (r.completed_at - r.started_at).total_seconds()
            for r in self._runs.values()
            if r.completed_at
        ]
        avg_dur = sum(durations) / len(durations) if durations else 0.0
        most_fired_id = (
            max(self._automations.values(), key=lambda a: a.run_count).id
            if self._automations
            else ""
        )
        return {
            "total_automations": len(self._automations),
            "total_runs": total_runs,
            "successful_runs": successful,
            "failed_runs": failed,
            "average_duration_seconds": round(avg_dur, 4),
            "most_fired": most_fired_id,
        }

    def _evaluate_conditions(
        self, conditions: tuple[AutomationCondition, ...], ctx: dict[str, Any]
    ) -> bool:
        if not conditions:
            return True
        results: list[bool] = []
        for cond in conditions:
            results.append(self._evaluate_single(cond, ctx))
        # Apply logical operators
        logicals = [c.logical for c in conditions]
        result = results[0]
        for i in range(1, len(results)):
            op = logicals[i]
            if op == LogicalOperator.AND.value:
                result = result and results[i]
            elif op == LogicalOperator.OR.value:
                result = result or results[i]
            elif op == LogicalOperator.NOT.value:
                result = result and not results[i]
        return result

    def _evaluate_single(self, cond: AutomationCondition, ctx: dict[str, Any]) -> bool:
        val = str(ctx.get(cond.field, ""))
        target = cond.value
        if cond.operator == ConditionOperator.EQ.value:
            return val == target
        if cond.operator == ConditionOperator.NE.value:
            return val != target
        if cond.operator == ConditionOperator.GT.value:
            try:
                return float(val) > float(target)
            except ValueError:
                return val > target
        if cond.operator == ConditionOperator.GTE.value:
            try:
                return float(val) >= float(target)
            except ValueError:
                return val >= target
        if cond.operator == ConditionOperator.LT.value:
            try:
                return float(val) < float(target)
            except ValueError:
                return val < target
        if cond.operator == ConditionOperator.LTE.value:
            try:
                return float(val) <= float(target)
            except ValueError:
                return val <= target
        if cond.operator == ConditionOperator.CONTAINS.value:
            return target in val
        if cond.operator == ConditionOperator.IN.value:
            return val in target.split(",")
        if cond.operator == ConditionOperator.NOT_IN.value:
            return val not in target.split(",")
        return False

    def _execute_action(self, action: AutomationAction, ctx: dict[str, Any]) -> Any:
        if self._execute_fn is not None:
            return self._execute_fn(
                action=action.type, params=dict(action.params), context=ctx
            )
        return {"action": action.type, "executed": True}

    def _increment_run_count(self, aid: str) -> None:
        a = self._automations.get(aid)
        if a is None:
            return
        updated = dataclasses.replace(a, run_count=a.run_count + 1, last_run=_utcnow())
        self._automations[aid] = updated

    def _require(self, aid: str) -> Automation:
        a = self._automations.get(aid)
        if a is None:
            raise KeyError(f"automation {aid} not found")
        return a


__all__ = ["AutomationEngine"]
