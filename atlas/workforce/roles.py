"""Worker roles — specialisations, default skills, and capabilities.

Each :class:`~atlas.workforce.models.WorkerRole` has a default set of
skills, a default priority in the chain of command, and a set of
capabilities (what kinds of tasks the role can accept). This module
is a pure-Python lookup table — no Brain or subsystem imports.
"""

from __future__ import annotations

from atlas.workforce.models import WorkerRole, WorkerSkill

# ===========================================================================
# Chain of command (lower = higher authority)
# ===========================================================================


_CHAIN_OF_COMMAND: dict[str, int] = {
    WorkerRole.CEO.value: 0,
    WorkerRole.CTO.value: 1,
    WorkerRole.PROJECT_MANAGER.value: 2,
    WorkerRole.SOFTWARE_ENGINEER.value: 3,
    WorkerRole.RESEARCH_ENGINEER.value: 3,
    WorkerRole.MINING_ENGINEER.value: 3,
    WorkerRole.DEVOPS_ENGINEER.value: 3,
    WorkerRole.UI_DESIGNER.value: 3,
    WorkerRole.VIDEO_CREATOR.value: 3,
    WorkerRole.TECHNICAL_WRITER.value: 3,
    WorkerRole.QA_ENGINEER.value: 3,
    WorkerRole.KNOWLEDGE_SPECIALIST.value: 4,
    WorkerRole.MEMORY_SPECIALIST.value: 4,
    WorkerRole.VISION_SPECIALIST.value: 4,
    WorkerRole.BROWSER_AGENT.value: 5,
    WorkerRole.GITHUB_AGENT.value: 5,
    WorkerRole.BLENDER_ARTIST.value: 5,
}


def chain_of_command_rank(role: str) -> int:
    """Return the rank of ``role`` in the chain of command.

    Lower numbers represent higher authority. Unknown roles rank last.
    """
    return _CHAIN_OF_COMMAND.get(role, 99)


# ===========================================================================
# Default skills per role
# ===========================================================================


def default_skills(role: str) -> tuple[WorkerSkill, ...]:
    """Return the default skills for ``role``.

    Unknown roles return an empty tuple.
    """
    skills = _DEFAULT_SKILLS.get(role, ())
    return skills


