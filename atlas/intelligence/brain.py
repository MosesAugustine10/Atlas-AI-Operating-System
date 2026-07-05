"""Brain — the top-level facade of the Intelligence Layer.

The :class:`Brain` is the single entry point through which the rest of
Atlas invokes intelligence. It wires together the :class:`GoalManager`,
:class:`TaskDecomposer`, :class:`Reasoner`, :class:`AdaptivePlanner`,
:class:`DecisionEngine`, :class:`Critic`, :class:`ReflectionEngine`,
:class:`LearningEngine`, and :class:`Coordinator`.

The public API is intentionally minimal::

    brain = Brain()
    outcome = brain.think("Create a website for my portfolio")
    print(outcome.status, outcome.result)

The :meth:`think` method runs the full thinking pipeline:

1. Understand Goal
2. Search Knowledge
3. Recall Memory
4. Reason
5. Plan
6. Choose Agents / Providers / Tools
7. Execute
8. Review
9. Reflect
10. Learn
11. Update Memory
12. Return Report
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.critic import Critic
from atlas.intelligence.decision import DecisionEngine
from atlas.intelligence.goal_manager import GoalManager
from atlas.intelligence.learning import LearningEngine
from atlas.intelligence.models import (
    AdaptivePlan,
    Decision,
    ExecutionOutcome,
    Goal,
    GoalPriority,
    GoalScope,
    GoalStatus,
    Reflection,
)
from atlas.intelligence.planner import AdaptivePlanner
from atlas.intelligence.reasoner import Reasoner
from atlas.intelligence.reflection import ReflectionEngine
from atlas.intelligence.task_decomposer import TaskDecomposer


class BrainError(RuntimeError):
    """Raised when the brain cannot perform the requested operation."""


class Brain:
    """The top-level facade of the Atlas Intelligence Layer.

    Parameters:
        goal_manager: The :class:`GoalManager` to use. A new one is
            created if omitted.
        decomposer: The :class:`TaskDecomposer` to use. A new one is
            created if omitted.
        reasoner: The :class:`Reasoner` to use. A new one is created
            if omitted.
        planner: The :class:`AdaptivePlanner` to use. A new one is
            created if omitted.
        decision: The :class:`DecisionEngine` to use. A new one is
            created if omitted.
        critic: The :class:`Critic` to use. A new one is created if
            omitted.
        reflection: The :class:`ReflectionEngine` to use. A new one
            is created if omitted.
        learning: The :class:`LearningEngine` to use. A new one is
            created if omitted.
        coordinator: The :class:`Coordinator` to use. If omitted, the
            brain runs in "offline" mode (no subsystem execution).
    """

    def __init__(
        self,
        goal_manager: GoalManager | None = None,
        decomposer: TaskDecomposer | None = None,
        reasoner: Reasoner | None = None,
        planner: AdaptivePlanner | None = None,
        decision: DecisionEngine | None = None,
        critic: Critic | None = None,
        reflection: ReflectionEngine | None = None,
        learning: LearningEngine | None = None,
        coordinator: Any = None,
    ) -> None:
        # NOTE: explicit ``is None`` checks because some dependencies
        # define ``__len__`` and would be falsy when empty.
        self.goal_manager = goal_manager if goal_manager is not None else GoalManager()
        self.decomposer = decomposer if decomposer is not None else TaskDecomposer()
        self.reasoner = reasoner if reasoner is not None else Reasoner()
        self.planner = planner if planner is not None else AdaptivePlanner()
        self.decision = decision if decision is not None else DecisionEngine()
        self.critic = critic if critic is not None else Critic()
        self.reflection = reflection if reflection is not None else ReflectionEngine()
        self.learning = learning if learning is not None else LearningEngine()
        self.coordinator = coordinator
        self.logger = get_logger("intelligence.brain")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def think(
        self,
        goal_description: str,
        scope: GoalScope = GoalScope.SHORT_TERM,
        priority: GoalPriority = GoalPriority.NORMAL,
    ) -> ExecutionOutcome:
        """Run the full thinking pipeline for ``goal_description``.

        This is the canonical entry point. The pipeline is:

        1. Understand Goal — create a :class:`Goal`.
        2. Search Knowledge — query the knowledge engine.
        3. Recall Memory — query the memory engine.
        4. Reason — build a :class:`ReasoningChain`.
        5. Plan — generate an :class:`AdaptivePlan`.
        6. Choose — make :class:`Decision` items for each task.
        7. Execute — run the plan via the coordinator.
        8. Review — critique the output.
        9. Reflect — extract lessons.
        10. Learn — store lessons.
        11. Update Memory — write the outcome to memory.
        12. Return — return an :class:`ExecutionOutcome`.
        """
        if not goal_description or not goal_description.strip():
            raise BrainError("goal_description must be non-empty")

        started = datetime.now(UTC)
        self.logger.info("Thinking about: %r", goal_description[:60])

        # 1. Understand Goal
        goal = self.goal_manager.create(
            description=goal_description,
            scope=scope,
            priority=priority,
        )
        self.goal_manager.start(goal.id)

        try:
            # 2. Search Knowledge
            knowledge_hits = self._search_knowledge(goal_description)

            # 3. Recall Memory
            memory_hits = self._recall_memory(goal_description)

            # 4. Reason
            chain = self.reasoner.reason(
                goal_description,
                context={
                    "knowledge_hits": knowledge_hits,
                    "memory_hits": memory_hits,
                },
            )

            # 5. Plan
            plan = self.planner.plan(goal.id, goal_description)

            # 6. Choose
            decisions = self._make_decisions(plan)

            # 7. Execute
            result = self._execute(plan, decisions)

            # 8. Review
            critique = self.critic.critique(
                output=result,
                expected=goal_description,
                success=True,
            )

            # 9. Reflect
            duration = (datetime.now(UTC) - started).total_seconds()
            reflection = self.reflection.reflect(
                goal_id=goal.id,
                expected=goal_description,
                actual=str(result),
                success=True,
                quality_score=critique.quality_score,
                duration_seconds=duration,
            )

            # 10. Learn
            for lesson in reflection.lessons:
                self.learning.learn(lesson)

            # 11. Update Memory
            self._update_memory(goal, result, reflection)

            # 12. Return
            self.goal_manager.complete(goal.id, result=result)
            completed = datetime.now(UTC)
            outcome = ExecutionOutcome(
                goal_id=goal.id,
                status=GoalStatus.COMPLETED,
                result=result,
                reasoning=chain,
                plan=plan,
                decisions=decisions,
                critique=critique,
                reflection=reflection,
                lessons=reflection.lessons,
                duration_seconds=(completed - started).total_seconds(),
                started_at=started,
                completed_at=completed,
                metadata={
                    "knowledge_hits": len(knowledge_hits),
                    "memory_hits": len(memory_hits),
                },
            )
            self.logger.info(
                "Finished thinking about %s: status=%s duration=%.2fs",
                goal.id,
                outcome.status.value,
                outcome.duration_seconds,
            )
            return outcome

        except Exception as exc:  # noqa: BLE001
            self.goal_manager.fail(goal.id, error=str(exc))
            completed = datetime.now(UTC)
            return ExecutionOutcome(
                goal_id=goal.id,
                status=GoalStatus.FAILED,
                error=str(exc),
                started_at=started,
                completed_at=completed,
                duration_seconds=(completed - started).total_seconds(),
            )

    def think_many(
        self,
        goal_descriptions: list[str],
    ) -> list[ExecutionOutcome]:
        """Run :meth:`think` for each goal in ``goal_descriptions``."""
        return [self.think(g) for g in goal_descriptions]

    def status(self) -> dict[str, Any]:
        """Return a brief status summary of the brain."""
        return {
            "goals_total": len(self.goal_manager),
            "goals_active": len(self.goal_manager.active_goals()),
            "lessons_learned": len(self.learning),
            "has_coordinator": self.coordinator is not None,
        }

    # ------------------------------------------------------------------
    # Internal pipeline stages
    # ------------------------------------------------------------------

    def _search_knowledge(self, query: str) -> list[Any]:
        """Stage 2: Search the knowledge engine via the coordinator."""
        if self.coordinator is None:
            return []
        return self.coordinator.search_knowledge(query)

    def _recall_memory(self, query: str) -> list[Any]:  # noqa: ARG002
        """Stage 3: Recall from the memory engine via the coordinator."""
        if self.coordinator is None:
            return []
        return self.coordinator.recall_memory()

    def _make_decisions(self, plan: AdaptivePlan) -> list[Decision]:
        """Stage 6: Choose a candidate for each task in the plan."""
        decisions: list[Decision] = []
        candidates = (
            self.coordinator.all_candidates() if self.coordinator is not None else []
        )
        for task in plan.tasks:
            if not task.capability:
                continue
            try:
                decision = self.decision.decide(
                    required_capability=task.capability,
                    candidates=candidates or [],
                    kind="auto",
                )
                decisions.append(decision)
            except ValueError:
                # No matching candidate — skip.
                pass
        return decisions

    def _execute(
        self,
        plan: AdaptivePlan,
        decisions: list[Decision],
    ) -> Any:
        """Stage 7: Execute the plan via the coordinator."""
        if self.coordinator is None:
            return {
                "status": "offline",
                "plan_tasks": len(plan.tasks),
                "decisions": len(decisions),
                "note": "coordinator not configured",
            }
        # Try execution engine first.
        if self.coordinator.has_execution():
            goal_desc = plan.metadata.get("goal", "")
            return self.coordinator.execute_goal(goal_desc)
        # Fall back to runtime.
        if self.coordinator.has_runtime():
            return self.coordinator.run_runtime(plan.metadata.get("goal", ""))
        return {
            "status": "no_executor",
            "plan_tasks": len(plan.tasks),
        }

    def _update_memory(
        self,
        goal: Goal,
        result: Any,
        reflection: Reflection,
    ) -> None:
        """Stage 11: Write the outcome to memory."""
        if self.coordinator is None:
            return
        self.coordinator.remember(
            content={
                "goal_id": goal.id,
                "goal": goal.description,
                "result": str(result)[:200],
                "quality": reflection.quality_score,
                "lessons": len(reflection.lessons),
            },
            source="intelligence.brain",
            tags=["intelligence", "outcome"],
        )

    def __repr__(self) -> str:
        return (
            f"<Brain goals={len(self.goal_manager)} " f"lessons={len(self.learning)}>"
        )


__all__ = ["Brain", "BrainError"]
