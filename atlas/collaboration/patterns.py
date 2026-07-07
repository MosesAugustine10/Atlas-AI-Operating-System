"""Collaboration patterns — reusable multi-agent collaboration templates.

The :class:`PatternLibrary` provides ready-made collaboration patterns
that can be instantiated and executed. Each pattern returns a
:class:`~atlas.collaboration.coordination.CoordinationEngine` pipeline
or a set of coordination instructions.

Patterns are pure-Python templates — they never import Brain or
Workforce directly.
"""

from __future__ import annotations

from atlas.collaboration.coordination import CoordinationEngine
from atlas.collaboration.models import (
    AgentRole,
    Pipeline,
)


class PatternLibrary:
    """Library of ready-made collaboration patterns."""

    def __init__(self, engine: CoordinationEngine | None = None) -> None:
        self.engine = engine or CoordinationEngine()

    # ------------------------------------------------------------------
    # Software development patterns
    # ------------------------------------------------------------------

    def research_plan_code_review(
        self,
        session_id: str,
        researcher_id: str,
        planner_id: str,
        coder_id: str,
        reviewer_id: str,
    ) -> Pipeline:
        """Research → Plan → Code → Review pipeline."""
        return self.engine.build_pipeline(
            session_id=session_id,
            steps=[
                (researcher_id, AgentRole.RESEARCHER.value),
                (planner_id, AgentRole.PLANNER.value),
                (coder_id, AgentRole.CODER.value),
                (reviewer_id, AgentRole.REVIEWER.value),
            ],
            name="research_plan_code_review",
        )

    def code_review_deploy(
        self,
        session_id: str,
        coder_id: str,
        reviewer_id: str,
        deployer_id: str,
    ) -> Pipeline:
        """Code → Review → Deploy pipeline."""
        return self.engine.build_pipeline(
            session_id=session_id,
            steps=[
                (coder_id, AgentRole.CODER.value),
                (reviewer_id, AgentRole.REVIEWER.value),
                (deployer_id, AgentRole.DEPLOYER.value),
            ],
            name="code_review_deploy",
        )

    # ------------------------------------------------------------------
    # Content creation patterns
    # ------------------------------------------------------------------

    def research_write_review_publish(
        self,
        session_id: str,
        researcher_id: str,
        writer_id: str,
        reviewer_id: str,
        deployer_id: str,
    ) -> Pipeline:
        """Research → Write → Review → Publish pipeline."""
        return self.engine.build_pipeline(
            session_id=session_id,
            steps=[
                (researcher_id, AgentRole.RESEARCHER.value),
                (writer_id, AgentRole.WRITER.value),
                (reviewer_id, AgentRole.REVIEWER.value),
                (deployer_id, AgentRole.DEPLOYER.value),
            ],
            name="research_write_review_publish",
        )

    def design_review_iterate(
        self,
        session_id: str,
        designer_id: str,
        reviewer_id: str,
        rounds: int = 2,
    ) -> Pipeline:
        """Design → Review → iterate ``rounds`` times."""
        steps: list[tuple[str, str]] = []
        for _ in range(rounds):
            steps.append((designer_id, AgentRole.DESIGNER.value))
            steps.append((reviewer_id, AgentRole.REVIEWER.value))
        return self.engine.build_pipeline(
            session_id=session_id,
            steps=steps,
            name="design_review_iterate",
        )

    # ------------------------------------------------------------------
    # Fan-out / fan-in patterns
    # ------------------------------------------------------------------

    def parallel_research_synthesize(
        self,
        session_id: str,
        coordinator_id: str,
        researcher_ids: list[str],
    ) -> Pipeline:
        """Coordinator → fan-out to researchers → fan-in to coordinator."""
        return self.engine.build_fan_out(
            session_id=session_id,
            initiator_id=coordinator_id,
            worker_ids=researcher_ids,
            name="parallel_research",
        )

    def parallel_coding_integrate(
        self,
        session_id: str,
        coder_ids: list[str],
        integrator_id: str,
    ) -> Pipeline:
        """Fan-out to coders → fan-in to integrator."""
        return self.engine.build_fan_in(
            session_id=session_id,
            worker_ids=coder_ids,
            aggregator_id=integrator_id,
            name="parallel_coding_integrate",
        )

    # ------------------------------------------------------------------
    # Debate / consensus patterns
    # ------------------------------------------------------------------

    def debate_and_vote(
        self,
        session_id: str,
        proposer_ids: list[str],
        voter_ids: list[str],
    ) -> Pipeline:
        """Proposers debate, then voters vote."""
        return self.engine.build_debate(
            session_id=session_id,
            proposer_ids=proposer_ids,
            voter_ids=voter_ids,
            name="debate_and_vote",
        )

    def round_robin_review(
        self,
        session_id: str,
        reviewer_ids: list[str],
        rounds: int = 1,
    ) -> Pipeline:
        """Reviewers take turns in a round-robin."""
        return self.engine.build_round_robin(
            session_id=session_id,
            agent_ids=reviewer_ids,
            rounds=rounds,
            name="round_robin_review",
        )

    # ------------------------------------------------------------------
    # Full lifecycle patterns
    # ------------------------------------------------------------------

    def full_software_lifecycle(
        self,
        session_id: str,
        researcher_id: str,
        planner_id: str,
        coder_id: str,
        tester_id: str,
        reviewer_id: str,
        deployer_id: str,
    ) -> Pipeline:
        """Research → Plan → Code → Test → Review → Deploy."""
        return self.engine.build_pipeline(
            session_id=session_id,
            steps=[
                (researcher_id, AgentRole.RESEARCHER.value),
                (planner_id, AgentRole.PLANNER.value),
                (coder_id, AgentRole.CODER.value),
                (tester_id, AgentRole.TESTER.value),
                (reviewer_id, AgentRole.REVIEWER.value),
                (deployer_id, AgentRole.DEPLOYER.value),
            ],
            name="full_software_lifecycle",
        )

    # ------------------------------------------------------------------
    # Pattern catalogue
    # ------------------------------------------------------------------

    def pattern_names(self) -> list[str]:
        """Return the names of all available patterns."""
        return [
            "research_plan_code_review",
            "code_review_deploy",
            "research_write_review_publish",
            "design_review_iterate",
            "parallel_research_synthesize",
            "parallel_coding_integrate",
            "debate_and_vote",
            "round_robin_review",
            "full_software_lifecycle",
        ]

    def build(
        self,
        pattern_name: str,
        session_id: str,
        agent_ids: dict[str, str],
    ) -> Pipeline:
        """Build a pattern by name.

        ``agent_ids`` maps role names to agent ids, e.g.
        ``{"researcher": "w1", "planner": "w2", ...}``.
        """
        if pattern_name == "research_plan_code_review":
            return self.research_plan_code_review(
                session_id,
                agent_ids["researcher"],
                agent_ids["planner"],
                agent_ids["coder"],
                agent_ids["reviewer"],
            )
        if pattern_name == "code_review_deploy":
            return self.code_review_deploy(
                session_id,
                agent_ids["coder"],
                agent_ids["reviewer"],
                agent_ids["deployer"],
            )
        if pattern_name == "full_software_lifecycle":
            return self.full_software_lifecycle(
                session_id,
                agent_ids["researcher"],
                agent_ids["planner"],
                agent_ids["coder"],
                agent_ids["tester"],
                agent_ids["reviewer"],
                agent_ids["deployer"],
            )
        if pattern_name == "parallel_research_synthesize":
            return self.parallel_research_synthesize(
                session_id,
                agent_ids["coordinator"],
                (
                    agent_ids["researchers"].split(",")
                    if isinstance(agent_ids["researchers"], str)
                    else agent_ids["researchers"]
                ),
            )
        if pattern_name == "debate_and_vote":
            return self.debate_and_vote(
                session_id,
                (
                    agent_ids["proposers"].split(",")
                    if isinstance(agent_ids["proposers"], str)
                    else agent_ids["proposers"]
                ),
                (
                    agent_ids["voters"].split(",")
                    if isinstance(agent_ids["voters"], str)
                    else agent_ids["voters"]
                ),
            )
        if pattern_name == "round_robin_review":
            return self.round_robin_review(
                session_id,
                (
                    agent_ids["reviewers"].split(",")
                    if isinstance(agent_ids["reviewers"], str)
                    else agent_ids["reviewers"]
                ),
                rounds=int(agent_ids.get("rounds", "1")),
            )
        raise ValueError(f"unknown pattern: {pattern_name}")


__all__ = ["PatternLibrary"]
