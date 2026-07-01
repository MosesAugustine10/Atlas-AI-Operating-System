"""Base agent class defining the Atlas agent lifecycle."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger


class BaseAgent(ABC):
    """Abstract base class for all Atlas agents.

    Every agent follows a four-phase lifecycle:

        plan -> execute -> review -> report

    Subclasses implement each phase. :meth:`run` wires them together
    into a single end-to-end pass over an objective.
    """

    def __init__(self, name: str, role: str | None = None) -> None:
        self.name = name
        self.role = role or name
        self.logger = get_logger(f"agent.{name}")
        self.logger.info("Agent initialised: %s (%s)", self.name, self.role)

    @abstractmethod
    def plan(self, objective: str) -> Any:
        """Develop a plan for the given objective."""

    @abstractmethod
    def execute(self, plan: Any) -> Any:
        """Execute the plan and return the raw result."""

    @abstractmethod
    def review(self, result: Any) -> Any:
        """Review the result of execution."""

    @abstractmethod
    def report(self, review: Any) -> str:
        """Produce a human-readable report from the review."""

    def run(self, objective: str) -> str:
        """Run the full four-phase lifecycle for an objective."""
        self.logger.info("Starting lifecycle: %s", objective)
        plan = self.plan(objective)
        result = self.execute(plan)
        review = self.review(result)
        return self.report(review)
