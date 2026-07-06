"""Tests for the Atlas Live Agents (Production Sprint 3).

Covers capability routing, metrics, streaming, health, statistics,
and real execution for all 11 agents. All tests are deterministic
and headless.
"""

from __future__ import annotations

import pytest

from atlas.agents import (
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
from atlas.pipeline import build_pipeline

# ===========================================================================
# Package
# ===========================================================================


class TestPackage:
    def test_imports(self) -> None:
        from atlas.agents import __all__

        assert "LiveAgent" in __all__
        assert "CodingAgent" in __all__
        assert "instantiate_all_agents" in __all__

    def test_all_live_agents_count(self) -> None:
        assert len(ALL_LIVE_AGENTS) == 11


# ===========================================================================
# AgentMetrics
# ===========================================================================


class TestAgentMetrics:
    def test_default(self) -> None:
        m = AgentMetrics()
        assert m.total_executions == 0
        assert m.success_rate == 0.0
        assert m.average_latency == 0.0

    def test_success_rate(self) -> None:
        m = AgentMetrics(total_executions=10, successful=8)
        assert m.success_rate == 0.8

    def test_average_latency(self) -> None:
        m = AgentMetrics(total_executions=5, total_latency_seconds=10.0)
        assert m.average_latency == 2.0

    def test_uptime(self) -> None:
        m = AgentMetrics()
        assert m.uptime_seconds >= 0.0


# ===========================================================================
# LiveAgent base
# ===========================================================================


class TestLiveAgentBase:
    def test_construct(self) -> None:
        a = CodingAgent()
        assert a.name == "coding_agent"
        assert a.role == "Code Generation"

    def test_supports(self) -> None:
        a = CodingAgent()
        assert a.supports("code_generation")
        assert a.supports("debugging")
        assert not a.supports("browsing")

    def test_capabilities(self) -> None:
        a = CodingAgent()
        caps = a.capabilities()
        assert "code_generation" in caps
        assert "testing" in caps

    def test_estimate(self) -> None:
        a = CodingAgent()
        est = a.estimate("Write a function")
        assert "estimated_duration_seconds" in est
        assert "estimated_cost_usd" in est

    def test_health(self) -> None:
        a = CodingAgent()
        assert a.health() is True

    def test_statistics_initial(self) -> None:
        a = CodingAgent()
        stats = a.statistics()
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0

    def test_execute_tracks_metrics(self) -> None:
        a = CodingAgent()
        plan = a.plan("Write hello world")
        a.execute(plan)
        stats = a.statistics()
        assert stats["total_executions"] == 1
        assert stats["successful"] == 1
        assert stats["success_rate"] == 1.0

    def test_execute_failure_tracked(self) -> None:
        class FailingAgent(LiveAgent):
            CAPABILITIES = ("test",)

            def _do_execute(self, plan: object) -> object:
                raise RuntimeError("boom")

        a = FailingAgent(name="failing")
        plan = {"objective": "test"}
        with pytest.raises(RuntimeError):
            a.execute(plan)
        stats = a.statistics()
        assert stats["total_executions"] == 1
        assert stats["failed"] == 1
        assert "boom" in stats["last_error"]

    def test_streaming_yields_events(self) -> None:
        a = CodingAgent()
        events = list(a.execute_stream("Write hello"))
        event_types = [e["event"] for e in events]
        assert "started" in event_types
        assert "thinking" in event_types
        assert "executing" in event_types
        assert "completed" in event_types

    def test_streaming_error_event(self) -> None:
        class FailingAgent(LiveAgent):
            CAPABILITIES = ("test",)

            def _do_execute(self, plan: object) -> object:
                raise RuntimeError("stream boom")

        a = FailingAgent(name="failing")
        events = list(a.execute_stream("test"))
        assert any(e["event"] == "error" for e in events)

    def test_streaming_tracks_metrics(self) -> None:
        a = CodingAgent()
        list(a.execute_stream("test"))
        stats = a.statistics()
        assert stats["total_executions"] == 1
        assert stats["successful"] == 1

    def test_generate_no_providers(self) -> None:
        a = CodingAgent()
        result = a._generate("test")
        assert "[offline:" in result

    def test_generate_with_providers(self) -> None:
        pipeline = build_pipeline()
        a = CodingAgent(providers=pipeline.providers)
        result = a._generate("Hello")
        assert len(result) > 0

    def test_think_no_brain(self) -> None:
        a = CodingAgent()
        result = a._think("goal")
        assert result["status"] == "offline"


# ===========================================================================
# Capability routing — every agent
# ===========================================================================


class TestCapabilityRouting:
    def test_coding_agent_capabilities(self) -> None:
        a = CodingAgent()
        assert a.supports("code_generation")
        assert a.supports("debugging")
        assert a.supports("refactoring")
        assert a.supports("testing")
        assert not a.supports("browsing")

    def test_research_agent_capabilities(self) -> None:
        a = ResearchAgent()
        assert a.supports("web_research")
        assert a.supports("summarization")
        assert a.supports("citations")

    def test_github_agent_capabilities(self) -> None:
        a = GitHubAgent()
        assert a.supports("commit")
        assert a.supports("branch")
        assert a.supports("merge")
        assert a.supports("pull_request")
        assert a.supports("repository_management")

    def test_browser_agent_capabilities(self) -> None:
        a = BrowserAgent()
        assert a.supports("browsing")
        assert a.supports("scraping")
        assert a.supports("form_filling")

    def test_mining_agent_capabilities(self) -> None:
        a = MiningAgent()
        assert a.supports("surpac")
        assert a.supports("autocad")
        assert a.supports("qgis")

    def test_vision_agent_capabilities(self) -> None:
        a = VisionAgent()
        assert a.supports("ocr")
        assert a.supports("image_analysis")

    def test_windows_agent_capabilities(self) -> None:
        a = WindowsAgent()
        assert a.supports("filesystem")
        assert a.supports("terminal")
        assert a.supports("automation")

    def test_planner_agent_capabilities(self) -> None:
        a = PlannerAgent()
        assert a.supports("planning")
        assert a.supports("decomposition")

    def test_knowledge_agent_capabilities(self) -> None:
        a = KnowledgeAgent()
        assert a.supports("indexing")
        assert a.supports("retrieval")

    def test_memory_agent_capabilities(self) -> None:
        a = MemoryAgent()
        assert a.supports("recall")
        assert a.supports("remember")

    def test_blender_agent_capabilities(self) -> None:
        a = BlenderAgent()
        assert a.supports("rendering")
        assert a.supports("scene_generation")


# ===========================================================================
# Execution — every agent
# ===========================================================================


class TestAgentExecution:
    def test_coding_agent_execute(self) -> None:
        a = CodingAgent()
        plan = a.plan("Write hello world")
        result = a.execute(plan)
        assert "code" in result
        assert result["language"] == "python"

    def test_coding_agent_run(self) -> None:
        a = CodingAgent()
        report = a.run("Write a function")
        assert "Generated" in report

    def test_research_agent_execute(self) -> None:
        a = ResearchAgent()
        plan = a.plan("Research AI")
        result = a.execute(plan)
        assert "findings" in result
        assert "summary" in result

    def test_github_agent_execute(self) -> None:
        a = GitHubAgent()
        plan = a.plan("Check status")
        result = a.execute(plan)
        assert "git_status" in result

    def test_browser_agent_execute(self) -> None:
        a = BrowserAgent()
        plan = a.plan("Browse example.com")
        result = a.execute(plan)
        assert "browse_result" in result

    def test_mining_agent_execute(self) -> None:
        a = MiningAgent()
        plan = a.plan("List files")
        result = a.execute(plan)
        assert "data_result" in result

    def test_vision_agent_execute(self) -> None:
        a = VisionAgent()
        plan = a.plan("Take screenshot")
        result = a.execute(plan)
        assert "vision_result" in result

    def test_windows_agent_execute(self) -> None:
        a = WindowsAgent()
        plan = a.plan("Run echo")
        result = a.execute(plan)
        assert "os_result" in result

    def test_planner_agent_execute(self) -> None:
        a = PlannerAgent()
        plan = a.plan("Build an app")
        result = a.execute(plan)
        assert "steps" in result
        assert len(result["steps"]) > 0

    def test_knowledge_agent_execute(self) -> None:
        a = KnowledgeAgent()
        plan = a.plan("Search knowledge")
        result = a.execute(plan)
        assert "knowledge_hits" in result

    def test_memory_agent_execute(self) -> None:
        a = MemoryAgent()
        plan = a.plan("Recall memories")
        result = a.execute(plan)
        assert "memories" in result

    def test_blender_agent_execute(self) -> None:
        a = BlenderAgent()
        plan = a.plan("Render frame")
        result = a.execute(plan)
        assert "render_result" in result


# ===========================================================================
# Estimates — every agent
# ===========================================================================


class TestEstimates:
    def test_coding_estimate(self) -> None:
        a = CodingAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0
        assert est["estimated_cost_usd"] > 0

    def test_research_estimate(self) -> None:
        a = ResearchAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_github_estimate(self) -> None:
        a = GitHubAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_browser_estimate(self) -> None:
        a = BrowserAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_mining_estimate(self) -> None:
        a = MiningAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_vision_estimate(self) -> None:
        a = VisionAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_windows_estimate(self) -> None:
        a = WindowsAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_planner_estimate(self) -> None:
        a = PlannerAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_knowledge_estimate(self) -> None:
        a = KnowledgeAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_memory_estimate(self) -> None:
        a = MemoryAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0

    def test_blender_estimate(self) -> None:
        a = BlenderAgent()
        est = a.estimate("task")
        assert est["estimated_duration_seconds"] > 0


# ===========================================================================
# Streaming — every agent
# ===========================================================================


class TestStreaming:
    @pytest.mark.parametrize(
        "agent_cls",
        [
            CodingAgent,
            ResearchAgent,
            GitHubAgent,
            BrowserAgent,
            MiningAgent,
            VisionAgent,
            WindowsAgent,
            PlannerAgent,
            KnowledgeAgent,
            MemoryAgent,
            BlenderAgent,
        ],
    )
    def test_stream_yields_started_and_completed(self, agent_cls: type) -> None:
        a = agent_cls()
        events = list(a.execute_stream("test task"))
        types = [e["event"] for e in events]
        assert "started" in types
        assert "completed" in types

    @pytest.mark.parametrize(
        "agent_cls",
        [
            CodingAgent,
            ResearchAgent,
            GitHubAgent,
            BrowserAgent,
            MiningAgent,
            VisionAgent,
            WindowsAgent,
            PlannerAgent,
            KnowledgeAgent,
            MemoryAgent,
            BlenderAgent,
        ],
    )
    def test_stream_includes_thinking(self, agent_cls: type) -> None:
        a = agent_cls()
        events = list(a.execute_stream("test"))
        assert any(e["event"] == "thinking" for e in events)

    @pytest.mark.parametrize(
        "agent_cls",
        [
            CodingAgent,
            ResearchAgent,
            GitHubAgent,
            BrowserAgent,
            MiningAgent,
            VisionAgent,
            WindowsAgent,
            PlannerAgent,
            KnowledgeAgent,
            MemoryAgent,
            BlenderAgent,
        ],
    )
    def test_stream_includes_executing(self, agent_cls: type) -> None:
        a = agent_cls()
        events = list(a.execute_stream("test"))
        assert any(e["event"] == "executing" for e in events)


# ===========================================================================
# Statistics — every agent
# ===========================================================================


class TestStatistics:
    @pytest.mark.parametrize(
        "agent_cls",
        [
            CodingAgent,
            ResearchAgent,
            GitHubAgent,
            BrowserAgent,
            MiningAgent,
            VisionAgent,
            WindowsAgent,
            PlannerAgent,
            KnowledgeAgent,
            MemoryAgent,
            BlenderAgent,
        ],
    )
    def test_statistics_after_execution(self, agent_cls: type) -> None:
        a = agent_cls()
        a.run("test objective")
        stats = a.statistics()
        assert stats["total_executions"] == 1
        assert stats["successful"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["average_latency_seconds"] >= 0.0
        assert stats["last_execution_time"] is not None

    def test_statistics_after_multiple_executions(self) -> None:
        a = CodingAgent()
        for i in range(5):
            a.run(f"task {i}")
        stats = a.statistics()
        assert stats["total_executions"] == 5
        assert stats["successful"] == 5


# ===========================================================================
# instantiate_all_agents
# ===========================================================================


class TestInstantiateAll:
    def test_instantiate_all_default(self) -> None:
        agents = instantiate_all_agents()
        assert len(agents) == 11

    def test_instantiate_all_with_pipeline(self) -> None:
        p = build_pipeline()
        agents = instantiate_all_agents(
            providers=p.providers,
            memory=p.memory,
            knowledge=p.knowledge,
            mcp_manager=p.mcp,
            brain=p.brain,
        )
        assert len(agents) == 11
        # Verify they have real subsystems wired
        coding = next(a for a in agents if isinstance(a, CodingAgent))
        assert coding.providers is not None
        assert coding.memory is not None
        assert coding.brain is not None

    def test_instantiate_all_names(self) -> None:
        agents = instantiate_all_agents()
        names = [a.name for a in agents]
        assert "coding_agent" in names
        assert "research_agent" in names
        assert "github_agent" in names
        assert "blender_agent" in names

    def test_instantiate_all_unique_names(self) -> None:
        agents = instantiate_all_agents()
        names = [a.name for a in agents]
        assert len(names) == len(set(names))


# ===========================================================================
# Integration with real pipeline
# ===========================================================================


class TestPipelineIntegration:
    def test_coding_agent_with_real_providers(self) -> None:
        p = build_pipeline()
        a = CodingAgent(providers=p.providers)
        report = a.run("Write a print statement")
        assert "Generated" in report
        stats = a.statistics()
        assert stats["total_executions"] == 1

    def test_research_agent_with_real_knowledge(self) -> None:
        p = build_pipeline()
        p.knowledge.ingest_text("Atlas is an AI OS", source="test")
        a = ResearchAgent(knowledge=p.knowledge, providers=p.providers)
        report = a.run("Research Atlas")
        assert "Found" in report

    def test_knowledge_agent_with_real_engine(self) -> None:
        p = build_pipeline()
        p.knowledge.ingest_text("Python is great", source="test")
        a = KnowledgeAgent(knowledge=p.knowledge)
        report = a.run("Search for Python")
        assert "Found" in report

    def test_memory_agent_with_real_engine(self) -> None:
        p = build_pipeline()
        p.memory.remember("test memory", source="test")
        a = MemoryAgent(memory=p.memory)
        report = a.run("Recall memories")
        assert "Recalled" in report

    def test_planner_agent_with_real_brain(self) -> None:
        p = build_pipeline()
        a = PlannerAgent(brain=p.brain)
        plan = a.plan("Build an app")
        assert "steps" in plan

    def test_streaming_with_real_pipeline(self) -> None:
        p = build_pipeline()
        a = CodingAgent(providers=p.providers, memory=p.memory, knowledge=p.knowledge)
        events = list(a.execute_stream("Write hello"))
        assert any(e["event"] == "completed" for e in events)


# ===========================================================================
# Run lifecycle
# ===========================================================================


class TestRunLifecycle:
    @pytest.mark.parametrize(
        "agent_cls",
        [
            CodingAgent,
            ResearchAgent,
            GitHubAgent,
            BrowserAgent,
            MiningAgent,
            VisionAgent,
            WindowsAgent,
            PlannerAgent,
            KnowledgeAgent,
            MemoryAgent,
            BlenderAgent,
        ],
    )
    def test_run_returns_string(self, agent_cls: type) -> None:
        a = agent_cls()
        report = a.run("test objective")
        assert isinstance(report, str)
        assert len(report) > 0


# ===========================================================================
# No circular imports
# ===========================================================================


class TestNoCircularImports:
    def test_agents_does_not_import_subsystems(self) -> None:
        """The agents package must not import Atlas subsystems directly."""
        import os
        import re

        import atlas.agents

        root = os.path.dirname(atlas.agents.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|mcp|memory|knowledge|workflows|tools|integration|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline|workforce|collaboration|creator_pipeline|evaluation)\b"
        )
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path) as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert (
            not offenders
        ), "atlas.agents imports other Atlas subsystems:\n" + "\n".join(offenders)
