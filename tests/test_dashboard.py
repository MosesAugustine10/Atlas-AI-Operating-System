"""Tests for the Atlas Professional Dashboard.

Covers the DashboardDataCollector and all dashboard API endpoints.
All tests are deterministic and headless — they verify real data
aggregation from injected subsystems.
"""

from __future__ import annotations

import pytest

from atlas.dashboard import DashboardDataCollector, create_app
from atlas.evaluation import EvaluationOrchestrator
from atlas.pipeline import build_pipeline
from atlas.workforce import WorkforceOrchestrator

# ===========================================================================
# DashboardDataCollector — empty (no subsystems)
# ===========================================================================


class TestEmptyCollector:
    def setup_method(self) -> None:
        self.c = DashboardDataCollector()

    def test_system_metrics_empty(self) -> None:
        data = self.c.system_metrics()
        assert data["cpu_percent"] == 0.0
        assert data["ram_percent"] == 0.0
        assert data["gpu_name"] == ""

    def test_ai_metrics_empty(self) -> None:
        data = self.c.ai_metrics()
        assert data["provider_count"] == 0
        assert data["total_cost_usd"] == 0.0

    def test_workforce_metrics_empty(self) -> None:
        data = self.c.workforce_metrics()
        assert data["total_workers"] == 0
        assert data["idle_workers"] == 0

    def test_execution_metrics_empty(self) -> None:
        data = self.c.execution_metrics()
        assert data["running_workflows"] == 0
        assert data["success_rate"] == 0.0

    def test_memory_metrics_empty(self) -> None:
        data = self.c.memory_metrics()
        assert data["working_memory"] == 0

    def test_knowledge_metrics_empty(self) -> None:
        data = self.c.knowledge_metrics()
        assert data["documents"] == 0

    def test_mcp_metrics_empty(self) -> None:
        data = self.c.mcp_metrics()
        assert data["connector_count"] == 0

    def test_creator_metrics_empty(self) -> None:
        data = self.c.creator_metrics()
        assert data["projects"] == 0

    def test_evaluation_metrics_empty(self) -> None:
        data = self.c.evaluation_metrics()
        assert data["runs"] == 0

    def test_collect_all_has_all_sections(self) -> None:
        data = self.c.collect_all()
        assert "system" in data
        assert "ai" in data
        assert "workforce" in data
        assert "execution" in data
        assert "memory" in data
        assert "knowledge" in data
        assert "mcp" in data
        assert "creator" in data
        assert "evaluation" in data

    def test_system_metrics_has_hostname(self) -> None:
        data = self.c.system_metrics()
        assert data["hostname"] != ""
        assert data["platform"] != ""
        assert data["python_version"] != ""


# ===========================================================================
# DashboardDataCollector — with real pipeline
# ===========================================================================


class TestWithPipeline:
    def setup_method(self) -> None:
        self.pipeline = build_pipeline()
        self.c = DashboardDataCollector(
            providers=self.pipeline.providers,
            memory=self.pipeline.memory,
            knowledge=self.pipeline.knowledge,
            mcp=self.pipeline.mcp,
        )

    def test_ai_metrics_has_providers(self) -> None:
        data = self.c.ai_metrics()
        assert data["provider_count"] == 6
        assert "openai" in data["providers"]

    def test_ai_metrics_has_health(self) -> None:
        data = self.c.ai_metrics()
        assert isinstance(data["health"], dict)
        assert len(data["health"]) == 6

    def test_ai_metrics_has_current_provider(self) -> None:
        data = self.c.ai_metrics()
        assert data["current_provider"] != ""

    def test_ai_metrics_has_models(self) -> None:
        data = self.c.ai_metrics()
        assert "models" in data
        assert len(data["models"]) == 6

    def test_memory_metrics_after_remember(self) -> None:
        self.pipeline.memory.remember("test data", source="test")
        data = self.c.memory_metrics()
        assert data["working_memory"] > 0

    def test_knowledge_metrics_after_ingest(self) -> None:
        self.pipeline.knowledge.ingest_text("test content", source="test")
        data = self.c.knowledge_metrics()
        assert data["documents"] > 0

    def test_cost_tracking_after_generate(self) -> None:
        self.pipeline.providers.generate("Hello")
        data = self.c.ai_metrics()
        assert data["call_count"] > 0
        assert data["total_tokens_in"] > 0


# ===========================================================================
# DashboardDataCollector — with workforce
# ===========================================================================


