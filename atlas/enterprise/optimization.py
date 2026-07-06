"""Optimization engine — continuously improves scheduling, costs, revenue, etc."""

from __future__ import annotations

from collections.abc import Callable

from atlas.enterprise.models import (
    OptimizationResult,
    OptimizationTarget,
    OptimizationTask,
    _new_id,
)


class OptimizationEngine:
    """Generates optimization recommendations."""

    def __init__(
        self, optimize_fn: Callable[..., OptimizationResult] | None = None
    ) -> None:
        self._tasks: dict[str, OptimizationTask] = {}
        self._results: dict[str, OptimizationResult] = {}
        self._optimize_fn = optimize_fn

    def create_task(
        self,
        target: str = OptimizationTarget.COSTS.value,
        description: str = "",
        current_value: float = 0.0,
        target_value: float = 0.0,
    ) -> OptimizationTask:
        t = OptimizationTask(
            id=_new_id("opt"),
            target=target,
            description=description,
            current_value=current_value,
            target_value=target_value,
        )
        self._tasks[t.id] = t
        return t

    def optimize(self, task_id: str) -> OptimizationResult:
        t = self._tasks.get(task_id)
        if t is None:
            raise KeyError(f"optimization task {task_id} not found")
        if self._optimize_fn is not None:
            result = self._optimize_fn(task=t)
        else:
            result = self._fallback_optimize(t)
        self._results[result.id] = result
        return result

    def _fallback_optimize(self, task: OptimizationTask) -> OptimizationResult:
        # Simple: move 10% toward target
        delta = (task.target_value - task.current_value) * 0.1
        optimized = task.current_value + delta
        improvement = abs(delta)
        recommendation = (
            f"Move {task.target} from {task.current_value}"
            f" toward {task.target_value} by {delta:.2f}"
        )
        return OptimizationResult(
            id=_new_id("optres"),
            task_id=task.id,
            optimized_value=round(optimized, 2),
            improvement=round(improvement, 2),
            recommendation=recommendation,
        )

    def get_task(self, tid: str) -> OptimizationTask | None:
        return self._tasks.get(tid)

    def get_result(self, rid: str) -> OptimizationResult | None:
        return self._results.get(rid)

    def list_tasks(self, target: str | None = None) -> list[OptimizationTask]:
        ts = list(self._tasks.values())
        if target is not None:
            ts = [t for t in ts if t.target == target]
        return ts

    def list_results(self, task_id: str | None = None) -> list[OptimizationResult]:
        rs = list(self._results.values())
        if task_id is not None:
            rs = [r for r in rs if r.task_id == task_id]
        return rs

    def top_improvements(self, limit: int = 5) -> list[OptimizationResult]:
        return sorted(
            self._results.values(), key=lambda r: r.improvement, reverse=True
        )[:limit]

    def count(self) -> int:
        return len(self._tasks)


__all__ = ["OptimizationEngine"]
