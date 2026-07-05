"""Adaptive planner — generates and adjusts plans dynamically.

Unlike the :class:`ExecutionPlanner` (which produces a fixed plan),
the :class:`AdaptivePlanner` can **split**, **merge**, **remove**,
**insert**, and **reorder** tasks during execution based on
intermediate results.

The planner is deterministic: it recognises goal patterns and produces
a fixed initial plan. Adjustments are driven by explicit method calls
(:meth:`split`, :meth:`merge`, :meth:`remove`, :meth:`insert`,
:meth:`reorder`) that the :class:`Coordinator` invokes based on
execution feedback.
"""

from __future__ import annotations

import dataclasses

from atlas.core.logger import get_logger
from atlas.intelligence.models import (
    AdaptivePlan,
    GoalPriority,
    IntelligenceTask,
    PlanAdjustment,
)


class AdaptivePlanner:
    """Generates and dynamically adjusts :class:`AdaptivePlan` instances.

    Parameters:
        max_tasks: Maximum tasks per plan. Defaults to 20.
    """

    def __init__(self, max_tasks: int = 20) -> None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be >= 1")
        self.max_tasks = max_tasks
        self.logger = get_logger("intelligence.planner")

    # ------------------------------------------------------------------
    # Initial plan generation
    # ------------------------------------------------------------------

    def plan(
        self,
        goal_id: str,
        goal_description: str,
    ) -> AdaptivePlan:
        """Generate an initial :class:`AdaptivePlan` for ``goal_description``."""
        tasks = self._generate_tasks(goal_description)
        plan = AdaptivePlan(
            goal_id=goal_id,
            tasks=tasks,
            adjustments=[],
            version=1,
            metadata={"goal": goal_description},
        )
        self.logger.info(
            "Generated plan %s with %d task(s) for goal %s",
            plan.id,
            len(tasks),
            goal_id,
        )
        return plan

    # ------------------------------------------------------------------
    # Adaptive adjustments
    # ------------------------------------------------------------------

    def split(
        self,
        plan: AdaptivePlan,
        task_id: str,
        sub_descriptions: list[str],
    ) -> AdaptivePlan:
        """Split ``task_id`` into multiple sub-tasks.

        The original task is replaced by the sub-tasks. Each sub-task
        depends on the original task's dependencies.
        """
        task = plan.task_by_id(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id!r}")
        if not sub_descriptions:
            raise ValueError("sub_descriptions must be non-empty")
        new_tasks: list[IntelligenceTask] = []
        for i, desc in enumerate(sub_descriptions):
            new_tasks.append(
                IntelligenceTask(
                    description=desc,
                    capability=task.capability,
                    params=dict(task.params),
                    dependencies=list(task.dependencies) if i == 0 else [f"prev_{i}"],
                    priority=task.priority,
                    optional=task.optional,
                    metadata={"split_from": task_id},
                )
            )
        # Fix dependencies: each sub-task depends on the previous one.
        for i in range(1, len(new_tasks)):
            new_tasks[i] = dataclasses.replace(
                new_tasks[i],
                dependencies=[new_tasks[i - 1].id],
            )
        # Replace the original task in the list.
        updated_tasks = []
        for t in plan.tasks:
            if t.id == task_id:
                updated_tasks.extend(new_tasks)
            else:
                # Update any dependencies that pointed to the old task.
                if task_id in t.dependencies:
                    t = dataclasses.replace(
                        t,
                        dependencies=[
                            new_tasks[-1].id if d == task_id else d
                            for d in t.dependencies
                        ],
                    )
                updated_tasks.append(t)
        return self._new_version(plan, updated_tasks, PlanAdjustment.SPLIT)

    def merge(
        self,
        plan: AdaptivePlan,
        task_ids: list[str],
        merged_description: str,
    ) -> AdaptivePlan:
        """Merge multiple tasks into one."""
        if len(task_ids) < 2:
            raise ValueError("merge requires at least 2 tasks")
        tasks_to_merge = [plan.task_by_id(tid) for tid in task_ids]
        if any(t is None for t in tasks_to_merge):
            raise ValueError("one or more tasks not found")
        # Collect all dependencies from merged tasks.
        all_deps: list[str] = []
        for t in tasks_to_merge:
            for dep in t.dependencies:
                if dep not in task_ids and dep not in all_deps:
                    all_deps.append(dep)
        merged = IntelligenceTask(
            description=merged_description,
            capability=tasks_to_merge[0].capability,
            params={},
            dependencies=all_deps,
            priority=max(t.priority for t in tasks_to_merge),
            optional=all(t.optional for t in tasks_to_merge),
            metadata={"merged_from": task_ids},
        )
        updated_tasks = []
        for t in plan.tasks:
            if t.id in task_ids:
                if not updated_tasks or updated_tasks[-1].id != merged.id:
                    updated_tasks.append(merged)
            else:
                # Update dependencies that pointed to any merged task.
                if any(tid in t.dependencies for tid in task_ids):
                    t = dataclasses.replace(
                        t,
                        dependencies=[
                            merged.id if d in task_ids else d for d in t.dependencies
                        ],
                    )
                updated_tasks.append(t)
        return self._new_version(plan, updated_tasks, PlanAdjustment.MERGE)

    def remove(
        self,
        plan: AdaptivePlan,
        task_id: str,
    ) -> AdaptivePlan:
        """Remove a task from the plan."""
        task = plan.task_by_id(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id!r}")
        updated_tasks = []
        for t in plan.tasks:
            if t.id == task_id:
                continue
            # Remove the deleted task from dependencies.
            if task_id in t.dependencies:
                t = dataclasses.replace(
                    t,
                    dependencies=[d for d in t.dependencies if d != task_id],
                )
            updated_tasks.append(t)
        return self._new_version(plan, updated_tasks, PlanAdjustment.REMOVE)

    def insert(
        self,
        plan: AdaptivePlan,
        after_task_id: str | None,
        task: IntelligenceTask,
    ) -> AdaptivePlan:
        """Insert ``task`` after ``after_task_id`` (or at the beginning)."""
        if after_task_id is not None:
            existing = plan.task_by_id(after_task_id)
            if existing is None:
                raise ValueError(f"task not found: {after_task_id!r}")
        updated_tasks: list[IntelligenceTask] = []
        inserted = False
        for t in plan.tasks:
            updated_tasks.append(t)
            if after_task_id is not None and t.id == after_task_id and not inserted:
                updated_tasks.append(task)
                inserted = True
        if not inserted:
            if after_task_id is None:
                updated_tasks.insert(0, task)
            else:
                updated_tasks.append(task)
        return self._new_version(plan, updated_tasks, PlanAdjustment.INSERT)

    def reorder(
        self,
        plan: AdaptivePlan,
        new_order: list[str],
    ) -> AdaptivePlan:
        """Reorder tasks by ID."""
        task_map = {t.id: t for t in plan.tasks}
        if set(new_order) != set(task_map):
            raise ValueError("new_order must contain every task id exactly once")
        updated_tasks = [task_map[tid] for tid in new_order]
        return self._new_version(plan, updated_tasks, PlanAdjustment.REORDER)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate_tasks(self, goal_description: str) -> list[IntelligenceTask]:
        """Generate tasks based on goal pattern matching."""
        desc_lower = goal_description.lower()
        if "website" in desc_lower or "web app" in desc_lower:
            return self._website_tasks(goal_description)
        if "research" in desc_lower:
            return self._research_tasks(goal_description)
        if "code" in desc_lower or "implement" in desc_lower:
            return self._code_tasks(goal_description)
        if "deploy" in desc_lower:
            return self._deploy_tasks(goal_description)
        # Default: single task.
        return [
            IntelligenceTask(
                description=f"Execute: {goal_description}",
                capability="execute",
                priority=GoalPriority.NORMAL,
            )
        ]

    def _website_tasks(self, goal: str) -> list[IntelligenceTask]:
        t1 = IntelligenceTask(
            description="Research requirements",
            capability="research",
            priority=GoalPriority.HIGH,
        )
        t2 = IntelligenceTask(
            description="Design architecture",
            capability="generate",
            dependencies=[t1.id],
            priority=GoalPriority.HIGH,
        )
        t3 = IntelligenceTask(
            description="Implement frontend",
            capability="generate_code",
            dependencies=[t2.id],
            priority=GoalPriority.NORMAL,
        )
        t4 = IntelligenceTask(
            description="Implement backend",
            capability="generate_code",
            dependencies=[t2.id],
            priority=GoalPriority.NORMAL,
        )
        t5 = IntelligenceTask(
            description="Test and deploy",
            capability="deploy",
            dependencies=[t3.id, t4.id],
            priority=GoalPriority.LOW,
        )
        return [t1, t2, t3, t4, t5]

    def _research_tasks(self, goal: str) -> list[IntelligenceTask]:
        t1 = IntelligenceTask(
            description="Gather sources",
            capability="research",
            priority=GoalPriority.HIGH,
        )
        t2 = IntelligenceTask(
            description="Synthesize findings",
            capability="generate",
            dependencies=[t1.id],
            priority=GoalPriority.NORMAL,
        )
        return [t1, t2]

    def _code_tasks(self, goal: str) -> list[IntelligenceTask]:
        t1 = IntelligenceTask(
            description="Understand requirements",
            capability="research",
            priority=GoalPriority.HIGH,
        )
        t2 = IntelligenceTask(
            description="Write implementation",
            capability="generate_code",
            dependencies=[t1.id],
            priority=GoalPriority.HIGH,
        )
        t3 = IntelligenceTask(
            description="Write tests",
            capability="run_tests",
            dependencies=[t2.id],
            priority=GoalPriority.NORMAL,
        )
        return [t1, t2, t3]

    def _deploy_tasks(self, goal: str) -> list[IntelligenceTask]:
        t1 = IntelligenceTask(
            description="Run tests",
            capability="run_tests",
            priority=GoalPriority.HIGH,
        )
        t2 = IntelligenceTask(
            description="Build artifacts",
            capability="generate",
            dependencies=[t1.id],
            priority=GoalPriority.NORMAL,
        )
        t3 = IntelligenceTask(
            description="Deploy to target",
            capability="deploy",
            dependencies=[t2.id],
            priority=GoalPriority.LOW,
        )
        return [t1, t2, t3]

    def _new_version(
        self,
        plan: AdaptivePlan,
        tasks: list[IntelligenceTask],
        adjustment: PlanAdjustment,
    ) -> AdaptivePlan:
        """Create a new plan version with the adjustment recorded."""
        return dataclasses.replace(
            plan,
            tasks=tasks,
            adjustments=[*plan.adjustments, adjustment],
            version=plan.version + 1,
        )


__all__ = ["AdaptivePlanner"]
