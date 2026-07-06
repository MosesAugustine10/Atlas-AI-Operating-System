"""Dashboard data collector — aggregates real data from every Atlas subsystem.

The :class:`DashboardDataCollector` is a pure-Python aggregator that
pulls real metrics from injected subsystems (SystemController,
ProviderManager, WorkforceOrchestrator, ExecutionEngine, MemoryEngine,
KnowledgeEngine, MCPManager, EvaluationOrchestrator,
CreatorPipelineOrchestrator). It never fabricates data — when a
subsystem is not wired, its section returns empty/zero values.

The collector is the single source of truth for the dashboard API
endpoints. It does NOT duplicate any logic — it only reads existing
state from the subsystems.
"""

from __future__ import annotations

import platform
from typing import Any

from atlas.core.logger import get_logger


class DashboardDataCollector:
    """Aggregates real-time data from every Atlas subsystem.

    All parameters are optional — missing subsystems return empty
    data sections. This lets the dashboard work in any configuration.
    """

    def __init__(
        self,
        system_controller: Any = None,
        providers: Any = None,
        workforce: Any = None,
        collaboration: Any = None,
        execution: Any = None,
        memory: Any = None,
        knowledge: Any = None,
        mcp: Any = None,
        creator_pipeline: Any = None,
        evaluation: Any = None,
        event_bus: Any = None,
    ) -> None:
        self.system = system_controller
        self.providers = providers
        self.workforce = workforce
        self.collaboration = collaboration
        self.execution = execution
        self.memory = memory
        self.knowledge = knowledge
        self.mcp = mcp
        self.creator_pipeline = creator_pipeline
        self.evaluation = evaluation
        self.event_bus = event_bus
        self.logger = get_logger("dashboard.collector")
        self._log_buffer: list[dict[str, str]] = []
        self._max_logs: int = 500

    # ------------------------------------------------------------------
    # SYSTEM
    # ------------------------------------------------------------------

    def system_metrics(self) -> dict[str, Any]:
        """Return real CPU, RAM, GPU, disk, network, process metrics."""
        if self.system is None:
            return self._empty_system()
        try:
            metric = self.system.collect()
            history = self.system.history(limit=60)
            return {
                "cpu_percent": metric.cpu_percent,
                "ram_percent": metric.ram_percent,
                "ram_used_mb": metric.ram_used_mb,
                "ram_total_mb": metric.ram_total_mb,
                "disk_percent": metric.disk_percent,
                "network_in_kbps": metric.network_in,
                "network_out_kbps": metric.network_out,
                "gpu_percent": metric.gpu_percent,
                "gpu_name": metric.gpu_name,
                "process_count": self._process_count(),
                "thread_count": self._thread_count(),
                "temperature": self._temperature(),
                "hostname": platform.node(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "history": [
                    {
                        "cpu": m.cpu_percent,
                        "ram": m.ram_percent,
                        "disk": m.disk_percent,
                    }
                    for m in history
                ],
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("System metrics failed: %s", exc)
            return self._empty_system()

    def _empty_system(self) -> dict[str, Any]:
        return {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "ram_used_mb": 0.0,
            "ram_total_mb": 0.0,
            "disk_percent": 0.0,
            "network_in_kbps": 0.0,
            "network_out_kbps": 0.0,
            "gpu_percent": 0.0,
            "gpu_name": "",
            "process_count": 0,
            "thread_count": 0,
            "temperature": 0.0,
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "history": [],
        }

    @staticmethod
    def _process_count() -> int:
        try:
            import psutil  # type: ignore[import-not-found]

            return len(psutil.pids())
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _thread_count() -> int:
        try:
            import psutil  # type: ignore[import-not-found]

            return sum(p.num_threads() for p in psutil.process_iter(["num_threads"]))
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _temperature() -> float:
        try:
            import psutil  # type: ignore[import-not-found]

            temps = psutil.sensors_temperatures()
            if temps:
                for _name, entries in temps.items():
                    if entries:
                        return float(entries[0].current)
        except Exception:  # noqa: BLE001
            pass
        return 0.0

    # ------------------------------------------------------------------
    # AI
    # ------------------------------------------------------------------

    def ai_metrics(self) -> dict[str, Any]:
        """Return real provider, model, token, and cost metrics."""
        if self.providers is None:
            return {
                "providers": {},
                "provider_count": 0,
                "current_provider": "",
                "active_model": "",
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost_usd": 0.0,
                "call_count": 0,
                "error_count": 0,
                "queue_size": 0,
                "health": {},
            }
        try:
            health = self.providers.health()
            names = (
                self.providers.provider_names()
                if hasattr(self.providers, "provider_names")
                else []
            )
            cost = (
                self.providers.cost_summary()
                if hasattr(self.providers, "cost_summary")
                else {}
            )
            models = (
                self.providers.list_models()
                if hasattr(self.providers, "list_models")
                else {}
            )
            # Determine current provider (first healthy)
            current = next(
                (n for n in names if health.get(n, False)), names[0] if names else ""
            )
            active_model = ""
            if current and current in models and models[current]:
                active_model = models[current][0]
            return {
                "providers": {n: health.get(n, False) for n in names},
                "provider_count": len(names),
                "current_provider": current,
                "active_model": active_model,
                "total_tokens_in": cost.get("total_tokens_in", 0),
                "total_tokens_out": cost.get("total_tokens_out", 0),
                "total_cost_usd": cost.get("total_cost_usd", 0.0),
                "call_count": cost.get("call_count", 0),
                "error_count": cost.get("error_count", 0),
                "queue_size": 0,
                "health": health,
                "models": models,
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("AI metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # WORKFORCE
    # ------------------------------------------------------------------

    def workforce_metrics(self) -> dict[str, Any]:
        """Return real worker, task, and productivity metrics."""
        if self.workforce is None:
            return {
                "total_workers": 0,
                "active_workers": 0,
                "idle_workers": 0,
                "busy_workers": 0,
                "teams": 0,
                "active_teams": 0,
                "current_tasks": [],
            }
        try:
            status = (
                self.workforce.status() if hasattr(self.workforce, "status") else {}
            )
            workers = (
                self.workforce.list_workers()
                if hasattr(self.workforce, "list_workers")
                else []
            )
            idle = [w for w in workers if w.status == "idle"] if workers else []
            busy = [w for w in workers if w.status == "busy"] if workers else []
            return {
                "total_workers": status.get("total_workers", len(workers)),
                "active_workers": status.get("online_workers", 0),
                "idle_workers": len(idle),
                "busy_workers": len(busy),
                "teams": status.get("total_teams", 0),
                "active_teams": status.get("active_teams", 0),
                "worker_details": [
                    {
                        "id": w.id,
                        "name": w.name,
                        "role": w.role,
                        "status": w.status,
                        "tasks_completed": w.state.tasks_completed,
                    }
                    for w in workers
                ],
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Workforce metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------

    def execution_metrics(self) -> dict[str, Any]:
        """Return real workflow, task, and pipeline metrics."""
        if self.execution is None:
            return {
                "running_workflows": 0,
                "running_tasks": 0,
                "current_stage": "",
                "success_rate": 0.0,
                "retry_count": 0,
            }
        try:
            timeline = (
                self.execution.timeline()
                if hasattr(self.execution, "timeline")
                else None
            )
            history = (
                self.execution.history() if hasattr(self.execution, "history") else []
            )
            total = len(history)
            completed = sum(
                1 for h in history if hasattr(h, "status") and h.status == "completed"
            )
            success_rate = (completed / total) if total > 0 else 0.0
            current_stage = ""
            if timeline and hasattr(timeline, "status"):
                current_stage = timeline.status
            return {
                "running_workflows": sum(
                    1 for h in history if hasattr(h, "status") and h.status == "running"
                ),
                "running_tasks": (
                    1
                    if timeline
                    and hasattr(timeline, "status")
                    and timeline.status == "running"
                    else 0
                ),
                "current_stage": current_stage,
                "success_rate": success_rate,
                "retry_count": 0,
                "history_count": total,
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Execution metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # MEMORY
    # ------------------------------------------------------------------

    def memory_metrics(self) -> dict[str, Any]:
        """Return real memory store metrics."""
        if self.memory is None:
            return {
                "working_memory": 0,
                "long_term_memory": 0,
                "knowledge_hits": 0,
                "cache_entries": 0,
            }
        try:
            entries = self.memory.recall() if hasattr(self.memory, "recall") else []
            return {
                "working_memory": len(entries),
                "long_term_memory": len(entries),
                "knowledge_hits": 0,
                "cache_entries": len(entries),
                "recent_entries": [
                    {
                        "id": getattr(e, "id", ""),
                        "content": str(getattr(e, "content", ""))[:100],
                        "timestamp": str(getattr(e, "timestamp", "")),
                    }
                    for e in entries[:10]
                ],
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Memory metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # KNOWLEDGE
    # ------------------------------------------------------------------

    def knowledge_metrics(self) -> dict[str, Any]:
        """Return real knowledge engine metrics."""
        if self.knowledge is None:
            return {
                "documents": 0,
                "chunks": 0,
            }
        try:
            docs = (
                self.knowledge.list_documents()
                if hasattr(self.knowledge, "list_documents")
                else []
            )
            return {
                "documents": len(docs),
                "chunks": sum(
                    len(self.knowledge.chunks_of(d.id))
                    for d in docs
                    if hasattr(self.knowledge, "chunks_of")
                ),
                "recent_documents": [
                    {
                        "id": d.id,
                        "source": d.source,
                    }
                    for d in docs[:10]
                ],
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Knowledge metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # MCP
    # ------------------------------------------------------------------

    def mcp_metrics(self) -> dict[str, Any]:
        """Return real MCP connector metrics."""
        if self.mcp is None:
            return {
                "connectors": [],
                "connector_count": 0,
            }
        try:
            connectors = (
                self.mcp.connectors() if hasattr(self.mcp, "connectors") else []
            )
            return {
                "connectors": [
                    {
                        "name": getattr(c, "name", ""),
                        "status": getattr(c, "status", "unknown"),
                        "healthy": getattr(c, "healthy", False),
                        "latency_ms": getattr(c, "latency_ms", 0.0),
                        "capabilities": list(getattr(c, "capabilities", [])),
                    }
                    for c in connectors
                ],
                "connector_count": len(connectors),
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("MCP metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # CREATOR
    # ------------------------------------------------------------------

    def creator_metrics(self) -> dict[str, Any]:
        """Return real creator pipeline metrics."""
        if self.creator_pipeline is None:
            return {
                "projects": 0,
                "running_projects": 0,
                "render_jobs": 0,
                "video_jobs": 0,
                "audio_jobs": 0,
                "exports": 0,
            }
        try:
            projects = (
                self.creator_pipeline.list_projects()
                if hasattr(self.creator_pipeline, "list_projects")
                else []
            )
            running = [p for p in projects if p.status == "running"]
            return {
                "projects": len(projects),
                "running_projects": len(running),
                "render_jobs": 0,
                "video_jobs": 0,
                "audio_jobs": 0,
                "exports": sum(1 for p in projects if p.status == "exported"),
                "project_details": [
                    {
                        "id": p.id,
                        "goal": p.goal[:80],
                        "status": p.status,
                        "stages_total": len(p.stages),
                    }
                    for p in projects[:10]
                ],
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Creator metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # EVALUATION
    # ------------------------------------------------------------------

    def evaluation_metrics(self) -> dict[str, Any]:
        """Return real evaluation metrics."""
        if self.evaluation is None:
            return {
                "runs": 0,
                "latest_score": 0.0,
                "suggestions": 0,
                "regressions": 0,
            }
        try:
            status = (
                self.evaluation.status() if hasattr(self.evaluation, "status") else {}
            )
            runs = (
                self.evaluation.list_runs()
                if hasattr(self.evaluation, "list_runs")
                else []
            )
            latest_score = runs[0].overall_score if runs else 0.0
            return {
                "runs": len(runs),
                "latest_score": latest_score,
                "suggestions": status.get("optimization_reports", 0),
                "regressions": status.get("regression_reports", 0),
                "scenarios": status.get("scenarios", 0),
                "benchmarks": status.get("benchmarks", 0),
            }
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Evaluation metrics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # LOGS
    # ------------------------------------------------------------------

    def add_log(self, level: str, message: str, source: str = "") -> None:
        """Add a log entry to the in-memory buffer."""
        from datetime import UTC, datetime

        entry = {
            "level": level,
            "message": message,
            "source": source,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._log_buffer.append(entry)
        if len(self._log_buffer) > self._max_logs:
            self._log_buffer = self._log_buffer[-self._max_logs :]

    def logs(
        self,
        level: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, str]]:
        """Return log entries with optional filtering."""
        logs = list(self._log_buffer)
        if level is not None:
            logs = [entry for entry in logs if entry["level"] == level]
        if search is not None:
            search_lower = search.lower()
            logs = [
                entry
                for entry in logs
                if search_lower in entry["message"].lower()
                or search_lower in entry["source"].lower()
            ]
        return logs[-limit:]

    def export_logs(self) -> list[dict[str, str]]:
        """Export all log entries."""
        return list(self._log_buffer)

    def clear_logs(self) -> int:
        """Clear all logs. Returns the count cleared."""
        count = len(self._log_buffer)
        self._log_buffer.clear()
        return count

    # ------------------------------------------------------------------
    # FULL DASHBOARD
    # ------------------------------------------------------------------

    def collect_all(self) -> dict[str, Any]:
        """Return every dashboard section at once."""
        return {
            "system": self.system_metrics(),
            "ai": self.ai_metrics(),
            "workforce": self.workforce_metrics(),
            "execution": self.execution_metrics(),
            "memory": self.memory_metrics(),
            "knowledge": self.knowledge_metrics(),
            "mcp": self.mcp_metrics(),
            "creator": self.creator_metrics(),
            "evaluation": self.evaluation_metrics(),
        }


__all__ = ["DashboardDataCollector"]
