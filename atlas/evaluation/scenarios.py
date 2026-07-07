"""Evaluation scenarios — store of test scenarios.

The :class:`ScenarioStore` manages :class:`Scenario` instances and
ships with built-in scenarios for website generation, research, video
creation, coding, mining, automation, reasoning, collaboration,
knowledge, and memory.
"""

from __future__ import annotations

from atlas.evaluation.models import (
    Scenario,
    ScenarioCategory,
    _new_id,
)

# ---------------------------------------------------------------------------
# Built-in scenarios
# ---------------------------------------------------------------------------


def _builtin_scenarios() -> list[Scenario]:
    """Return the built-in evaluation scenarios."""
    return [
        Scenario(
            id=_new_id("scenario"),
            name="Website: Landing Page",
            category=ScenarioCategory.WEBSITE_GENERATION.value,
            description="Generate a complete landing page for a SaaS product.",
            prompt="Create a landing page for a project management SaaS called TaskFlow.",
            expected_keywords=("TaskFlow", "features", "pricing"),
            difficulty=3,
            tags=("html", "css", "web"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Research: Climate Impact",
            category=ScenarioCategory.RESEARCH.value,
            description="Research the impact of renewable energy on climate change.",
            prompt="Research the impact of renewable energy adoption on global carbon emissions.",
            expected_keywords=("renewable", "carbon", "emissions"),
            difficulty=4,
            tags=("research", "environment"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Video: Explainer Animation",
            category=ScenarioCategory.VIDEO_CREATION.value,
            description="Create a 60-second explainer animation about blockchain.",
            prompt="Create a 60-second animated explainer about how blockchain works.",
            expected_keywords=("blockchain", "blocks", "chain"),
            difficulty=4,
            tags=("video", "animation"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Coding: REST API",
            category=ScenarioCategory.CODING.value,
            description="Implement a REST API for a todo application.",
            prompt="Implement a REST API for a todo application with CRUD operations.",
            expected_keywords=("GET", "POST", "DELETE", "todo"),
            difficulty=3,
            tags=("python", "api", "rest"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Mining: Pit Optimization",
            category=ScenarioCategory.MINING.value,
            description="Analyze an open-pit mine design for optimal extraction.",
            prompt="Analyze the optimal extraction sequence for an open-pit copper mine.",
            expected_keywords=("pit", "extraction", "copper"),
            difficulty=5,
            tags=("mining", "surpac"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Automation: Data Pipeline",
            category=ScenarioCategory.AUTOMATION.value,
            description="Automate a data ETL pipeline from CSV to database.",
            prompt="Automate an ETL pipeline that ingests CSV files and loads them into a database.",
            expected_keywords=("ETL", "CSV", "database", "pipeline"),
            difficulty=3,
            tags=("automation", "data", "etl"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Reasoning: Logic Puzzle",
            category=ScenarioCategory.REASONING.value,
            description="Solve a multi-step logic puzzle.",
            prompt="Solve: Three people check into a hotel. The clerk charges $30. Later the clerk realizes the room is only $25 and sends $5 back. The bellhop keeps $2 and gives $1 to each guest. Each guest paid $9 ($27 total) plus the bellhop's $2 = $29. Where is the missing dollar?",
            expected_keywords=("missing", "dollar", "math"),
            difficulty=4,
            tags=("logic", "puzzle"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Collaboration: Multi-Agent Code Review",
            category=ScenarioCategory.COLLABORATION.value,
            description="Multiple agents collaborate to review and improve code.",
            prompt="Have a coder, reviewer, and tester collaborate to implement and validate a sorting algorithm.",
            expected_keywords=("sort", "review", "test"),
            difficulty=4,
            tags=("multi-agent", "code-review"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Knowledge: Fact Synthesis",
            category=ScenarioCategory.KNOWLEDGE.value,
            description="Synthesize knowledge from multiple sources.",
            prompt="Synthesize the key differences between supervised and unsupervised learning.",
            expected_keywords=("supervised", "unsupervised", "learning"),
            difficulty=3,
            tags=("ml", "knowledge"),
        ),
        Scenario(
            id=_new_id("scenario"),
            name="Memory: Context Recall",
            category=ScenarioCategory.MEMORY.value,
            description="Recall and integrate prior context into a response.",
            prompt="Given a conversation history about a project called Atlas, recall the key decisions and summarize them.",
            expected_keywords=("Atlas", "decisions", "summary"),
            difficulty=3,
            tags=("memory", "recall"),
        ),
    ]


class ScenarioStore:
    """Manages evaluation scenarios."""

    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}

    def add(self, scenario: Scenario) -> Scenario:
        """Register a scenario."""
        self._scenarios[scenario.id] = scenario
        return scenario

    def create(
        self,
        name: str,
        category: str = ScenarioCategory.REASONING.value,
        description: str = "",
        prompt: str = "",
        expected_output: str = "",
        expected_keywords: tuple[str, ...] = (),
        difficulty: int = 3,
        tags: tuple[str, ...] = (),
    ) -> Scenario:
        """Create and register a new scenario."""
        scenario = Scenario(
            id=_new_id("scenario"),
            name=name,
            category=category,
            description=description,
            prompt=prompt,
            expected_output=expected_output,
            expected_keywords=expected_keywords,
            difficulty=difficulty,
            tags=tags,
        )
        self._scenarios[scenario.id] = scenario
        return scenario

    def get(self, scenario_id: str) -> Scenario | None:
        """Return the scenario with ``scenario_id`` or ``None``."""
        return self._scenarios.get(scenario_id)

    def list_scenarios(
        self,
        category: str | None = None,
        tag: str | None = None,
        difficulty: int | None = None,
    ) -> list[Scenario]:
        """List scenarios with optional filters."""
        scenarios = list(self._scenarios.values())
        if category is not None:
            scenarios = [s for s in scenarios if s.category == category]
        if tag is not None:
            scenarios = [s for s in scenarios if tag in s.tags]
        if difficulty is not None:
            scenarios = [s for s in scenarios if s.difficulty == difficulty]
        return scenarios

    def count(self) -> int:
        """Return the total number of scenarios."""
        return len(self._scenarios)

    def categories(self) -> list[str]:
        """Return the unique categories present."""
        seen: list[str] = []
        for s in self._scenarios.values():
            if s.category not in seen:
                seen.append(s.category)
        return seen

    def remove(self, scenario_id: str) -> bool:
        """Remove a scenario. Returns ``True`` if removed."""
        return self._scenarios.pop(scenario_id, None) is not None

    def load_builtins(self) -> list[Scenario]:
        """Load the built-in scenarios and return them."""
        builtins = _builtin_scenarios()
        for scenario in builtins:
            self._scenarios[scenario.id] = scenario
        return builtins


__all__ = ["ScenarioStore"]