_DEFAULT_SKILLS: dict[str, tuple[WorkerSkill, ...]] = {
    WorkerRole.CEO.value: (
        WorkerSkill(name="strategy", level=0.95),
        WorkerSkill(name="leadership", level=0.95),
        WorkerSkill(name="decision_making", level=0.9),
        WorkerSkill(name="communication", level=0.9),
    ),
    WorkerRole.CTO.value: (
        WorkerSkill(name="architecture", level=0.95),
        WorkerSkill(name="technology_strategy", level=0.9),
        WorkerSkill(name="code_review", level=0.85),
        WorkerSkill(name="leadership", level=0.85),
    ),
    WorkerRole.SOFTWARE_ENGINEER.value: (
        WorkerSkill(name="python", level=0.9),
        WorkerSkill(name="software_design", level=0.85),
        WorkerSkill(name="debugging", level=0.85),
        WorkerSkill(name="testing", level=0.8),
        WorkerSkill(name="git", level=0.8),
    ),
    WorkerRole.RESEARCH_ENGINEER.value: (
        WorkerSkill(name="research", level=0.9),
        WorkerSkill(name="analysis", level=0.85),
        WorkerSkill(name="writing", level=0.8),
        WorkerSkill(name="data_analysis", level=0.85),
    ),
    WorkerRole.MINING_ENGINEER.value: (
        WorkerSkill(name="mining", level=0.9),
        WorkerSkill(name="geology", level=0.85),
        WorkerSkill(name="surpac", level=0.8),
        WorkerSkill(name="autocad", level=0.75),
        WorkerSkill(name="qgis", level=0.75),
    ),
    WorkerRole.UI_DESIGNER.value: (
        WorkerSkill(name="design", level=0.9),
        WorkerSkill(name="figma", level=0.85),
        WorkerSkill(name="canva", level=0.8),
        WorkerSkill(name="photoshop", level=0.8),
        WorkerSkill(name="typography", level=0.85),
    ),
    WorkerRole.VIDEO_CREATOR.value: (
        WorkerSkill(name="video_editing", level=0.9),
        WorkerSkill(name="blender", level=0.85),
        WorkerSkill(name="scripting", level=0.8),
        WorkerSkill(name="storyboarding", level=0.85),
    ),
    WorkerRole.TECHNICAL_WRITER.value: (
        WorkerSkill(name="writing", level=0.95),
        WorkerSkill(name="documentation", level=0.9),
        WorkerSkill(name="editing", level=0.85),
        WorkerSkill(name="markdown", level=0.9),
    ),
    WorkerRole.QA_ENGINEER.value: (
        WorkerSkill(name="testing", level=0.9),
        WorkerSkill(name="qa", level=0.9),
        WorkerSkill(name="debugging", level=0.85),
        WorkerSkill(name="automation", level=0.8),
    ),
    WorkerRole.DEVOPS_ENGINEER.value: (
        WorkerSkill(name="devops", level=0.9),
        WorkerSkill(name="ci_cd", level=0.85),
        WorkerSkill(name="docker", level=0.85),
        WorkerSkill(name="kubernetes", level=0.8),
        WorkerSkill(name="monitoring", level=0.85),
    ),
    WorkerRole.PROJECT_MANAGER.value: (
        WorkerSkill(name="project_management", level=0.9),
        WorkerSkill(name="planning", level=0.9),
        WorkerSkill(name="communication", level=0.9),
        WorkerSkill(name="agile", level=0.85),
    ),
    WorkerRole.KNOWLEDGE_SPECIALIST.value: (
        WorkerSkill(name="knowledge_management", level=0.9),
        WorkerSkill(name="research", level=0.8),
        WorkerSkill(name="indexing", level=0.85),
        WorkerSkill(name="curation", level=0.85),
    ),
    WorkerRole.MEMORY_SPECIALIST.value: (
        WorkerSkill(name="memory_management", level=0.9),
        WorkerSkill(name="categorisation", level=0.85),
        WorkerSkill(name="recall", level=0.85),
        WorkerSkill(name="reflection", level=0.8),
    ),
    WorkerRole.BROWSER_AGENT.value: (
        WorkerSkill(name="browsing", level=0.9),
        WorkerSkill(name="playwright", level=0.85),
        WorkerSkill(name="scraping", level=0.85),
        WorkerSkill(name="form_filling", level=0.8),
    ),
    WorkerRole.GITHUB_AGENT.value: (
        WorkerSkill(name="git", level=0.9),
        WorkerSkill(name="github", level=0.9),
        WorkerSkill(name="pull_requests", level=0.85),
        WorkerSkill(name="issue_tracking", level=0.85),
    ),
    WorkerRole.BLENDER_ARTIST.value: (
        WorkerSkill(name="blender", level=0.95),
        WorkerSkill(name="3d_modeling", level=0.9),
        WorkerSkill(name="rendering", level=0.85),
        WorkerSkill(name="animation", level=0.8),
    ),
    WorkerRole.VISION_SPECIALIST.value: (
        WorkerSkill(name="computer_vision", level=0.9),
        WorkerSkill(name="image_analysis", level=0.9),
        WorkerSkill(name="ocr", level=0.85),
        WorkerSkill(name="object_detection", level=0.85),
    ),
}


# ===========================================================================
# Role capabilities
# ===========================================================================


def can_review(role: str) -> bool:
    """Return ``True`` if ``role`` can review other workers' work."""
    return role in (
        WorkerRole.CEO.value,
        WorkerRole.CTO.value,
        WorkerRole.QA_ENGINEER.value,
        WorkerRole.PROJECT_MANAGER.value,
    )


