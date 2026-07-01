"""Tests for the BaseAgent lifecycle."""

from __future__ import annotations

from typing import Any

from atlas.agents.base import BaseAgent


class _DummyAgent(BaseAgent):
    """Minimal concrete agent used to exercise the lifecycle."""

    def plan(self, objective: str) -> Any:
        return f"plan:{objective}"

    def execute(self, plan: Any) -> Any:
        return f"result:{plan}"

    def review(self, result: Any) -> Any:
        return f"review:{result}"

    def report(self, review: Any) -> str:
        return str(review)


def test_agent_has_four_phases() -> None:
    agent = _DummyAgent(name="dummy")
    for phase in ("plan", "execute", "review", "report"):
        assert hasattr(agent, phase)


def test_agent_lifecycle_runs_end_to_end() -> None:
    agent = _DummyAgent(name="dummy")
    report = agent.run("test objective")
    assert report == "review:result:plan:test objective"
