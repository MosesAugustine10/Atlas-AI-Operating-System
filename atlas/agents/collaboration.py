"""Multi-agent collaboration — agents working together.

The :class:`AgentCollaborator` coordinates multiple agents to work on a
single goal sequentially. Each agent's output is passed as context to
the next agent in the chain.

Example::

    Research Agent → Coding Agent → GitHub Agent → Browser Agent → Report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from atlas.agents.base import BaseAgent
from atlas.core.logger import get_logger


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CollaborationResult:
    """The outcome of a multi-agent collaboration.

    Attributes:
        goal: The original goal.
        agent_reports: Ordered list of (agent_name, report) tuples.
        final_report: The combined report from all agents.
        success: Whether every agent succeeded.
        duration_seconds: Wall-clock duration.
    """

    goal: str = ""
    agent_reports: list[tuple[str, str]] = field(default_factory=list)
    final_report: str = ""
    success: bool = True
    duration_seconds: float = 0.0


class AgentCollaborator:
    """Coordinates multiple agents working on a single goal.

    Parameters:
        agents: Ordered list of :class:`BaseAgent` instances. Each
            agent's output is passed as context to the next.
    """

    def __init__(self, agents: list[BaseAgent] | None = None) -> None:
        self.agents: list[BaseAgent] = list(agents or [])
        self.logger = get_logger("live.collaboration")

    def add_agent(self, agent: BaseAgent) -> AgentCollaborator:
        """Append ``agent`` to the collaboration chain."""
        self.agents.append(agent)
        return self

    def collaborate(self, goal: str) -> CollaborationResult:
        """Run every agent in sequence on ``goal``.

        Each agent's output is passed as the objective to the next
        agent, creating a pipeline where each agent builds on the
        previous one's work.
        """
        started = _utcnow()
        reports: list[tuple[str, str]] = []
        current_objective = goal
        success = True

        for agent in self.agents:
            self.logger.info(
                "Agent %s collaborating on: %s",
                agent.name,
                current_objective[:60],
            )
            try:
                report = agent.run(current_objective)
                reports.append((agent.name, report))
                # The next agent uses this agent's report as its objective.
                current_objective = report if isinstance(report, str) else str(report)
            except Exception as exc:  # noqa: BLE001
                reports.append((agent.name, f"ERROR: {exc}"))
                success = False
                break

        duration = (_utcnow() - started).total_seconds()
        final = "\n\n".join(f"[{name}]:\n{report}" for name, report in reports)
        result = CollaborationResult(
            goal=goal,
            agent_reports=reports,
            final_report=final,
            success=success,
            duration_seconds=duration,
        )
        self.logger.info(
            "Collaboration %s in %.2fs (%d agents)",
            "succeeded" if success else "failed",
            duration,
            len(reports),
        )
        return result

    def __len__(self) -> int:
        return len(self.agents)

    def __repr__(self) -> str:
        return f"<AgentCollaborator agents={len(self.agents)}>"


__all__ = ["AgentCollaborator", "CollaborationResult"]