def can_approve(role: str) -> bool:
    """Return ``True`` if ``role`` can grant approvals."""
    return role in (
        WorkerRole.CEO.value,
        WorkerRole.CTO.value,
        WorkerRole.PROJECT_MANAGER.value,
    )


def can_delegate(role: str) -> bool:
    """Return ``True`` if ``role`` can delegate tasks to other workers."""
    return role in (
        WorkerRole.CEO.value,
        WorkerRole.CTO.value,
        WorkerRole.PROJECT_MANAGER.value,
        WorkerRole.SOFTWARE_ENGINEER.value,
        WorkerRole.RESEARCH_ENGINEER.value,
        WorkerRole.DEVOPS_ENGINEER.value,
    )


def can_lead_team(role: str) -> bool:
    """Return ``True`` if ``role`` can lead a team."""
    return role in (
        WorkerRole.CEO.value,
        WorkerRole.CTO.value,
        WorkerRole.PROJECT_MANAGER.value,
        WorkerRole.SOFTWARE_ENGINEER.value,
        WorkerRole.RESEARCH_ENGINEER.value,
    )


def is_executive(role: str) -> bool:
    """Return ``True`` if ``role`` is an executive (CEO or CTO)."""
    return role in (WorkerRole.CEO.value, WorkerRole.CTO.value)


def is_agent(role: str) -> bool:
    """Return ``True`` if ``role`` is an automated agent."""
    return role in (
        WorkerRole.BROWSER_AGENT.value,
        WorkerRole.GITHUB_AGENT.value,
        WorkerRole.BLENDER_ARTIST.value,
    )


def is_specialist(role: str) -> bool:
    """Return ``True`` if ``role`` is a specialist (non-engineering)."""
    return role in (
        WorkerRole.KNOWLEDGE_SPECIALIST.value,
        WorkerRole.MEMORY_SPECIALIST.value,
        WorkerRole.VISION_SPECIALIST.value,
    )


# ===========================================================================
# Role display
# ===========================================================================


_ROLE_DISPLAY_NAMES: dict[str, str] = {
    WorkerRole.CEO.value: "Chief Executive Officer",
    WorkerRole.CTO.value: "Chief Technology Officer",
    WorkerRole.SOFTWARE_ENGINEER.value: "Software Engineer",
    WorkerRole.RESEARCH_ENGINEER.value: "Research Engineer",
    WorkerRole.MINING_ENGINEER.value: "Mining Engineer",
    WorkerRole.UI_DESIGNER.value: "UI Designer",
    WorkerRole.VIDEO_CREATOR.value: "Video Creator",
    WorkerRole.TECHNICAL_WRITER.value: "Technical Writer",
    WorkerRole.QA_ENGINEER.value: "QA Engineer",
    WorkerRole.DEVOPS_ENGINEER.value: "DevOps Engineer",
    WorkerRole.PROJECT_MANAGER.value: "Project Manager",
    WorkerRole.KNOWLEDGE_SPECIALIST.value: "Knowledge Specialist",
    WorkerRole.MEMORY_SPECIALIST.value: "Memory Specialist",
    WorkerRole.BROWSER_AGENT.value: "Browser Agent",
    WorkerRole.GITHUB_AGENT.value: "GitHub Agent",
    WorkerRole.BLENDER_ARTIST.value: "Blender Artist",
    WorkerRole.VISION_SPECIALIST.value: "Vision Specialist",
}


def display_name(role: str) -> str:
    """Return the human-readable display name for ``role``."""
    return _ROLE_DISPLAY_NAMES.get(role, role.replace("_", " ").title())


def all_roles() -> list[str]:
    """Return all role identifiers in chain-of-command order."""
    return sorted(
        (role.value for role in WorkerRole),
        key=chain_of_command_rank,
    )


__all__ = [
    "all_roles",
    "can_approve",
    "can_delegate",
    "can_lead_team",
    "can_review",
    "chain_of_command_rank",
    "default_skills",
    "display_name",
    "is_agent",
    "is_executive",
    "is_specialist",
]
