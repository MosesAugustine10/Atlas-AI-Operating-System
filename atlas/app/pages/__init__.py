"""Atlas application pages package."""

from __future__ import annotations

from atlas.app.pages.agents_page import AgentsPage
from atlas.app.pages.artifacts_page import ArtifactsPage
from atlas.app.pages.chat_page import ChatPage
from atlas.app.pages.execution_page import ExecutionPage
from atlas.app.pages.knowledge_page import KnowledgePage
from atlas.app.pages.logs_page import LogsPage
from atlas.app.pages.mcp_page import MCPPage
from atlas.app.pages.memory_page import MemoryPage
from atlas.app.pages.providers_page import ProvidersPage
from atlas.app.pages.settings_page import SettingsPage
from atlas.app.pages.system_page import SystemPage
from atlas.app.pages.tools_page import ToolsPage

__all__ = [
    "AgentsPage",
    "ArtifactsPage",
    "ChatPage",
    "ExecutionPage",
    "KnowledgePage",
    "LogsPage",
    "MCPPage",
    "MemoryPage",
    "ProvidersPage",
    "SettingsPage",
    "SystemPage",
    "ToolsPage",
]
