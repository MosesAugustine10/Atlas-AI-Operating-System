"""Agent definitions for the Atlas AI Operating System.

Provides :class:`BaseAgent` (abstract lifecycle), :class:`LiveAgent`
(real execution with dependency injection), and 11 concrete agents:

* :class:`CodingAgent` — code generation, debugging, refactoring, testing
* :class:`ResearchAgent` — web research, summarization, citations
* :class:`GitHubAgent` — commit, branch, merge, PR, repo management
* :class:`BrowserAgent` — browsing, scraping, form filling
* :class:`MiningAgent` — Surpac, AutoCAD, QGIS
* :class:`VisionAgent` — OCR, image analysis
* :class:`WindowsAgent` — filesystem, terminal, automation
* :class:`PlannerAgent` — planning, decomposition
* :class:`MemoryAgent` — recall, remember
* :class:`KnowledgeAgent` — indexing, retrieval
* :class:`BlenderAgent` — rendering, scene generation

Each agent exposes: ``execute()``, ``supports()``, ``estimate()``,
``health()``, ``statistics()``, and ``execute_stream()``.
"""

from __future__ import annotations

from atlas.agents.base import BaseAgent
from atlas.agents.live import (
    ALL_LIVE_AGENTS,
    AgentMetrics,
    BlenderAgent,
    BrowserAgent,
    CodingAgent,
    GitHubAgent,
    KnowledgeAgent,
    LiveAgent,
    MemoryAgent,
    MiningAgent,
    PlannerAgent,
    ResearchAgent,
    VisionAgent,
    WindowsAgent,
    instantiate_all_agents,
)

__all__ = [
    "ALL_LIVE_AGENTS",
    "AgentMetrics",
    "BaseAgent",
    "BlenderAgent",
    "BrowserAgent",
    "CodingAgent",
    "GitHubAgent",
    "KnowledgeAgent",
    "LiveAgent",
    "MemoryAgent",
    "MiningAgent",
    "PlannerAgent",
    "ResearchAgent",
    "VisionAgent",
    "WindowsAgent",
    "instantiate_all_agents",
]
