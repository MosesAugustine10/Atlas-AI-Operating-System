"""Task decomposer — breaks complex goals into sub-goals recursively.

The :class:`TaskDecomposer` takes a goal and produces a
:class:`~atlas.intelligence.models.GoalTree` — a recursive tree of
sub-goals. The decomposition is deterministic and capability-based: the
decomposer recognises a small set of goal patterns and produces a fixed
tree for each.

Future AI-driven decomposition can replace :meth:`decompose` without
changing the contract.
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.intelligence.models import Goal, GoalPriority, GoalTree


class TaskDecomposer:
    """Breaks complex goals into sub-goals recursively.

    Parameters:
        max_depth: Maximum recursion depth. Defaults to 3.
        max_children: Maximum children per node. Defaults to 5.
    """

    def __init__(
        self,
        max_depth: int = 3,
        max_children: int = 5,
    ) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if max_children < 1:
            raise ValueError("max_children must be >= 1")
        self.max_depth = max_depth
        self.max_children = max_children
        self.logger = get_logger("intelligence.decomposer")

    def decompose(
        self,
        goal: Goal,
        depth: int = 0,
    ) -> GoalTree:
        """Recursively decompose ``goal`` into a :class:`GoalTree`.

        If ``depth`` >= :attr:`max_depth` or the goal is simple enough,
        returns a leaf tree with no children.
        """
        if depth >= self.max_depth:
            return GoalTree(root=goal)
        children_goals = self._generate_subgoals(goal, depth)
        if not children_goals:
            return GoalTree(root=goal)
        children_trees = [self.decompose(g, depth + 1) for g in children_goals]
        tree = GoalTree(root=goal, children=children_trees)
        self.logger.info(
            "Decomposed goal %s into %d sub-goal(s) at depth %d",
            goal.id,
            len(children_trees),
            depth,
        )
        return tree

    def decompose_flat(self, goal: Goal) -> list[Goal]:
        """Decompose ``goal`` and return a flat list of all sub-goals."""
        tree = self.decompose(goal)
        flat = tree.flatten()
        return flat[1:]  # exclude the root

    # ------------------------------------------------------------------
    # Pattern-based decomposition
    # ------------------------------------------------------------------

    def _generate_subgoals(self, goal: Goal, depth: int) -> list[Goal]:
        """Generate sub-goals for ``goal`` based on pattern matching.

        The current implementation is deterministic: it recognises a
        small set of keywords in the goal description and produces
        fixed sub-goals. Future versions can delegate to an LLM.
        """
        desc_lower = goal.description.lower()

        if "website" in desc_lower or "web app" in desc_lower:
            return self._website_subgoals(goal, depth)
        if "research" in desc_lower:
            return self._research_subgoals(goal, depth)
        if "code" in desc_lower or "implement" in desc_lower:
            return self._code_subgoals(goal, depth)
        if "deploy" in desc_lower:
            return self._deploy_subgoals(goal, depth)
        if "analyze" in desc_lower or "analyse" in desc_lower:
            return self._analyze_subgoals(goal, depth)
        # No pattern matched — return no sub-goals.
        return []

    def _website_subgoals(self, goal: Goal, depth: int) -> list[Goal]:
        return [
            self._subgoal(goal, "Research requirements", depth),
            self._subgoal(goal, "Design architecture", depth),
            self._subgoal(goal, "Implement frontend", depth),
            self._subgoal(goal, "Implement backend", depth),
            self._subgoal(goal, "Test and deploy", depth),
        ]

    def _research_subgoals(self, goal: Goal, depth: int) -> list[Goal]:
        return [
            self._subgoal(goal, "Gather sources", depth),
            self._subgoal(goal, "Synthesize findings", depth),
        ]

    def _code_subgoals(self, goal: Goal, depth: int) -> list[Goal]:
        return [
            self._subgoal(goal, "Understand requirements", depth),
            self._subgoal(goal, "Write implementation", depth),
            self._subgoal(goal, "Write tests", depth),
        ]

    def _deploy_subgoals(self, goal: Goal, depth: int) -> list[Goal]:
        return [
            self._subgoal(goal, "Run tests", depth),
            self._subgoal(goal, "Build artifacts", depth),
            self._subgoal(goal, "Deploy to target", depth),
        ]

    def _analyze_subgoals(self, goal: Goal, depth: int) -> list[Goal]:
        return [
            self._subgoal(goal, "Collect data", depth),
            self._subgoal(goal, "Process and analyze", depth),
            self._subgoal(goal, "Generate report", depth),
        ]

    def _subgoal(
        self,
        parent: Goal,
        description: str,
        depth: int,
    ) -> Goal:
        """Create a sub-goal of ``parent``."""
        priority = GoalPriority.NORMAL if depth > 0 else parent.priority
        return Goal(
            description=f"{description} (for: {parent.description[:40]})",
            scope=parent.scope,
            priority=priority,
            parent_id=parent.id,
            dependencies=[parent.id] if depth == 0 else [],
        )


__all__ = ["TaskDecomposer"]
