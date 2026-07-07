"""Agent selection for the Atlas Kernel.

The :class:`Router` examines each :class:`~atlas.core.planner.Task` and the
surrounding :class:`~atlas.core.context.Context`, then decides which agent is
best suited to execute it. In the full implementation this consults a
registry of agents and their declared capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from atlas.core.context import Context
from atlas.core.planner import Task


@dataclass
class AgentDescriptor:
    """Describes an agent available to the Router for assignment.

    Attributes:
        name: Unique name of the agent / role.
        capabilities: Keywords describing what the agent can do.
    """

    name: str
    capabilities: list[str] = field(default_factory=list)


class Router:
    """Selects the correct agent for a given task.

    Parameters:
        agents: Optional initial set of agents to register.
    """

    def __init__(self, agents: list[AgentDescriptor] | None = None) -> None:
        self.agents: dict[str, AgentDescriptor] = {
            agent.name: agent for agent in (agents or [])
        }
        self._default = AgentDescriptor(name="default")

    def register(self, agent: AgentDescriptor) -> None:
        """Register an agent as available for selection."""
        self.agents[agent.name] = agent

    def select(self, task: Task, context: Context) -> AgentDescriptor:  # noqa: ARG002
        """Choose an agent to execute ``task``.

        .. note::
            Placeholder implementation. When no agents are registered it
            returns a default descriptor; otherwise it returns the first
            registered agent. Capability-based matching is added later.
        """
        if not self.agents:
            return self._default
        return next(iter(self.agents.values()))
