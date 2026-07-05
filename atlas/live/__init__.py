"""Atlas Live Runtime — real execution integration layer.

This package wires every existing Atlas subsystem into a live execution
pipeline. It does NOT duplicate functionality — it orchestrates the
existing MCP, Provider, Memory, Knowledge, Execution, and Intelligence
layers through real connectors, real providers, and real storage.

Phases:

1. Real provider execution (Ollama, OpenRouter, Z.ai)
2. Real MCP execution (dispatch through MCPManager)
3. Live memory (auto-store everything)
4. Live knowledge (auto-index generated files)
5. Live agents (10 agents that do real work)
6. Multi-agent collaboration
7. Streaming progress
8. Unified event bus
9. Artifact management
10. Dashboard API (FastAPI)

Dependency graph (acyclic):

* ``event_bus`` — depends on ``atlas.runtime.events``.
* ``artifact_manager`` — leaf.
* ``provider_adapter`` — depends on ``atlas.providers``, ``atlas.mcp``.
* ``executor_bridge`` — depends on ``atlas.mcp``.
* ``memory_integration`` — depends on ``event_bus``.
* ``knowledge_indexer`` — depends on ``event_bus``.
* ``streaming`` — depends on ``event_bus``.
"""

from __future__ import annotations

from atlas.live.artifact_manager import (
    EXTENSION_MAP,
    Artifact,
    ArtifactManager,
    ArtifactType,
)
from atlas.live.event_bus import (
    ArtifactCreated,
    ConnectorConnected,
    ConnectorDisconnected,
    GoalFinished,
    GoalStarted,
    KnowledgeIndexed,
    LiveEvent,
    LiveEventBus,
    MemoryStored,
    ProviderFailed,
    ProviderSelected,
    StreamProgress,
    TaskCompleted,
    TaskStarted,
    WorkflowFinished,
    WorkflowStarted,
)
from atlas.live.executor_bridge import MCPExecutorBridge
from atlas.live.knowledge_indexer import INDEXABLE_EXTENSIONS, KnowledgeIndexer
from atlas.live.memory_integration import MemoryIntegrator
from atlas.live.provider_adapter import (
    OllamaProvider,
    OpenRouterProvider,
    ZAIProvider,
    create_live_providers,
    register_live_providers,
)
from atlas.live.streaming import StreamManager, default_progress_stages

__all__ = [
    "Artifact",
    "ArtifactCreated",
    "ArtifactManager",
    "ArtifactType",
    "ConnectorConnected",
    "ConnectorDisconnected",
    "EXTENSION_MAP",
    "GoalFinished",
    "GoalStarted",
    "INDEXABLE_EXTENSIONS",
    "KnowledgeIndexed",
    "KnowledgeIndexer",
    "LiveEvent",
    "LiveEventBus",
    "MCPExecutorBridge",
    "MemoryIntegrator",
    "MemoryStored",
    "OllamaProvider",
    "OpenRouterProvider",
    "ProviderFailed",
    "ProviderSelected",
    "StreamManager",
    "StreamProgress",
    "TaskCompleted",
    "TaskStarted",
    "WorkflowFinished",
    "WorkflowStarted",
    "ZAIProvider",
    "create_live_providers",
    "default_progress_stages",
    "register_live_providers",
]