class TestWithWorkforce:
    def setup_method(self) -> None:
        self.wf = WorkforceOrchestrator()
        self.wf.hire_default_workforce()
        self.c = DashboardDataCollector(workforce=self.wf.manager)

    def test_workforce_total(self) -> None:
        data = self.c.workforce_metrics()
        assert data["total_workers"] == 17

    def test_workforce_idle(self) -> None:
        data = self.c.workforce_metrics()
        assert data["idle_workers"] == 17

    def test_workforce_busy(self) -> None:
        data = self.c.workforce_metrics()
        assert data["busy_workers"] == 0

    def test_workforce_details(self) -> None:
        data = self.c.workforce_metrics()
        assert len(data["worker_details"]) == 17
        w = data["worker_details"][0]
        assert "name" in w
        assert "role" in w
        assert "status" in w


# ===========================================================================
# DashboardDataCollector — with evaluation
# ===========================================================================


class TestWithEvaluation:
    def setup_method(self) -> None:
        self.ev = EvaluationOrchestrator()
        self.ev.load_builtin_scenarios()
        b = self.ev.create_full_benchmark()
        self.ev.benchmark(b, version="1.0.0")
        self.c = DashboardDataCollector(evaluation=self.ev)

    def test_evaluation_runs(self) -> None:
        data = self.c.evaluation_metrics()
        assert data["runs"] == 1

    def test_evaluation_score(self) -> None:
        data = self.c.evaluation_metrics()
        assert data["latest_score"] > 0.0

    def test_evaluation_scenarios(self) -> None:
        data = self.c.evaluation_metrics()
        assert data["scenarios"] == 10


# ===========================================================================
# Logs
# ===========================================================================


class TestLogs:
    def setup_method(self) -> None:
        self.c = DashboardDataCollector()
        self.c.add_log("info", "Hello world", "test")
        self.c.add_log("warning", "Something happened", "system")
        self.c.add_log("error", "Boom", "test")

    def test_log_count(self) -> None:
        assert len(self.c.logs()) == 3

    def test_filter_by_level(self) -> None:
        assert len(self.c.logs(level="warning")) == 1
        assert len(self.c.logs(level="error")) == 1

    def test_search(self) -> None:
        results = self.c.logs(search="boom")
        assert len(results) == 1

    def test_search_case_insensitive(self) -> None:
        results = self.c.logs(search="HELLO")
        assert len(results) == 1

    def test_limit(self) -> None:
        assert len(self.c.logs(limit=2)) == 2

    def test_export(self) -> None:
        exported = self.c.export_logs()
        assert len(exported) == 3

    def test_clear(self) -> None:
        count = self.c.clear_logs()
        assert count == 3
        assert len(self.c.logs()) == 0

    def test_log_has_timestamp(self) -> None:
        logs = self.c.logs()
        assert "timestamp" in logs[0]

    def test_log_has_level(self) -> None:
        logs = self.c.logs()
        assert logs[0]["level"] == "info"

    def test_log_buffer_trims(self) -> None:
        c = DashboardDataCollector()
        c._max_logs = 5
        for i in range(10):
            c.add_log("info", f"msg {i}")
        assert len(c.logs()) == 5


# ===========================================================================
# System metrics with real SystemController
# ===========================================================================


class TestSystemMetrics:
    def test_system_metrics_with_controller(self) -> None:
        from atlas.studio.controllers.system_controller import SystemController

        ctrl = SystemController()
        c = DashboardDataCollector(system_controller=ctrl)
        data = c.system_metrics()
        # Should have real metrics (even if 0 on some hosts)
        assert "cpu_percent" in data
        assert "ram_percent" in data
        assert "disk_percent" in data
        assert "hostname" in data
        assert len(data["hostname"]) > 0

    def test_system_history(self) -> None:
        from atlas.studio.controllers.system_controller import SystemController

        ctrl = SystemController()
        ctrl.collect()
        ctrl.collect()
        c = DashboardDataCollector(system_controller=ctrl)
        data = c.system_metrics()
        assert len(data["history"]) >= 2


# ===========================================================================
# Creator pipeline metrics
# ===========================================================================


class TestCreatorMetrics:
    def test_creator_with_pipeline(self) -> None:
        from atlas.creator_pipeline import CreatorPipelineOrchestrator

        orch = CreatorPipelineOrchestrator()
        orch.create_project("Test goal")
        c = DashboardDataCollector(creator_pipeline=orch)
        data = c.creator_metrics()
        assert data["projects"] == 1
        assert data["running_projects"] == 1

    def test_creator_project_details(self) -> None:
        from atlas.creator_pipeline import CreatorPipelineOrchestrator

        orch = CreatorPipelineOrchestrator()
        orch.create_project("Create a video")
        c = DashboardDataCollector(creator_pipeline=orch)
        data = (
            c.creators_metrics()
            if hasattr(c, "creators_metrics")
            else c.creator_metrics()
        )
        assert len(data["project_details"]) == 1
        assert data["project_details"][0]["goal"] == "Create a video"


