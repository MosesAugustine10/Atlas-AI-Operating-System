"""Rules engine — IF/AND/OR/NOT conditions with priority and overrides."""

from __future__ import annotations

from typing import Any

from atlas.enterprise.models import (
    AutomationAction,
    AutomationCondition,
    BusinessRule,
    ConditionOperator,
    LogicalOperator,
    _new_id,
)


class RulesEngine:
    """Evaluates business rules with nested conditions, priority, and overrides."""

    def __init__(self) -> None:
        self._rules: dict[str, BusinessRule] = {}

    def create(
        self,
        name: str,
        conditions: tuple[AutomationCondition, ...] = (),
        actions: tuple[AutomationAction, ...] = (),
        priority: int = 0,
        override_ids: tuple[str, ...] = (),
        description: str = "",
    ) -> BusinessRule:
        r = BusinessRule(
            id=_new_id("rule"),
            name=name,
            description=description,
            conditions=conditions,
            actions=actions,
            priority=priority,
            override_ids=override_ids,
        )
        self._rules[r.id] = r
        return r

    def get(self, rid: str) -> BusinessRule | None:
        return self._rules.get(rid)

    def list(self, enabled_only: bool = False) -> list[BusinessRule]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def enable(self, rid: str) -> BusinessRule | None:
        r = self._rules.get(rid)
        if r is None:
            return None
        import dataclasses

        updated = dataclasses.replace(r, enabled=True)
        self._rules[rid] = updated
        return updated

    def disable(self, rid: str) -> BusinessRule | None:
        r = self._rules.get(rid)
        if r is None:
            return None
        import dataclasses

        updated = dataclasses.replace(r, enabled=False)
        self._rules[rid] = updated
        return updated

    def delete(self, rid: str) -> bool:
        return self._rules.pop(rid, None) is not None

    def evaluate(self, context: dict[str, Any]) -> list[BusinessRule]:
        """Return enabled rules matching ``context``, sorted by priority.

        Rules overridden by a higher-priority matching rule are excluded.
        """
        matched: list[BusinessRule] = []
        overridden: set[str] = set()
        for r in self._rules.values():
            if not r.enabled:
                continue
            if self._evaluate_conditions(r.conditions, context):
                matched.append(r)
                # Mark overridden rules
                for oid in r.override_ids:
                    overridden.add(oid)
        # Filter out overridden rules
        result = [r for r in matched if r.id not in overridden]
        return sorted(result, key=lambda r: r.priority, reverse=True)

    def evaluate_single(self, rule_id: str, context: dict[str, Any]) -> bool:
        r = self._rules.get(rule_id)
        if r is None:
            return False
        return self._evaluate_conditions(r.conditions, context)

    def count(self) -> int:
        return len(self._rules)

    def _evaluate_conditions(
        self, conditions: tuple[AutomationCondition, ...], ctx: dict[str, Any]
    ) -> bool:
        if not conditions:
            return True
        results: list[bool] = []
        for cond in conditions:
            results.append(self._evaluate_single(cond, ctx))
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


__all__ = ["RulesEngine"]
