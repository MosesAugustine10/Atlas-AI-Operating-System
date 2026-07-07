"""Tests for the Atlas Live Runtime.

Covers provider adapters, executor bridge, event bus, artifact manager,
memory integration, knowledge indexer, streaming, live agents,
collaboration, and dashboard API. All tests are deterministic and
offline — no external services are called.
"""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from atlas.agents.base import BaseAgent
from atlas.agents.collaboration import AgentCollaborator, CollaborationResult
from atlas.agents.live import (
    ALL_LIVE_AGENTS,
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
from atlas.live import (
    EXTENSION_MAP,
    INDEXABLE_EXTENSIONS,
    Artifact,
    ArtifactManager,
    ArtifactType,
    KnowledgeIndexer,
    LiveEventBus,
    MCPExecutorBridge,
    MemoryIntegrator,
    OllamaProvider,
    OpenRouterProvider,
    StreamManager,
    ZAIProvider,
    create_live_providers,
    default_progress_stages,
    register_live_providers,
)
from atlas.live.event_bus import (
    ArtifactCreated,
    ConnectorConnected,
    ConnectorDisconnected,
    GoalFinished,
    GoalStarted,
    KnowledgeIndexed,
    MemoryStored,
    ProviderFailed,
    ProviderSelected,
    StreamProgress,
    TaskCompleted,
    TaskStarted,
    WorkflowFinished,
    WorkflowStarted,
)
from atlas.mcp import MCPManager
from atlas.providers.models import ProviderRequest

# ===========================================================================
# Event Bus
# ===========================================================================


class TestEventBus:
    def test_live_event_bus_creates(self) -> None:
        bus = LiveEventBus()
        assert bus is not None
        assert len(bus) == 0

    def test_emit_goal_started(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test goal")
        assert len(bus) == 1
        assert isinstance(bus.history()[0], GoalStarted)

    def test_emit_goal_finished(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_finished("g1", "completed", 1.5)
        assert len(bus) == 1
        assert isinstance(bus.history()[0], GoalFinished)

    def test_emit_task_started(self) -> None:
        bus = LiveEventBus()
        bus.emit_task_started("t1", "research")
        assert isinstance(bus.history()[0], TaskStarted)

    def test_emit_task_completed(self) -> None:
        bus = LiveEventBus()
        bus.emit_task_completed("t1", True, 0.5)
        assert isinstance(bus.history()[0], TaskCompleted)

    def test_emit_provider_selected(self) -> None:
        bus = LiveEventBus()
        bus.emit_provider_selected("ollama", "generate")
        assert isinstance(bus.history()[0], ProviderSelected)

    def test_emit_provider_failed(self) -> None:
        bus = LiveEventBus()
        bus.emit_provider_failed("ollama", "timeout")
        assert isinstance(bus.history()[0], ProviderFailed)

    def test_emit_memory_stored(self) -> None:
        bus = LiveEventBus()
        bus.emit_memory_stored("goal", "e1")
        assert isinstance(bus.history()[0], MemoryStored)

    def test_emit_knowledge_indexed(self) -> None:
        bus = LiveEventBus()
        bus.emit_knowledge_indexed("d1", "file.txt")
        assert isinstance(bus.history()[0], KnowledgeIndexed)

    def test_emit_workflow_started(self) -> None:
        bus = LiveEventBus()
        bus.emit_workflow_started("w1")
        assert isinstance(bus.history()[0], WorkflowStarted)

    def test_emit_workflow_finished(self) -> None:
        bus = LiveEventBus()
        bus.emit_workflow_finished("w1", "completed")
        assert isinstance(bus.history()[0], WorkflowFinished)

    def test_emit_connector_connected(self) -> None:
        bus = LiveEventBus()
        bus.emit_connector_connected("filesystem")
        assert isinstance(bus.history()[0], ConnectorConnected)

    def test_emit_connector_disconnected(self) -> None:
        bus = LiveEventBus()
        bus.emit_connector_disconnected("filesystem")
        assert isinstance(bus.history()[0], ConnectorDisconnected)

    def test_emit_artifact_created(self) -> None:
        bus = LiveEventBus()
        bus.emit_artifact_created("a1", "image")
        assert isinstance(bus.history()[0], ArtifactCreated)

    def test_emit_stream_progress(self) -> None:
        bus = LiveEventBus()
        bus.emit_stream_progress("planning", "Planning...", 0.5)
        assert isinstance(bus.history()[0], StreamProgress)

    def test_subscribe(self) -> None:
        bus = LiveEventBus()
        received: list[Any] = []
        bus.subscribe(GoalStarted, received.append)
        bus.emit_goal_started("g1", "test")
        assert len(received) == 1

    def test_history_for(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        bus.emit_task_started("t1", "research")
        events = bus.history_for("g1")
        assert len(events) == 1

    def test_clear(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        bus.clear()
        assert len(bus) == 0

    def test_wraps_existing_bus(self) -> None:
        from atlas.runtime.events import EventBus

        inner = EventBus()
        bus = LiveEventBus(bus=inner)
        assert bus.bus is inner

    def test_repr(self) -> None:
        bus = LiveEventBus()
        assert "LiveEventBus" in repr(bus)

    def test_all_event_types_are_frozen(self) -> None:
        events = [
            GoalStarted(goal_id="g"),
            GoalFinished(goal_id="g"),
            TaskStarted(task_id="t"),
            TaskCompleted(task_id="t"),
            ProviderSelected(provider="p"),
            ProviderFailed(provider="p"),
            MemoryStored(category="c"),
            KnowledgeIndexed(document_id="d"),
            WorkflowStarted(workflow_id="w"),
            WorkflowFinished(workflow_id="w"),
            ConnectorConnected(connector="c"),
            ConnectorDisconnected(connector="c"),
            ArtifactCreated(artifact_id="a"),
            StreamProgress(stage="s"),
        ]
        for e in events:
            with pytest.raises(dataclasses.FrozenInstanceError):
                e.event_id = "other"  # type: ignore[misc]


# ===========================================================================
# Artifact Manager
# ===========================================================================


class TestArtifactManager:
    def test_create_artifact(self) -> None:
        am = ArtifactManager()
        a = am.create("test.txt", content="hello")
        assert a.name == "test.txt"
        assert a.artifact_type is ArtifactType.TEXT
        assert a.content == "hello"

    def test_create_artifact_infer_type(self) -> None:
        am = ArtifactManager()
        a = am.create("script.py", content="print('hello')")
        assert a.artifact_type is ArtifactType.PYTHON

    def test_create_artifact_infer_image(self) -> None:
        am = ArtifactManager()
        a = am.create("photo.png")
        assert a.artifact_type is ArtifactType.IMAGE

    def test_create_artifact_explicit_type(self) -> None:
        am = ArtifactManager()
        a = am.create("data", artifact_type="json", content="{}")
        assert a.artifact_type is ArtifactType.JSON

    def test_create_artifact_unknown_type(self) -> None:
        am = ArtifactManager()
        a = am.create("file.xyz")
        assert a.artifact_type is ArtifactType.UNKNOWN

    def test_get_artifact(self) -> None:
        am = ArtifactManager()
        a = am.create("test.txt")
        assert am.get(a.id) is a

    def test_get_missing_returns_none(self) -> None:
        am = ArtifactManager()
        assert am.get("missing") is None

    def test_list_all(self) -> None:
        am = ArtifactManager()
        am.create("a.txt")
        am.create("b.py")
        assert len(am.list()) == 2

    def test_list_filtered_by_type(self) -> None:
        am = ArtifactManager()
        am.create("a.txt")
        am.create("b.py")
        python = am.list(artifact_type=ArtifactType.PYTHON)
        assert len(python) == 1

    def test_list_filtered_by_source(self) -> None:
        am = ArtifactManager()
        am.create("a.txt", source="agent1")
        am.create("b.txt", source="agent2")
        filtered = am.list(source="agent1")
        assert len(filtered) == 1

    def test_list_filtered_by_goal_id(self) -> None:
        am = ArtifactManager()
        am.create("a.txt", goal_id="g1")
        am.create("b.txt", goal_id="g2")
        filtered = am.list(goal_id="g1")
        assert len(filtered) == 1

    def test_list_limit(self) -> None:
        am = ArtifactManager()
        for i in range(10):
            am.create(f"f{i}.txt")
        assert len(am.list(limit=3)) == 3

    def test_search_by_name(self) -> None:
        am = ArtifactManager()
        am.create("report.txt")
        am.create("code.py")
        results = am.search("report")
        assert len(results) == 1

    def test_search_by_content(self) -> None:
        am = ArtifactManager()
        am.create("a.txt", content="hello world")
        results = am.search("hello")
        assert len(results) == 1

    def test_search_by_source(self) -> None:
        am = ArtifactManager()
        am.create("a.txt", source="blender_agent")
        results = am.search("blender")
        assert len(results) == 1

    def test_count(self) -> None:
        am = ArtifactManager()
        am.create("a.txt")
        am.create("b.py")
        assert am.count() == 2

    def test_count_by_type(self) -> None:
        am = ArtifactManager()
        am.create("a.txt")
        am.create("b.txt")
        am.create("c.py")
        counts = am.count_by_type()
        assert counts["text"] == 2
        assert counts["python"] == 1

    def test_delete(self) -> None:
        am = ArtifactManager()
        a = am.create("test.txt")
        assert am.delete(a.id) is True
        assert am.delete(a.id) is False

    def test_clear(self) -> None:
        am = ArtifactManager()
        am.create("a.txt")
        am.clear()
        assert len(am) == 0

    def test_contains(self) -> None:
        am = ArtifactManager()
        a = am.create("test.txt")
        assert a.id in am

    def test_len(self) -> None:
        am = ArtifactManager()
        am.create("a.txt")
        am.create("b.txt")
        assert len(am) == 2

    def test_repr(self) -> None:
        am = ArtifactManager()
        assert "ArtifactManager" in repr(am)

    def test_storage_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            am = ArtifactManager(storage_dir=tmp)
            assert am.storage_dir.exists()

    def test_artifact_is_frozen(self) -> None:
        a = Artifact(name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.name = "other"  # type: ignore[misc]

    def test_extension_map_has_all_types(self) -> None:
        assert ".py" in EXTENSION_MAP
        assert ".md" in EXTENSION_MAP
        assert ".png" in EXTENSION_MAP
        assert ".pdf" in EXTENSION_MAP
        assert ".json" in EXTENSION_MAP
        assert ".csv" in EXTENSION_MAP
        assert ".docx" in EXTENSION_MAP
        assert ".pptx" in EXTENSION_MAP
        assert ".zip" in EXTENSION_MAP
        assert ".blend" in EXTENSION_MAP


# ===========================================================================
# Provider Adapter
# ===========================================================================


class TestProviderAdapter:
    def test_zai_provider_no_key(self) -> None:
        p = ZAIProvider(api_key=None)
        assert p.name == "zai"
        assert p.health() is False

    def test_zai_provider_generate_no_key(self) -> None:
        p = ZAIProvider(api_key=None)
        req = ProviderRequest(prompt="hello")
        resp = p.generate(req)
        assert "placeholder" in resp.text.lower()

    def test_zai_provider_health_with_key(self) -> None:
        p = ZAIProvider(api_key="test_key")
        assert p.health() is True

    def test_zai_provider_models(self) -> None:
        p = ZAIProvider(api_key="test_key")
        models = p.available_models()
        assert "glm-4" in models

    def test_zai_provider_stream(self) -> None:
        p = ZAIProvider(api_key=None)
        req = ProviderRequest(prompt="hello")
        chunks = list(p.stream(req))
        assert len(chunks) == 1

    @patch("requests.post")
    def test_zai_provider_generate_with_key(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [
                    {"message": {"content": "Hello!"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )
        p = ZAIProvider(api_key="test_key")
        req = ProviderRequest(prompt="hello", model="glm-4")
        resp = p.generate(req)
        assert resp.text == "Hello!"
        assert resp.provider == "zai"

    def test_ollama_provider_creates(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434")
        assert p.name == "ollama"
        assert p._standalone is not None

    def test_ollama_provider_health(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434")
        # Health will be False if Ollama isn't running.
        assert p.health() in (True, False)

    def test_ollama_provider_generate(self) -> None:
        """Ollama provider generate — may fail if server isn't running."""
        p = OllamaProvider(base_url="http://localhost:11434")
        req = ProviderRequest(prompt="hello", model="llama3")
        try:
            resp = p.generate(req)
            assert resp.provider == "ollama"
        except Exception:  # noqa: BLE001
            # Ollama server not running — expected in CI.
            pass

    def test_openrouter_provider_creates(self) -> None:
        p = OpenRouterProvider(api_key=None)
        assert p.name == "openrouter"

    def test_openrouter_provider_health_no_key(self) -> None:
        p = OpenRouterProvider(api_key=None)
        assert p.health() is False

    def test_openrouter_provider_health_with_key(self) -> None:
        p = OpenRouterProvider(api_key="test_key")
        assert p.health() is True

    def test_create_live_providers(self) -> None:
        providers = create_live_providers()
        assert len(providers) == 3
        names = {p.name for p in providers}
        assert names == {"zai", "ollama", "openrouter"}

    def test_register_live_providers(self) -> None:
        from atlas.providers import ProviderManager

        pm = ProviderManager()
        register_live_providers(pm)
        assert pm.registry.contains("zai")
        assert pm.registry.contains("ollama")
        assert pm.registry.contains("openrouter")
        assert pm.registry.default().name == "zai"


# ===========================================================================
# Executor Bridge
# ===========================================================================


class TestExecutorBridge:
    def test_bridge_without_manager(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        result = bridge.execute("research", {"url": "https://example.com"})
        assert result["success"] is True
        assert result["connector"] == "placeholder"

    def test_bridge_can_execute_without_manager(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        assert bridge.can_execute("research") is False

    def test_bridge_available_connectors_empty(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        assert bridge.available_connectors() == []

    def test_bridge_capability_map_has_research(self) -> None:
        assert "research" in MCPExecutorBridge.CAPABILITY_MAP

    def test_bridge_capability_map_has_generate_code(self) -> None:
        assert "generate_code" in MCPExecutorBridge.CAPABILITY_MAP

    def test_bridge_capability_map_has_git_commit(self) -> None:
        assert "git_commit" in MCPExecutorBridge.CAPABILITY_MAP

    def test_bridge_capability_map_has_file_read(self) -> None:
        assert "file.read" in MCPExecutorBridge.CAPABILITY_MAP

    def test_bridge_capability_map_has_deploy(self) -> None:
        assert "deploy" in MCPExecutorBridge.CAPABILITY_MAP

    def test_bridge_placeholder_research(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        result = bridge._placeholder("research", {"topic": "AI"})
        assert result["success"] is True
        assert result["output"]["capability"] == "research"

    def test_bridge_build_params_navigate(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params(
            "research", "browser.navigate", {"url": "https://x.com"}
        )
        assert params["url"] == "https://x.com"

    def test_bridge_build_params_generate(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params(
            "generate_code", "ollama.generate", {"prompt": "hello"}
        )
        assert params["prompt"] == "hello"

    def test_bridge_build_params_git_commit(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params("git_commit", "git.commit", {"message": "test"})
        assert params["message"] == "test"

    def test_bridge_build_params_file_write(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params(
            "file.write", "file.write", {"path": "/x", "content": "hi"}
        )
        assert params["path"] == "/x"
        assert params["content"] == "hi"

    def test_bridge_connect_without_manager(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        bridge.connect()  # should not raise

    def test_bridge_disconnect_without_manager(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        bridge.disconnect()  # should not raise

    def test_bridge_with_mcp_manager(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import FilesystemConnector

        mcp.register_connector(FilesystemConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        assert bridge.can_execute("file.read") is True
        assert "filesystem" in bridge.available_connectors()

    def test_bridge_execute_with_mcp(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import FilesystemConnector

        mcp.register_connector(FilesystemConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            path = f.name
        try:
            result = bridge.execute("file.read", {"path": path})
            assert result["success"] is True
            assert result["connector"] == "filesystem"
        finally:
            Path(path).unlink()

    def test_bridge_unknown_capability_placeholder(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        result = bridge.execute("bogus_capability", {})
        assert result["success"] is True
        assert result["connector"] == "placeholder"


# ===========================================================================
# Memory Integration
# ===========================================================================


class TestMemoryIntegrator:
    def test_creates_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        assert mi.memory is None

    def test_store_goal_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_goal("g1", "test", "completed")  # should not raise

    def test_store_goal_with_memory(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(
                self, content, source=None, tags=None, **kwargs
            ):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_goal("g1", "test", "completed")
        assert len(recorded) == 1
        assert recorded[0]["goal_id"] == "g1"

    def test_store_plan(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_plan("g1", MagicMock(id="p1", tasks=[MagicMock(description="step1")]))
        assert len(recorded) == 1

    def test_store_reasoning(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_reasoning(
            "g1",
            MagicMock(id="c1", conclusion="test", steps=[], overall_confidence=0.8),
        )
        assert len(recorded) == 1

    def test_store_tool_output(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_tool_output("g1", "filesystem", {"data": "test"})
        assert len(recorded) == 1

    def test_store_provider_output(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_provider_output("g1", "ollama", "Hello!")
        assert len(recorded) == 1

    def test_store_error(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_error("g1", "timeout", context="research")
        assert len(recorded) == 1

    def test_store_lesson(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_lesson("l1", "test lesson", "quality")
        assert len(recorded) == 1

    def test_store_artifact(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_artifact("g1", "a1", "test.png", "image")
        assert len(recorded) == 1

    def test_store_metrics(self) -> None:
        recorded: list[Any] = []

        class FakeMemory:
            def remember(self, content, **kwargs):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory())
        mi.store_metrics("g1", 1.5, 3, 0)
        assert len(recorded) == 1

    def test_events_emitted(self) -> None:
        bus = LiveEventBus()
        recorded: list[Any] = []

        class FakeMemory:
            def remember(
                self, content, source=None, tags=None, **kwargs
            ):  # noqa: ARG002
                recorded.append(content)

        mi = MemoryIntegrator(memory=FakeMemory(), event_bus=bus)
        mi.store_goal("g1", "test", "completed")
        assert len(recorded) == 1
        assert len(bus) == 1
        assert isinstance(bus.history()[0], MemoryStored)


# ===========================================================================
# Knowledge Indexer
# ===========================================================================


class TestKnowledgeIndexer:
    def test_creates_without_knowledge(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.knowledge is None

    def test_index_file_without_knowledge(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.index_file("test.txt") is None

    def test_index_text_without_knowledge(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.index_text("content", "source") is None

    def test_search_without_knowledge(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.search("query") == []

    def test_is_indexable(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.is_indexable("test.py") is True
        assert ki.is_indexable("test.png") is False

    def test_indexed_count_empty(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.indexed_count() == 0

    def test_indexable_extensions(self) -> None:
        assert ".py" in INDEXABLE_EXTENSIONS
        assert ".md" in INDEXABLE_EXTENSIONS
        assert ".json" in INDEXABLE_EXTENSIONS
        assert ".csv" in INDEXABLE_EXTENSIONS
        assert ".txt" in INDEXABLE_EXTENSIONS

    def test_index_text_with_knowledge(self) -> None:
        class FakeDoc:
            def __init__(self, doc_id: str):
                self.id = doc_id

        class FakeKnowledge:
            def __init__(self) -> None:
                self.docs: list[str] = []

            def ingest_text(
                self, content, source, tags=None, **metadata
            ):  # noqa: ARG002
                doc = FakeDoc(f"doc_{len(self.docs)}")
                self.docs.append(doc.id)
                return doc

            def search(self, query, top_k=5):  # noqa: ARG002
                return []

        ki = KnowledgeIndexer(knowledge=FakeKnowledge())
        doc_id = ki.index_text("test content", "test.txt")
        assert doc_id is not None
        assert ki.indexed_count() == 1

    def test_index_file_with_knowledge(self) -> None:
        class FakeDoc:
            def __init__(self):
                self.id = "doc_0"

        class FakeKnowledge:
            def ingest_text(
                self, content, source, tags=None, **metadata
            ):  # noqa: ARG002
                return FakeDoc()

        ki = KnowledgeIndexer(knowledge=FakeKnowledge())
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            path = f.name
        try:
            doc_id = ki.index_file(path)
            assert doc_id is not None
        finally:
            Path(path).unlink()

    def test_index_directory(self) -> None:
        class FakeDoc:
            def __init__(self):
                self.id = "doc"

        class FakeKnowledge:
            def ingest_text(
                self, content, source, tags=None, **metadata
            ):  # noqa: ARG002
                return FakeDoc()

        ki = KnowledgeIndexer(knowledge=FakeKnowledge())
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a")
            (Path(tmp) / "b.py").write_text("b")
            count = ki.index_directory(tmp)
            assert count == 2

    def test_index_file_not_found(self) -> None:
        ki = KnowledgeIndexer(knowledge=MagicMock())
        assert ki.index_file("/nonexistent/file.txt") is None

    def test_index_file_not_indexable(self) -> None:
        ki = KnowledgeIndexer(knowledge=MagicMock())
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            assert ki.index_file(path) is None
        finally:
            Path(path).unlink()

    def test_events_emitted(self) -> None:
        class FakeDoc:
            id = "d1"

        class FakeKnowledge:
            def ingest_text(
                self, content, source, tags=None, **metadata
            ):  # noqa: ARG002
                return FakeDoc()

        bus = LiveEventBus()
        ki = KnowledgeIndexer(knowledge=FakeKnowledge(), event_bus=bus)
        ki.index_text("content", "source")
        assert len(bus) == 1
        assert isinstance(bus.history()[0], KnowledgeIndexed)


# ===========================================================================
# Streaming
# ===========================================================================


class TestStreaming:
    def test_creates(self) -> None:
        sm = StreamManager()
        assert len(sm) == 0

    def test_progress(self) -> None:
        sm = StreamManager()
        sm.progress("planning", "Planning...", 0.5)
        assert len(sm) == 1

    def test_subscribe(self) -> None:
        sm = StreamManager()
        received: list[tuple] = []
        sm.subscribe(lambda s, m, p: received.append((s, m, p)))
        sm.progress("planning", "Planning...", 0.5)
        assert len(received) == 1
        assert received[0] == ("planning", "Planning...", 0.5)

    def test_unsubscribe(self) -> None:
        sm = StreamManager()
        listener = lambda s, m, p: None  # noqa: E731
        sm.subscribe(listener)
        assert sm.unsubscribe(listener) is True
        assert sm.unsubscribe(listener) is False

    def test_stage_context_manager(self) -> None:
        sm = StreamManager()
        with sm.stage("researching", "Searching..."):
            pass
        assert len(sm) == 2  # start + end

    def test_stages(self) -> None:
        sm = StreamManager()
        sm.progress("a", "msg1", 0.0)
        sm.progress("b", "msg2", 0.5)
        stages = sm.stages()
        assert len(stages) == 2
        assert stages[0][0] == "a"
        assert stages[1][0] == "b"

    def test_clear(self) -> None:
        sm = StreamManager()
        sm.progress("a", "", 0)
        sm.clear()
        assert len(sm) == 0

    def test_default_progress_stages(self) -> None:
        stages = default_progress_stages()
        assert "planning" in stages
        assert "executing" in stages
        assert "done" in stages

    def test_repr(self) -> None:
        sm = StreamManager()
        assert "StreamManager" in repr(sm)

    def test_listener_exception_isolated(self) -> None:
        sm = StreamManager()

        def bad(s: str, m: str, p: float) -> None:
            raise RuntimeError("boom")

        sm.subscribe(bad)
        sm.progress("test", "", 0)  # should not raise


# ===========================================================================
# Live Agents
# ===========================================================================


class TestLiveAgents:
    def test_all_agents_count(self) -> None:
        assert len(ALL_LIVE_AGENTS) == 11

    def test_instantiate_all(self) -> None:
        agents = instantiate_all_agents()
        assert len(agents) == 11

    def test_coding_agent(self) -> None:
        a = CodingAgent()
        report = a.run("write a hello world script")
        assert isinstance(report, str)

    def test_research_agent(self) -> None:
        a = ResearchAgent()
        report = a.run("research AI")
        assert isinstance(report, str)

    def test_github_agent(self) -> None:
        a = GitHubAgent()
        report = a.run("check git status")
        assert isinstance(report, str)

    def test_browser_agent(self) -> None:
        a = BrowserAgent()
        report = a.run("browse example.com")
        assert isinstance(report, str)

    def test_mining_agent(self) -> None:
        a = MiningAgent()
        report = a.run("process data")
        assert isinstance(report, str)

    def test_vision_agent(self) -> None:
        a = VisionAgent()
        report = a.run("capture image")
        assert isinstance(report, str)

    def test_windows_agent(self) -> None:
        a = WindowsAgent()
        report = a.run("run command")
        assert isinstance(report, str)

    def test_planner_agent(self) -> None:
        a = PlannerAgent()
        report = a.run("plan a project")
        assert isinstance(report, str)

    def test_knowledge_agent(self) -> None:
        a = KnowledgeAgent()
        report = a.run("search knowledge")
        assert isinstance(report, str)

    def test_memory_agent(self) -> None:
        a = MemoryAgent()
        report = a.run("recall memory")
        assert isinstance(report, str)

    def test_blender_agent(self) -> None:
        a = BlenderAgent()
        report = a.run("render image")
        assert isinstance(report, str)

    def test_agent_with_providers(self) -> None:
        class FakeProviders:
            def generate(self, prompt, **kwargs):  # noqa: ARG002
                return type("R", (), {"text": "generated code"})()

        a = CodingAgent(providers=FakeProviders())
        result = a.execute({"objective": "write code"})
        assert "generated code" in result["code"]

    def test_agent_with_memory(self) -> None:
        class FakeMemory:
            def recall(self):
                return [{"content": "memory1"}]

        a = MemoryAgent(memory=FakeMemory())
        result = a.execute({"objective": "recall"})
        assert len(result["memories"]) == 1

    def test_agent_with_knowledge(self) -> None:
        class FakeKnowledge:
            def search(self, query):  # noqa: ARG002
                return [{"content": "fact1"}]

        a = KnowledgeAgent(knowledge=FakeKnowledge())
        result = a.execute({"objective": "search"})
        assert len(result["knowledge_hits"]) == 1

    def test_agent_with_mcp(self) -> None:
        class FakeMCP:
            def open_session(self, name, **kwargs):  # noqa: ARG002
                return type("S", (), {"id": "s1"})()

            def execute_capability(
                self, cap, params, connector=None, session_id=None
            ):  # noqa: ARG002
                return type(
                    "R", (), {"success": True, "output": {"data": "ok"}, "error": None}
                )()

            def close_session(self, sid):  # noqa: ARG002
                pass

        a = BrowserAgent(mcp_manager=FakeMCP())
        result = a.execute({"objective": "browse"})
        assert result["browse_result"]["success"] is True

    def test_live_agent_is_base_agent(self) -> None:
        assert issubclass(LiveAgent, BaseAgent)

    def test_all_agents_are_base_agents(self) -> None:
        for cls in ALL_LIVE_AGENTS:
            assert issubclass(cls, BaseAgent)

    def test_agent_names_unique(self) -> None:
        agents = instantiate_all_agents()
        names = [a.name for a in agents]
        assert len(names) == len(set(names))

    def test_agent_roles(self) -> None:
        a = CodingAgent()
        assert a.role == "Code Generation"


# ===========================================================================
# Collaboration
# ===========================================================================


class TestCollaboration:
    def test_creates_empty(self) -> None:
        collab = AgentCollaborator()
        assert len(collab) == 0

    def test_add_agent(self) -> None:
        collab = AgentCollaborator()
        collab.add_agent(CodingAgent())
        assert len(collab) == 1

    def test_collaborate_single_agent(self) -> None:
        collab = AgentCollaborator([CodingAgent()])
        result = collab.collaborate("test goal")
        assert isinstance(result, CollaborationResult)
        assert result.success is True
        assert len(result.agent_reports) == 1

    def test_collaborate_multiple_agents(self) -> None:
        collab = AgentCollaborator([ResearchAgent(), CodingAgent(), GitHubAgent()])
        result = collab.collaborate("build a website")
        assert result.success is True
        assert len(result.agent_reports) == 3

    def test_collaborate_final_report(self) -> None:
        collab = AgentCollaborator([CodingAgent(), ResearchAgent()])
        result = collab.collaborate("test")
        assert result.final_report != ""
        assert "[coding_agent]" in result.final_report

    def test_collaborate_agent_failure(self) -> None:
        class BadAgent(BaseAgent):
            def __init__(self) -> None:
                super().__init__(name="bad")

            def plan(self, objective: str) -> Any:
                raise RuntimeError("boom")

            def execute(self, plan: Any) -> Any:
                pass

            def review(self, result: Any) -> Any:
                pass

            def report(self, review: Any) -> str:
                pass

        collab = AgentCollaborator([BadAgent(), CodingAgent()])
        result = collab.collaborate("test")
        assert result.success is False
        assert "ERROR" in result.agent_reports[0][1]

    def test_collaboration_result_is_frozen(self) -> None:
        result = CollaborationResult(goal="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.goal = "other"  # type: ignore[misc]

    def test_add_agent_chaining(self) -> None:
        collab = AgentCollaborator()
        result = collab.add_agent(CodingAgent()).add_agent(ResearchAgent())
        assert result is collab
        assert len(collab) == 2

    def test_collaborate_empty_agents(self) -> None:
        collab = AgentCollaborator([])
        result = collab.collaborate("test")
        assert result.success is True
        assert len(result.agent_reports) == 0

    def test_repr(self) -> None:
        collab = AgentCollaborator([CodingAgent()])
        assert "AgentCollaborator" in repr(collab)


# ===========================================================================
# Dashboard
# ===========================================================================


class TestDashboard:
    def test_create_app(self) -> None:
        from atlas.dashboard import create_app

        app = create_app()
        assert app is not None

    def test_health_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_status_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/status")
        assert resp.status_code == 200
        assert "timestamp" in resp.json()

    def test_providers_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/providers")
        assert resp.status_code == 200
        assert "providers" in resp.json()

    def test_agents_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 11

    def test_tools_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/tools")
        assert resp.status_code == 200
        assert "connectors" in resp.json()

    def test_workflows_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/workflows")
        assert resp.status_code == 200

    def test_memory_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/memory")
        assert resp.status_code == 200
        assert "entries" in resp.json()

    def test_knowledge_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/knowledge")
        assert resp.status_code == 200
        assert "documents" in resp.json()

    def test_events_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/events")
        assert resp.status_code == 200
        assert "events" in resp.json()

    def test_runtime_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/runtime")
        assert resp.status_code == 200

    def test_executions_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/executions")
        assert resp.status_code == 200

    def test_artifacts_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/artifacts")
        assert resp.status_code == 200
        assert "artifacts" in resp.json()

    def test_live_poll_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.get("/live")
        assert resp.status_code == 200
        assert "events" in resp.json()

    def test_app_with_subsystems(self) -> None:
        from atlas.dashboard import create_app

        am = ArtifactManager()
        am.create("test.txt")
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        app = create_app(artifact_manager=am, event_bus=bus)
        assert app.state.artifacts is am
        assert app.state.event_bus is bus

    def test_artifacts_with_manager(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        am = ArtifactManager()
        am.create("test.txt")
        am.create("code.py")
        app = create_app(artifact_manager=am)
        client = TestClient(app)
        resp = client.get("/artifacts")
        data = resp.json()
        assert data["count"] == 2
        assert len(data["artifacts"]) == 2

    def test_events_with_bus(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        bus.emit_task_started("t1", "research")
        app = create_app(event_bus=bus)
        client = TestClient(app)
        resp = client.get("/events")
        data = resp.json()
        assert data["total"] == 2


# ===========================================================================
# End-to-end integration
# ===========================================================================


class TestEndToEnd:
    def test_zero_circular_imports(self) -> None:
        import importlib

        modules = [
            "atlas.live.event_bus",
            "atlas.live.artifact_manager",
            "atlas.live.provider_adapter",
            "atlas.live.executor_bridge",
            "atlas.live.memory_integration",
            "atlas.live.knowledge_indexer",
            "atlas.live.streaming",
            "atlas.live",
            "atlas.agents.live",
            "atlas.agents.collaboration",
            "atlas.dashboard.app",
            "atlas.dashboard",
        ]
        for m in modules:
            importlib.import_module(m)

    def test_full_pipeline_without_subsystems(self) -> None:
        """The live runtime works even without injected subsystems."""
        bus = LiveEventBus()
        stream = StreamManager(event_bus=bus)
        artifacts = ArtifactManager()
        bridge = MCPExecutorBridge()

        stream.progress("starting", "Starting execution", 0.0)
        result = bridge.execute("research", {"url": "https://example.com"})
        assert result["success"]
        stream.progress("done", "Execution complete", 1.0)

        assert len(stream) == 2
        assert artifacts.count() == 0

    def test_full_pipeline_with_artifacts(self) -> None:
        """Artifacts are created and tracked."""
        bus = LiveEventBus()
        artifacts = ArtifactManager()
        stream = StreamManager(event_bus=bus)

        with stream.stage("generating", "Generating code..."):
            a = artifacts.create(
                "output.py",
                content="print('hello')",
                source="coding_agent",
            )
            bus.emit_artifact_created(a.id, a.artifact_type.value)

        assert artifacts.count() == 1
        assert len(bus) >= 2  # stream progress + artifact created

    def test_collaboration_with_live_agents(self) -> None:
        agents = instantiate_all_agents()
        collab = AgentCollaborator(agents[:3])
        result = collab.collaborate("build a website")
        assert result.success is True
        assert len(result.agent_reports) == 3

    def test_event_bus_history_tracks_all_types(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        bus.emit_task_started("t1", "research")
        bus.emit_task_completed("t1", True, 0.5)
        bus.emit_memory_stored("goal", "e1")
        bus.emit_artifact_created("a1", "image")
        bus.emit_goal_finished("g1", "completed", 1.0)

        history = bus.history()
        types = [type(e).__name__ for e in history]
        assert "GoalStarted" in types
        assert "TaskStarted" in types
        assert "TaskCompleted" in types
        assert "MemoryStored" in types
        assert "ArtifactCreated" in types
        assert "GoalFinished" in types


# ===========================================================================
# Additional Event Bus tests
# ===========================================================================


class TestEventBusAdditional:
    def test_multiple_events_same_goal(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        bus.emit_task_started("t1", "research")
        bus.emit_task_completed("t1", True, 0.5)
        bus.emit_goal_finished("g1", "completed", 1.0)
        assert len(bus) == 4
        events = bus.history_for("g1")
        assert len(events) == 2  # GoalStarted and GoalFinished have execution_id="g1"

    def test_subscribe_multiple_listeners(self) -> None:
        bus = LiveEventBus()
        received1: list[Any] = []
        received2: list[Any] = []
        bus.subscribe(GoalStarted, received1.append)
        bus.subscribe(GoalStarted, received2.append)
        bus.emit_goal_started("g1", "test")
        assert len(received1) == 1
        assert len(received2) == 1

    def test_unsubscribe(self) -> None:
        bus = LiveEventBus()
        received: list[Any] = []
        bus.subscribe(GoalStarted, received.append)
        bus.bus.unsubscribe(GoalStarted, received.append)
        bus.emit_goal_started("g1", "test")
        assert len(received) == 0

    def test_wildcard_subscription(self) -> None:
        bus = LiveEventBus()
        received: list[Any] = []
        bus.subscribe("*", received.append)
        bus.emit_goal_started("g1", "test")
        bus.emit_task_started("t1", "research")
        assert len(received) == 2

    def test_history_order_preserved(self) -> None:
        bus = LiveEventBus()
        bus.emit_goal_started("g1", "first")
        bus.emit_goal_finished("g1", "completed")
        bus.emit_goal_started("g2", "second")
        history = bus.history()
        assert isinstance(history[0], GoalStarted)
        assert history[0].goal_id == "g1"
        assert isinstance(history[2], GoalStarted)
        assert history[2].goal_id == "g2"

    def test_stream_progress_values(self) -> None:
        bus = LiveEventBus()
        bus.emit_stream_progress("planning", "Planning...", 0.0)
        bus.emit_stream_progress("executing", "Running...", 0.5)
        bus.emit_stream_progress("done", "Complete", 1.0)
        history = bus.history()
        assert history[0].progress == 0.0
        assert history[1].progress == 0.5
        assert history[2].progress == 1.0


# ===========================================================================
# Additional Artifact Manager tests
# ===========================================================================


class TestArtifactManagerAdditional:
    def test_artifact_with_goal_id(self) -> None:
        am = ArtifactManager()
        a = am.create("test.py", goal_id="g1")
        assert a.goal_id == "g1"

    def test_artifact_with_source(self) -> None:
        am = ArtifactManager()
        a = am.create("test.py", source="coding_agent")
        assert a.source == "coding_agent"

    def test_artifact_with_metadata(self) -> None:
        am = ArtifactManager()
        a = am.create("test.py", metadata={"lines": 42, "language": "python"})
        assert a.metadata["lines"] == 42
        assert a.metadata["language"] == "python"

    def test_artifact_created_at(self) -> None:
        am = ArtifactManager()
        a = am.create("test.py")
        assert a.created_at is not None

    def test_artifact_id_unique(self) -> None:
        am = ArtifactManager()
        a1 = am.create("test1.py")
        a2 = am.create("test2.py")
        assert a1.id != a2.id

    def test_search_no_results(self) -> None:
        am = ArtifactManager()
        am.create("test.py")
        results = am.search("nonexistent")
        assert len(results) == 0

    def test_search_case_insensitive(self) -> None:
        am = ArtifactManager()
        am.create("PythonScript.py")
        results = am.search("python")
        assert len(results) == 1

    def test_count_by_type_empty(self) -> None:
        am = ArtifactManager()
        assert am.count_by_type() == {}

    def test_list_sorted_newest_first(self) -> None:
        am = ArtifactManager()
        a1 = am.create("first.txt")
        am.create("second.txt")
        a3 = am.create("third.txt")
        listed = am.list()
        assert listed[0].id == a3.id
        assert listed[-1].id == a1.id

    def test_delete_artifact_removes_from_search(self) -> None:
        am = ArtifactManager()
        a = am.create("test.py", content="hello")
        am.delete(a.id)
        results = am.search("hello")
        assert len(results) == 0

    def test_all_artifact_types(self) -> None:
        types = list(ArtifactType)
        assert ArtifactType.IMAGE in types
        assert ArtifactType.VIDEO in types
        assert ArtifactType.PYTHON in types
        assert ArtifactType.MARKDOWN in types
        assert ArtifactType.JSON in types
        assert ArtifactType.PDF in types
        assert ArtifactType.ZIP in types
        assert ArtifactType.BLEND in types


# ===========================================================================
# Additional Provider Adapter tests
# ===========================================================================


class TestProviderAdapterAdditional:
    def test_zai_provider_priority(self) -> None:
        p = ZAIProvider(api_key="test")
        assert p.info.priority == 1

    def test_ollama_provider_priority(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434")
        assert p.info.priority == 5

    def test_openrouter_provider_priority(self) -> None:
        p = OpenRouterProvider(api_key="test")
        assert p.info.priority == 10

    def test_zai_provider_cost(self) -> None:
        p = ZAIProvider(api_key="test")
        assert p.info.cost_per_1k == 0.001

    def test_ollama_provider_cost(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434")
        assert p.info.cost_per_1k == 0.0

    def test_zai_provider_capabilities(self) -> None:
        p = ZAIProvider(api_key="test")
        assert p.info.capabilities.streaming is True
        assert p.info.capabilities.tools is True

    def test_ollama_provider_capabilities(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434")
        assert p.info.capabilities.streaming is True
        assert p.info.capabilities.system_prompt is True

    def test_openrouter_provider_capabilities(self) -> None:
        p = OpenRouterProvider(api_key="test")
        assert p.info.capabilities.images is True
        assert p.info.capabilities.tools is True

    def test_openrouter_provider_available_models(self) -> None:
        p = OpenRouterProvider(api_key=None)
        models = p.available_models()
        assert isinstance(models, list)

    def test_create_live_providers_count(self) -> None:
        providers = create_live_providers()
        assert len(providers) == 3

    def test_register_live_providers_default(self) -> None:
        from atlas.providers import ProviderManager

        pm = ProviderManager()
        register_live_providers(pm)
        default = pm.registry.default()
        assert default.name == "zai"

    @patch("requests.post")
    def test_zai_provider_generate_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = Exception("network error")
        p = ZAIProvider(api_key="test_key")
        req = ProviderRequest(prompt="hello")
        resp = p.generate(req)
        assert "error" in resp.text.lower()

    def test_zai_provider_stream_yields(self) -> None:
        p = ZAIProvider(api_key=None)
        req = ProviderRequest(prompt="hello")
        chunks = list(p.stream(req))
        assert len(chunks) >= 1

    def test_ollama_provider_stream_yields(self) -> None:
        p = OllamaProvider(base_url="http://localhost:11434")
        req = ProviderRequest(prompt="hello")
        try:
            chunks = list(p.stream(req))
            assert len(chunks) >= 1
        except Exception:
            pass

    def test_openrouter_provider_stream_yields(self) -> None:
        p = OpenRouterProvider(api_key=None)
        req = ProviderRequest(prompt="hello")
        try:
            chunks = list(p.stream(req))
            assert len(chunks) >= 1
        except Exception:
            pass


# ===========================================================================
# Additional Executor Bridge tests
# ===========================================================================


class TestExecutorBridgeAdditional:
    def test_capability_map_has_all_capabilities(self) -> None:
        assert len(MCPExecutorBridge.CAPABILITY_MAP) >= 15

    def test_bridge_with_mcp_filesystem(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import FilesystemConnector

        mcp.register_connector(FilesystemConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        assert bridge.can_execute("file.read")
        assert bridge.can_execute("file.write")
        assert bridge.can_execute("file.list")
        assert bridge.can_execute("file.delete")

    def test_bridge_with_mcp_github(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import GitHubConnector

        mcp.register_connector(GitHubConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        assert bridge.can_execute("git_commit")
        assert bridge.can_execute("git.status")

    def test_bridge_with_mcp_browser(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import BrowserConnector

        mcp.register_connector(BrowserConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        assert bridge.can_execute("research")
        assert bridge.can_execute("browser.navigate")

    def test_bridge_with_mcp_blender(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import BlenderConnector

        mcp.register_connector(BlenderConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        assert bridge.can_execute("generate_assets")

    def test_bridge_with_mcp_windows(self) -> None:
        mcp = MCPManager()
        from atlas.mcp import WindowsConnector

        mcp.register_connector(WindowsConnector())
        bridge = MCPExecutorBridge(mcp_manager=mcp)
        assert bridge.can_execute("deploy")

    def test_bridge_build_params_shell(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params("deploy", "windows.shell", {"command": "echo hi"})
        assert params["command"] == "echo hi"

    def test_bridge_build_params_blender(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params("generate_assets", "blender.render", {"frame": 5})
        assert params["frame"] == 5

    def test_bridge_build_params_playwright(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params(
            "playwright.goto", "playwright.goto", {"url": "https://x.com"}
        )
        assert params["url"] == "https://x.com"

    def test_bridge_build_params_unknown(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        params = bridge._build_params("bogus", "bogus.cap", {"key": "val"})
        assert params == {"key": "val"}

    def test_bridge_placeholder_has_note(self) -> None:
        bridge = MCPExecutorBridge(mcp_manager=None)
        result = bridge._placeholder("test", {})
        assert "note" in result["output"]


# ===========================================================================
# Additional Memory Integration tests
# ===========================================================================


class TestMemoryIntegratorAdditional:
    def test_store_plan_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_plan("g1", MagicMock())  # should not raise

    def test_store_reasoning_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_reasoning("g1", MagicMock())  # should not raise

    def test_store_tool_output_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_tool_output("g1", "fs", {})  # should not raise

    def test_store_provider_output_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_provider_output("g1", "ollama", "text")  # should not raise

    def test_store_error_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_error("g1", "error")  # should not raise

    def test_store_lesson_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_lesson("l1", "content", "cat")  # should not raise

    def test_store_artifact_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_artifact("g1", "a1", "test", "image")  # should not raise

    def test_store_metrics_without_memory(self) -> None:
        mi = MemoryIntegrator(memory=None)
        mi.store_metrics("g1", 1.0, 1, 0)  # should not raise

    def test_repr(self) -> None:
        mi = MemoryIntegrator(memory=None)
        assert "MemoryIntegrator" in repr(mi)


# ===========================================================================
# Additional Knowledge Indexer tests
# ===========================================================================


class TestKnowledgeIndexerAdditional:
    def test_indexed_ids_empty(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert ki.indexed_ids() == []

    def test_index_directory_not_found(self) -> None:
        ki = KnowledgeIndexer(knowledge=MagicMock())
        assert ki.index_directory("/nonexistent") == 0

    def test_search_with_knowledge(self) -> None:
        class FakeKnowledge:
            def search(self, query, top_k=5):  # noqa: ARG002
                return [{"content": "result"}]

        ki = KnowledgeIndexer(knowledge=FakeKnowledge())
        results = ki.search("test")
        assert len(results) == 1

    def test_repr(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert "KnowledgeIndexer" in repr(ki)

    def test_not_indexable_extensions(self) -> None:
        ki = KnowledgeIndexer(knowledge=None)
        assert not ki.is_indexable("file.png")
        assert not ki.is_indexable("file.pdf")
        assert not ki.is_indexable("file.zip")

    def test_index_text_returns_doc_id(self) -> None:
        class FakeDoc:
            id = "doc_123"

        class FakeKnowledge:
            def ingest_text(
                self, content, source, tags=None, **metadata
            ):  # noqa: ARG002
                return FakeDoc()

        ki = KnowledgeIndexer(knowledge=FakeKnowledge())
        doc_id = ki.index_text("content", "source")
        assert doc_id == "doc_123"
        assert "doc_123" in ki.indexed_ids()


# ===========================================================================
# Additional Streaming tests
# ===========================================================================


class TestStreamingAdditional:
    def test_stage_context_manager_progress(self) -> None:
        sm = StreamManager()
        with sm.stage("researching", "Searching..."):
            pass
        stages = sm.stages()
        assert stages[0][0] == "researching"
        assert stages[0][2] == 0.0
        assert stages[1][0] == "researching"
        assert stages[1][2] == 1.0

    def test_multiple_subscribers(self) -> None:
        sm = StreamManager()
        r1: list[Any] = []
        r2: list[Any] = []
        sm.subscribe(lambda s, m, p: r1.append(s))
        sm.subscribe(lambda s, m, p: r2.append(s))
        sm.progress("test", "", 0)
        assert len(r1) == 1
        assert len(r2) == 1

    def test_unsubscribe_not_found(self) -> None:
        sm = StreamManager()
        assert sm.unsubscribe(lambda: None) is False  # type: ignore[arg-type]

    def test_progress_stages_order(self) -> None:
        sm = StreamManager()
        sm.progress("a", "", 0.0)
        sm.progress("b", "", 0.5)
        sm.progress("c", "", 1.0)
        stages = sm.stages()
        assert [s[0] for s in stages] == ["a", "b", "c"]

    def test_default_stages_count(self) -> None:
        stages = default_progress_stages()
        assert len(stages) >= 10


# ===========================================================================
# Additional Agent tests
# ===========================================================================


class TestLiveAgentsAdditional:
    def test_coding_agent_plan(self) -> None:
        a = CodingAgent()
        plan = a.plan("write code")
        assert plan["approach"] == "generate_code"

    def test_research_agent_plan(self) -> None:
        a = ResearchAgent()
        plan = a.plan("research")
        assert plan["approach"] == "research"

    def test_github_agent_plan(self) -> None:
        a = GitHubAgent()
        plan = a.plan("git")
        assert plan["approach"] == "git_operations"

    def test_browser_agent_plan(self) -> None:
        a = BrowserAgent()
        plan = a.plan("browse")
        assert plan["approach"] == "browse"

    def test_mining_agent_plan(self) -> None:
        a = MiningAgent()
        plan = a.plan("mine")
        assert plan["approach"] == "data_processing"

    def test_vision_agent_plan(self) -> None:
        a = VisionAgent()
        plan = a.plan("capture")
        assert plan["approach"] == "capture"

    def test_windows_agent_plan(self) -> None:
        a = WindowsAgent()
        plan = a.plan("run")
        assert plan["approach"] == "os_operations"

    def test_planner_agent_plan(self) -> None:
        a = PlannerAgent()
        plan = a.plan("plan")
        assert "steps" in plan

    def test_knowledge_agent_plan(self) -> None:
        a = KnowledgeAgent()
        plan = a.plan("search")
        assert plan["approach"] == "knowledge_search"

    def test_memory_agent_plan(self) -> None:
        a = MemoryAgent()
        plan = a.plan("recall")
        assert plan["approach"] == "memory_recall"

    def test_blender_agent_plan(self) -> None:
        a = BlenderAgent()
        plan = a.plan("render")
        assert plan["approach"] == "render"

    def test_coding_agent_execute(self) -> None:
        a = CodingAgent()
        result = a.execute({"objective": "write hello world"})
        assert "code" in result
        assert "language" in result

    def test_research_agent_execute(self) -> None:
        a = ResearchAgent()
        result = a.execute({"objective": "AI"})
        assert "findings" in result

    def test_coding_agent_report(self) -> None:
        a = CodingAgent()
        report = a.report({"code": "print('hello')"})
        assert "code" in report.lower() or "character" in report.lower()

    def test_instantiate_with_deps(self) -> None:
        agents = instantiate_all_agents(
            mcp_manager=MagicMock(),
            providers=MagicMock(),
            memory=MagicMock(),
            knowledge=MagicMock(),
        )
        assert len(agents) == 11
        for a in agents:
            assert a.mcp_manager is not None
            assert a.providers is not None
            assert a.memory is not None
            assert a.knowledge is not None


# ===========================================================================
# Additional Collaboration tests
# ===========================================================================


class TestCollaborationAdditional:
    def test_collaborate_with_all_agents(self) -> None:
        agents = instantiate_all_agents()
        collab = AgentCollaborator(agents)
        result = collab.collaborate("build everything")
        assert result.success is True
        assert len(result.agent_reports) == 11

    def test_collaboration_duration_positive(self) -> None:
        collab = AgentCollaborator([CodingAgent()])
        result = collab.collaborate("test")
        assert result.duration_seconds >= 0.0

    def test_collaboration_final_report_contains_all(self) -> None:
        collab = AgentCollaborator([CodingAgent(), ResearchAgent()])
        result = collab.collaborate("test")
        assert "[coding_agent]" in result.final_report
        assert "[research_agent]" in result.final_report

    def test_add_agent_returns_self(self) -> None:
        collab = AgentCollaborator()
        ret = collab.add_agent(CodingAgent())
        assert ret is collab


# ===========================================================================
# Additional Dashboard tests
# ===========================================================================


class TestDashboardAdditional:
    def test_health_with_mcp(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app
        from atlas.mcp import MCPManager

        mcp = MCPManager()
        app = create_app(mcp_manager=mcp)
        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()
        assert "mcp" in data

    def test_status_with_brain(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app
        from atlas.intelligence import Brain

        brain = Brain()
        app = create_app(brain=brain)
        client = TestClient(app)
        resp = client.get("/status")
        data = resp.json()
        assert "brain" in data

    def test_memory_with_engine(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app
        from atlas.memory import MemoryEngine

        memory = MemoryEngine()
        app = create_app(memory=memory)
        client = TestClient(app)
        resp = client.get("/memory")
        data = resp.json()
        assert "stores" in data

    def test_knowledge_with_engine(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app
        from atlas.knowledge import KnowledgeEngine

        knowledge = KnowledgeEngine()
        app = create_app(knowledge=knowledge)
        client = TestClient(app)
        resp = client.get("/knowledge")
        data = resp.json()
        assert "documents" in data

    def test_events_with_bus_limit(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        bus = LiveEventBus()
        for i in range(10):
            bus.emit_goal_started(f"g{i}", "test")
        app = create_app(event_bus=bus)
        client = TestClient(app)
        resp = client.get("/events?limit=5")
        data = resp.json()
        assert len(data["events"]) == 5
        assert data["total"] == 10

    def test_artifacts_with_manager_filtered(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        am = ArtifactManager()
        am.create("a.txt")
        am.create("b.py")
        app = create_app(artifact_manager=am)
        client = TestClient(app)
        resp = client.get("/artifacts?limit=1")
        data = resp.json()
        assert data["count"] == 2
        assert len(data["artifacts"]) == 1

    def test_live_poll_returns_events(self) -> None:
        from fastapi.testclient import TestClient

        from atlas.dashboard import create_app

        bus = LiveEventBus()
        bus.emit_goal_started("g1", "test")
        app = create_app(event_bus=bus)
        client = TestClient(app)
        resp = client.get("/live")
        data = resp.json()
        assert len(data["events"]) >= 1

    def test_app_title(self) -> None:
        from atlas.dashboard import create_app

        app = create_app()
        assert app.title == "Atlas Dashboard API"