# ===========================================================================
# MCP metrics
# ===========================================================================


class TestMCPMetrics:
    def test_mcp_with_manager(self) -> None:
        from atlas.mcp.manager import MCPManager

        mgr = MCPManager()
        c = DashboardDataCollector(mcp=mgr)
        data = c.mcp_metrics()
        # MCPManager may have 0 connectors by default
        assert "connectors" in data
        assert "connector_count" in data


# ===========================================================================
# FastAPI app endpoints
# ===========================================================================


class TestFastAPIApp:
    def test_create_app_minimal(self) -> None:
        try:
            app = create_app()
            assert app is not None
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_create_app_with_pipeline(self) -> None:
        try:
            pipeline = build_pipeline()
            app = create_app(
                provider_manager=pipeline.providers,
                memory=pipeline.memory,
                knowledge=pipeline.knowledge,
                mcp_manager=pipeline.mcp,
            )
            assert app is not None
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_app_has_dashboard_endpoints(self) -> None:
        try:
            app = create_app()
            routes = [r.path for r in app.routes]
            assert "/dashboard/system" in routes
            assert "/dashboard/ai" in routes
            assert "/dashboard/workforce" in routes
            assert "/dashboard/execution" in routes
            assert "/dashboard/memory" in routes
            assert "/dashboard/knowledge" in routes
            assert "/dashboard/mcp" in routes
            assert "/dashboard/creator" in routes
            assert "/dashboard/evaluation" in routes
            assert "/dashboard/logs" in routes
            assert "/dashboard/all" in routes
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_app_has_original_endpoints(self) -> None:
        try:
            app = create_app()
            routes = [r.path for r in app.routes]
            assert "/health" in routes
            assert "/status" in routes
            assert "/providers" in routes
            assert "/live" in routes
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_app_version_is_v2(self) -> None:
        try:
            app = create_app()
            assert app.version == "2.0.0"
        except ImportError:
            pytest.skip("FastAPI not installed")


# ===========================================================================
# Integration — full dashboard with all subsystems
# ===========================================================================


class TestFullDashboard:
    def test_collect_all_with_all_subsystems(self) -> None:
        pipeline = build_pipeline()
        wf = WorkforceOrchestrator()
        wf.hire_default_workforce()
        ev = EvaluationOrchestrator()
        ev.load_builtin_scenarios()
        b = ev.create_full_benchmark()
        ev.benchmark(b, version="1.0.0")

        c = DashboardDataCollector(
            providers=pipeline.providers,
            memory=pipeline.memory,
            knowledge=pipeline.knowledge,
            mcp=pipeline.mcp,
            workforce=wf.manager,
            evaluation=ev,
        )
        all_data = c.collect_all()

        # Verify every section has real data
        assert all_data["ai"]["provider_count"] == 6
        assert all_data["workforce"]["total_workers"] == 17
        assert all_data["evaluation"]["runs"] == 1
        assert all_data["evaluation"]["scenarios"] == 10

    def test_dashboard_logs_lifecycle(self) -> None:
        c = DashboardDataCollector()
        # Add logs
        c.add_log("info", "Started", "system")
        c.add_log("warning", "High CPU", "monitor")
        c.add_log("error", "Failed", "execution")
        # Search
        assert len(c.logs(search="CPU")) == 1
        # Filter
        assert len(c.logs(level="error")) == 1
        # Export
        exported = c.export_logs()
        assert len(exported) == 3
        # Clear
        assert c.clear_logs() == 3
        assert len(c.logs()) == 0

    def test_ai_cost_tracking_integration(self) -> None:
        pipeline = build_pipeline()
        c = DashboardDataCollector(providers=pipeline.providers)
        # Make a real call
        pipeline.providers.generate("Hello")
        data = c.ai_metrics()
        assert data["call_count"] == 1
        assert data["total_tokens_in"] > 0
        assert data["total_cost_usd"] > 0.0

    def test_workforce_after_task_execution(self) -> None:
        wf = WorkforceOrchestrator()
        wf.hire_default_workforce()
        wf.execute_goal("Test goal")
        c = DashboardDataCollector(workforce=wf.manager)
        data = c.workforce_metrics()
        # After execution, some workers may have completed tasks
        assert data["total_workers"] == 17
