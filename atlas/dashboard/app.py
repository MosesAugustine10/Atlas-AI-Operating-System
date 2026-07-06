"""Atlas Dashboard API — FastAPI backend with WebSocket live updates.

Provides REST endpoints for health, status, providers, agents, tools,
workflows, memory, knowledge, events, runtime, executions, artifacts,
and live updates. No frontend — only the backend API.

Usage::

    from atlas.dashboard import create_app
    app = create_app()
    # Run with: uvicorn atlas.dashboard.app:app
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_app(
    brain: Any = None,
    mcp_manager: Any = None,
    provider_manager: Any = None,
    memory: Any = None,
    knowledge: Any = None,
    event_bus: Any = None,
    artifact_manager: Any = None,
    stream_manager: Any = None,
    system_controller: Any = None,
    workforce: Any = None,
    collaboration: Any = None,
    execution: Any = None,
    creator_pipeline: Any = None,
    evaluation: Any = None,
) -> Any:
    """Create a FastAPI application wired to Atlas subsystems.

    All parameters are optional — missing subsystems return empty
    responses.

    Returns:
        A :class:`fastapi.FastAPI` instance.
    """
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware

    from atlas.dashboard.collector import DashboardDataCollector

    app = FastAPI(
        title="Atlas Dashboard API",
        description="Backend API for the Atlas AI Operating System",
        version="2.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger = get_logger("dashboard")

    # Build the data collector that aggregates real metrics.
    collector = DashboardDataCollector(
        system_controller=system_controller,
        providers=provider_manager,
        workforce=workforce,
        collaboration=collaboration,
        execution=execution,
        memory=memory,
        knowledge=knowledge,
        mcp=mcp_manager,
        creator_pipeline=creator_pipeline,
        evaluation=evaluation,
        event_bus=event_bus,
    )

    # Store subsystems in app state.
    app.state.brain = brain
    app.state.mcp = mcp_manager
    app.state.providers = provider_manager
    app.state.memory = memory
    app.state.knowledge = knowledge
    app.state.event_bus = event_bus
    app.state.artifacts = artifact_manager
    app.state.stream = stream_manager
    app.state.collector = collector

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Return overall health status."""
        status: dict[str, Any] = {
            "status": "healthy",
            "timestamp": _utcnow().isoformat(),
        }
        if mcp_manager is not None:
            status["mcp"] = mcp_manager.overall_health().value
        if provider_manager is not None:
            try:
                status["providers"] = provider_manager.health()
            except Exception:  # noqa: BLE001
                status["providers"] = {}
        return status

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @app.get("/status")
    async def status() -> dict[str, Any]:
        """Return system status summary."""
        s: dict[str, Any] = {"timestamp": _utcnow().isoformat()}
        if brain is not None:
            s["brain"] = brain.status()
        if mcp_manager is not None:
            stats = mcp_manager.statistics()
            s["mcp"] = {
                "connectors": stats.connectors_total,
                "connected": stats.connectors_connected,
                "requests": stats.requests_total,
            }
        if artifact_manager is not None:
            s["artifacts"] = artifact_manager.count()
            s["artifact_types"] = artifact_manager.count_by_type()
        return s

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    @app.get("/providers")
    async def providers() -> dict[str, Any]:
        """List registered providers."""
        if provider_manager is None:
            return {"providers": []}
        try:
            registry = provider_manager.registry
            return {
                "providers": [
                    {"name": p.name, "available": p.available} for p in registry.all()
                ]
            }
        except Exception:  # noqa: BLE001
            return {"providers": []}

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    @app.get("/agents")
    async def agents() -> dict[str, Any]:
        """List available agents."""
        from atlas.agents.live import ALL_LIVE_AGENTS

        return {
            "agents": [
                {"name": cls.__name__, "role": cls.__name__} for cls in ALL_LIVE_AGENTS
            ]
        }

    # ------------------------------------------------------------------
    # Tools / MCP
    # ------------------------------------------------------------------

    @app.get("/tools")
    async def tools() -> dict[str, Any]:
        """List registered MCP connectors and their capabilities."""
        if mcp_manager is None:
            return {"connectors": []}
        connectors = []
        for name in mcp_manager.connector_names():
            connector = mcp_manager.registry.get_optional(name)
            caps = []
            if connector is not None:
                caps = [c.name for c in connector.capabilities()]
            connectors.append(
                {
                    "name": name,
                    "connected": connector.is_connected if connector else False,
                    "capabilities": caps,
                }
            )
        return {"connectors": connectors}

    # ------------------------------------------------------------------
    # Workflows
    # ------------------------------------------------------------------

    @app.get("/workflows")
    async def workflows() -> dict[str, Any]:
        """List registered workflows."""
        return {"workflows": []}

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    @app.get("/memory")
    async def memory_endpoint() -> dict[str, Any]:
        """Return memory statistics."""
        if memory is None:
            return {"entries": 0, "stores": {}}
        try:
            stores: dict[str, int] = {}
            for attr in ("working", "episodic", "semantic", "procedural", "reflection"):
                store = getattr(memory, attr, None)
                if store is not None:
                    stores[attr] = len(store) if hasattr(store, "__len__") else 0
            return {"entries": sum(stores.values()), "stores": stores}
        except Exception:  # noqa: BLE001
            return {"entries": 0, "stores": {}}

    # ------------------------------------------------------------------
    # Knowledge
    # ------------------------------------------------------------------

    @app.get("/knowledge")
    async def knowledge_endpoint() -> dict[str, Any]:
        """Return knowledge statistics."""
        if knowledge is None:
            return {"documents": 0}
        try:
            count_fn = getattr(knowledge, "count", None)
            count = count_fn() if callable(count_fn) else 0
            return {"documents": count}
        except Exception:  # noqa: BLE001
            return {"documents": 0}

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    @app.get("/events")
    async def events(limit: int = 50) -> dict[str, Any]:
        """Return recent events."""
        if event_bus is None:
            return {"events": []}
        history = event_bus.history()
        recent = history[-limit:]
        return {
            "events": [
                {
                    "type": type(e).__name__,
                    "timestamp": (
                        e.timestamp.isoformat() if hasattr(e, "timestamp") else ""
                    ),
                    "execution_id": getattr(e, "execution_id", None),
                }
                for e in recent
            ],
            "total": len(history),
        }

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    @app.get("/runtime")
    async def runtime() -> dict[str, Any]:
        """Return runtime statistics."""
        return {"timestamp": _utcnow().isoformat()}

    # ------------------------------------------------------------------
    # Executions
    # ------------------------------------------------------------------

    @app.get("/executions")
    async def executions() -> dict[str, Any]:
        """Return recent executions."""
        if brain is None:
            return {"executions": []}
        try:
            goals = brain.goal_manager.terminal_goals()
            return {
                "executions": [
                    {
                        "goal_id": g.id,
                        "description": g.description[:60],
                        "status": g.status.value,
                        "completed_at": (
                            g.completed_at.isoformat() if g.completed_at else None
                        ),
                    }
                    for g in goals[-20:]
                ]
            }
        except Exception:  # noqa: BLE001
            return {"executions": []}

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    @app.get("/artifacts")
    async def artifacts(limit: int = 50) -> dict[str, Any]:
        """List recent artifacts."""
        if artifact_manager is None:
            return {"artifacts": [], "count": 0}
        arts = artifact_manager.list(limit=limit)
        return {
            "artifacts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.artifact_type.value,
                    "source": a.source,
                    "created_at": a.created_at.isoformat(),
                }
                for a in arts
            ],
            "count": artifact_manager.count(),
        }

    # ------------------------------------------------------------------
    # Live (WebSocket)
    # ------------------------------------------------------------------

    @app.websocket("/live")
    async def live(websocket: WebSocket) -> None:
        """WebSocket endpoint for live updates."""
        await websocket.accept()
        logger.info("WebSocket client connected")

        # Subscribe to the event bus.
        events: list[str] = []

        def listener(event: Any) -> None:
            events.append(
                json.dumps(
                    {
                        "type": type(event).__name__,
                        "timestamp": (
                            getattr(event, "timestamp", _utcnow()).isoformat()
                            if hasattr(event, "timestamp")
                            else _utcnow().isoformat()
                        ),
                        "data": {
                            k: v
                            for k, v in event.__dict__.items()
                            if k not in ("event_id", "timestamp")
                            and isinstance(v, (str, int, float, bool, type(None)))
                        },
                    }
                )
            )

        if event_bus is not None:
            from atlas.live.event_bus import LiveEvent

            event_bus.subscribe(LiveEvent, lambda e: listener(e))

        try:
            while True:
                # Send any pending events.
                while events:
                    await websocket.send_text(events.pop(0))
                # Keep connection alive.
                await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as exc:  # noqa: BLE001
            logger.warning("WebSocket error: %s", exc)

    @app.get("/live")
    async def live_poll() -> dict[str, Any]:
        """Polling fallback for live updates (returns recent events)."""
        if event_bus is None:
            return {"events": []}
        history = event_bus.history()
        return {
            "events": [
                {
                    "type": type(e).__name__,
                    "timestamp": (
                        e.timestamp.isoformat() if hasattr(e, "timestamp") else ""
                    ),
                }
                for e in history[-10:]
            ]
        }

    # ------------------------------------------------------------------
    # Professional Dashboard Endpoints (v2.0)
    # ------------------------------------------------------------------

    @app.get("/dashboard/system")
    async def dashboard_system() -> dict[str, Any]:
        """Return real CPU, RAM, GPU, disk, network, process metrics."""
        return collector.system_metrics()

    @app.get("/dashboard/ai")
    async def dashboard_ai() -> dict[str, Any]:
        """Return real provider, model, token, and cost metrics."""
        return collector.ai_metrics()

    @app.get("/dashboard/workforce")
    async def dashboard_workforce() -> dict[str, Any]:
        """Return real worker, task, and productivity metrics."""
        return collector.workforce_metrics()

    @app.get("/dashboard/execution")
    async def dashboard_execution() -> dict[str, Any]:
        """Return real workflow, task, and pipeline metrics."""
        return collector.execution_metrics()

    @app.get("/dashboard/memory")
    async def dashboard_memory() -> dict[str, Any]:
        """Return real memory store metrics."""
        return collector.memory_metrics()

    @app.get("/dashboard/knowledge")
    async def dashboard_knowledge() -> dict[str, Any]:
        """Return real knowledge engine metrics."""
        return collector.knowledge_metrics()

    @app.get("/dashboard/mcp")
    async def dashboard_mcp() -> dict[str, Any]:
        """Return real MCP connector metrics."""
        return collector.mcp_metrics()

    @app.get("/dashboard/creator")
    async def dashboard_creator() -> dict[str, Any]:
        """Return real creator pipeline metrics."""
        return collector.creator_metrics()

    @app.get("/dashboard/evaluation")
    async def dashboard_evaluation() -> dict[str, Any]:
        """Return real evaluation metrics."""
        return collector.evaluation_metrics()

    @app.get("/dashboard/logs")
    async def dashboard_logs(
        level: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Return log entries with optional filtering."""
        return {"logs": collector.logs(level=level, search=search, limit=limit)}

    @app.post("/dashboard/logs")
    async def dashboard_add_log(
        level: str, message: str, source: str = ""
    ) -> dict[str, Any]:
        """Add a log entry."""
        collector.add_log(level=level, message=message, source=source)
        return {"status": "ok"}

    @app.get("/dashboard/logs/export")
    async def dashboard_export_logs() -> dict[str, Any]:
        """Export all log entries."""
        return {"logs": collector.export_logs()}

    @app.delete("/dashboard/logs")
    async def dashboard_clear_logs() -> dict[str, Any]:
        """Clear all logs."""
        count = collector.clear_logs()
        return {"cleared": count}

    @app.get("/dashboard/all")
    async def dashboard_all() -> dict[str, Any]:
        """Return every dashboard section at once."""
        return collector.collect_all()

    return app


__all__ = ["create_app"]
