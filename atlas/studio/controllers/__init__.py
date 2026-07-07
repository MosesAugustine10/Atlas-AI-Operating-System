"""Studio controllers package — re-exports every ViewModel controller.

Each controller adapts an Atlas subsystem (brain, providers, MCP, memory,
knowledge, artifacts, ...) into Studio view-models. All controllers
accept their wrapped subsystem via an optional constructor parameter and
degrade gracefully (returning empty results) when that subsystem is
``None``.
"""

from __future__ import annotations

from atlas.studio.controllers.agent_controller import AgentController
from atlas.studio.controllers.artifact_controller import ArtifactController
from atlas.studio.controllers.chat_controller import ChatController
from atlas.studio.controllers.execution_controller import ExecutionController
from atlas.studio.controllers.knowledge_controller import KnowledgeController
from atlas.studio.controllers.mcp_controller import MCPController
from atlas.studio.controllers.memory_controller import MemoryController
from atlas.studio.controllers.plugin_controller import PluginController
from atlas.studio.controllers.provider_controller import ProviderController
from atlas.studio.controllers.system_controller import SystemController

__all__ = [
    "AgentController",
    "ArtifactController",
    "ChatController",
    "ExecutionController",
    "KnowledgeController",
    "MCPController",
    "MemoryController",
    "PluginController",
    "ProviderController",
    "SystemController",
]
