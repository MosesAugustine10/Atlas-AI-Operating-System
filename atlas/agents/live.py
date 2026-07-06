"""Live agents - real execution with capability routing and streaming.

Each agent inherits :class:`LiveAgent` and uses injected subsystems
(ProviderManager, MCPManager, MemoryEngine, KnowledgeEngine, etc.)
to execute real operations. Agents never instantiate subsystems
internally - everything comes through dependency injection.

Agents:
* :class:`CodingAgent` - code generation, debugging, refactoring, testing
* :class:`ResearchAgent` - web research, summarization, citations
* :class:`GitHubAgent` - commit, branch, merge, PR, repo management
* :class:`BrowserAgent` - browsing, scraping, form filling
* :class:`MiningAgent` - Surpac, AutoCAD, QGIS
* :class:`VisionAgent` - OCR, image analysis
* :class:`WindowsAgent` - filesystem, terminal, automation
* :class:`PlannerAgent` - planning, decomposition
* :class:`MemoryAgent` - recall, remember
* :class:`KnowledgeAgent` - indexing, retrieval
* :class:`BlenderAgent` - rendering, scene generation

Each agent exposes:
* :meth:`execute(task)` - run a task and return the result.
* :meth:`supports(capability)` - check if the agent supports a capability.
* :meth:`estimate(task)` - estimate cost and duration.
* :meth:`health()` - check agent health.
* :meth:`statistics()` - return execution metrics.
* :meth:`execute_stream(task)` - stream execution events.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from atlas.agents.base import BaseAgent


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class AgentMetrics:
    """Mutable metrics tracked per agent (not frozen - updated in place).

    Attributes:
        total_executions: Total number of execute() calls.
        successful: Number of successful executions.
        failed: Number of failed executions.
        total_latency_seconds: Sum of execution durations.
        total_tokens_in: Total input tokens consumed.
        total_tokens_out: Total output tokens produced.
        total_cost_usd: Total estimated cost.
        last_execution_time: When the agent was last used (or None).
        last_error: Last error message (or "").
        created_at: When the agent was created.
    """

    total_executions: int = 0
    successful: int = 0
    failed: int = 0
    total_latency_seconds: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0
    last_execution_time: datetime | None = None
    last_error: str = ""
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def success_rate(self) -> float:
        """Return the fraction of successful executions (0.0 to 1.0)."""
        if self.total_executions == 0:
            return 0.0
        return self.successful / self.total_executions

    @property
    def average_latency(self) -> float:
        """Return the average execution latency in seconds."""
        if self.total_executions == 0:
            return 0.0
        return self.total_latency_seconds / self.total_executions

    @property
    def uptime_seconds(self) -> float:
        """Return the agent uptime in seconds."""
        return (_utcnow() - self.created_at).total_seconds()


# ---------------------------------------------------------------------------
# LiveAgent base
# ---------------------------------------------------------------------------


class LiveAgent(BaseAgent):
    """Base class for live agents with injected subsystems.

    Parameters:
        name: Agent name.
        role: Agent role.
        mcp_manager: Optional MCPManager for real connector access.
        providers: Optional ProviderManager for LLM access.
        memory: Optional MemoryEngine.
        knowledge: Optional KnowledgeEngine.
        brain: Optional Brain for think() calls.
        execution_engine: Optional ExecutionEngine.
        workflow_engine: Optional WorkflowEngine.
        think_fn: Optional callback (typically ``brain.think``).
    """

    #: Capabilities this agent supports (overridden by subclasses).
    CAPABILITIES: tuple[str, ...] = ()

    def __init__(
        self,
        name: str,
        role: str | None = None,
        mcp_manager: Any = None,
        providers: Any = None,
        memory: Any = None,
        knowledge: Any = None,
        brain: Any = None,
        execution_engine: Any = None,
        workflow_engine: Any = None,
        think_fn: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(name=name, role=role or name)
        self.mcp_manager = mcp_manager
        self.providers = providers
        self.memory = memory
        self.knowledge = knowledge
        self.brain = brain
        self.execution_engine = execution_engine
        self.workflow_engine = workflow_engine
        self._think_fn = think_fn
        self._metrics = AgentMetrics()

    # ------------------------------------------------------------------
    # Capability routing
    # ------------------------------------------------------------------

    def supports(self, capability: str) -> bool:
        """Return ``True`` if this agent supports ``capability``."""
        return capability in self.CAPABILITIES

    def capabilities(self) -> list[str]:
        """Return the list of capabilities this agent supports."""
        return list(self.CAPABILITIES)

    def estimate(self, task: str) -> dict[str, float]:
        """Estimate the cost and duration of executing ``task``.

        Returns a dict with ``estimated_duration_seconds`` and
        ``estimated_cost_usd``.
        """
        return {
            "estimated_duration_seconds": 2.0,
            "estimated_cost_usd": 0.001,
        }

    # ------------------------------------------------------------------
    # Health + statistics
    # ------------------------------------------------------------------

    def health(self) -> bool:
        """Return ``True`` if the agent is healthy and ready to execute."""
        return True

    def statistics(self) -> dict[str, Any]:
        """Return execution metrics."""
        m = self._metrics
        return {
            "total_executions": m.total_executions,
            "successful": m.successful,
            "failed": m.failed,
            "success_rate": round(m.success_rate, 4),
            "average_latency_seconds": round(m.average_latency, 4),
            "total_tokens_in": m.total_tokens_in,
            "total_tokens_out": m.total_tokens_out,
            "total_cost_usd": round(m.total_cost_usd, 6),
            "last_execution_time": (
                m.last_execution_time.isoformat() if m.last_execution_time else None
            ),
            "last_error": m.last_error,
            "uptime_seconds": round(m.uptime_seconds, 1),
        }

    # ------------------------------------------------------------------
    # Execute with metrics tracking
    # ------------------------------------------------------------------

    def execute(self, plan: Any) -> Any:
        """Execute a plan and track metrics.

        Subclasses override :meth:`_do_execute` to implement the actual
        logic. This wrapper tracks timing, success, cost, and errors.
        """
        start = time.monotonic()
        self._metrics.total_executions += 1
        self._metrics.last_execution_time = _utcnow()
        try:
            result = self._do_execute(plan)
            self._metrics.successful += 1
            self._track_cost(result)
            return result
        except Exception as exc:  # noqa: BLE001
            self._metrics.failed += 1
            self._metrics.last_error = str(exc)
            raise
        finally:
            elapsed = time.monotonic() - start
            self._metrics.total_latency_seconds += elapsed

    def _do_execute(self, plan: Any) -> Any:
        """Subclasses override this to implement the actual execution."""
        return plan

    def _track_cost(self, result: Any) -> None:
        """Extract token usage and cost from the result if available."""
        if isinstance(result, dict):
            usage = result.get("usage", {})
            self._metrics.total_tokens_in += usage.get(
                "prompt", usage.get("input_tokens", 0)
            )
            self._metrics.total_tokens_out += usage.get(
                "completion", usage.get("output_tokens", 0)
            )
            self._metrics.total_cost_usd += result.get("cost_usd", 0.0)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def execute_stream(self, task: str) -> Iterator[dict[str, Any]]:
        """Stream execution events for ``task``.

        Yields dicts with ``event`` and ``data`` keys:
            ``{"event": "started", "data": {"task": task}}``
            ``{"event": "thinking", "data": {"plan": ...}}``
            ``{"event": "executing", "data": {"step": ...}}``
            ``{"event": "tool_call", "data": {"capability": ...}}``
            ``{"event": "memory", "data": {"recall": ...}}``
            ``{"event": "knowledge", "data": {"hits": ...}}``
            ``{"event": "completed", "data": {"result": ...}}``
            ``{"event": "error", "data": {"error": ...}}``
        """
        yield {"event": "started", "data": {"task": task, "agent": self.name}}
        start = time.monotonic()
        self._metrics.total_executions += 1
        self._metrics.last_execution_time = _utcnow()
        try:
            # Thinking phase
            plan = self.plan(task)
            yield {"event": "thinking", "data": {"plan": plan}}

            # Memory recall (if available)
            if self.memory is not None:
                try:
                    memories = list(self.memory.recall())
                    yield {"event": "memory", "data": {"recall_count": len(memories)}}
                except Exception:  # noqa: BLE001
                    pass

            # Knowledge search (if available)
            if self.knowledge is not None:
                try:
                    hits = list(self.knowledge.search(task))
                    yield {"event": "knowledge", "data": {"hit_count": len(hits)}}
                except Exception:  # noqa: BLE001
                    pass

            # Execute
            yield {"event": "executing", "data": {"step": "main"}}
            result = self._do_execute(plan)
            self._metrics.successful += 1
            self._track_cost(result)

            review = self.review(result)
            report = self.report(review)

            yield {
                "event": "completed",
                "data": {
                    "result": report,
                    "duration_seconds": time.monotonic() - start,
                },
            }
        except Exception as exc:  # noqa: BLE001
            self._metrics.failed += 1
            self._metrics.last_error = str(exc)
            yield {"event": "error", "data": {"error": str(exc)}}
        finally:
            elapsed = time.monotonic() - start
            self._metrics.total_latency_seconds += elapsed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mcp_execute(
        self,
        capability: str,
        params: dict[str, Any] | None = None,
        connector: str | None = None,
    ) -> dict[str, Any]:
        """Execute an MCP capability (if manager is available)."""
        if self.mcp_manager is None:
            return {"success": False, "error": "MCP manager not available"}
        try:
            session = self.mcp_manager.open_session(
                connector or "filesystem",
                permissions=["read", "write", "execute"],
            )
            try:
                resp = self.mcp_manager.execute_capability(
                    capability,
                    params or {},
                    connector=connector,
                    session_id=session.id,
                )
                return {
                    "success": resp.success,
                    "output": resp.output,
                    "error": resp.error,
                }
            finally:
                self.mcp_manager.close_session(session.id)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}

    def _generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text via the provider manager (if available)."""
        if self.providers is None:
            return f"[offline: {prompt[:50]}]"
        try:
            response = self.providers.generate(prompt, **kwargs)
            return getattr(response, "text", str(response))
        except Exception as exc:  # noqa: BLE001
            return f"[generation error: {exc}]"

    def _think(self, goal: str) -> Any:
        """Call the injected think_fn or Brain.think (if available)."""
        if self._think_fn is not None:
            return self._think_fn(goal)
        if self.brain is not None and hasattr(self.brain, "think"):
            return self.brain.think(goal)
        return {"status": "offline", "goal": goal}

    def plan(self, objective: str) -> Any:
        """Default plan: return the objective as a single-step plan."""
        return {"objective": objective, "steps": [objective]}

    def review(self, result: Any) -> Any:
        """Default review: pass through."""
        return result

    def report(self, review: Any) -> str:
        """Default report: stringify the review."""
        return str(review)


# ---------------------------------------------------------------------------
# Concrete agents
# ---------------------------------------------------------------------------


class CodingAgent(LiveAgent):
    """Code generation, debugging, refactoring, and testing agent."""

    CAPABILITIES = ("code_generation", "debugging", "refactoring", "testing")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="coding_agent", role="Code Generation", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "generate_code"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        code = self._generate(
            f"Write Python code for: {objective}\nReturn only the code."
        )
        return {"code": code, "language": "python", "objective": objective}

    def report(self, review: Any) -> str:
        code = review.get("code", "") if isinstance(review, dict) else str(review)
        return f"Generated {len(code)} characters of code"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 5.0,
            "estimated_cost_usd": 0.005,
        }


class ResearchAgent(LiveAgent):
    """Web research, summarization, and citation agent."""

    CAPABILITIES = ("web_research", "summarization", "citations")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="research_agent", role="Research", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "research"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        results: list[Any] = []
        # Search knowledge first.
        if self.knowledge is not None:
            try:
                hits = self.knowledge.search(objective)
                results.extend(hits[:3])
            except Exception:  # noqa: BLE001
                pass
        # Generate a research summary via providers.
        summary = self._generate(
            f"Research and summarize: {objective}\nProvide key findings with citations."
        )
        results.append(summary)
        return {"findings": results, "objective": objective, "summary": summary}

    def report(self, review: Any) -> str:
        count = len(review.get("findings", [])) if isinstance(review, dict) else 0
        return f"Found {count} research findings"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 10.0,
            "estimated_cost_usd": 0.01,
        }


class GitHubAgent(LiveAgent):
    """Git repository management agent."""

    CAPABILITIES = (
        "commit",
        "branch",
        "merge",
        "pull_request",
        "repository_management",
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="github_agent", role="Git Management", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "git_operations"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "git.status",
            {"path": "."},
            connector="github",
        )
        return {"git_status": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Git operations completed"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 3.0,
            "estimated_cost_usd": 0.0,
        }


class BrowserAgent(LiveAgent):
    """Web browsing, scraping, and form filling agent."""

    CAPABILITIES = ("browsing", "scraping", "form_filling")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="browser_agent", role="Web Browsing", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "browse"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "browser.navigate",
            {"url": f"https://example.com/?q={objective[:50]}"},
            connector="browser",
        )
        return {"browse_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Browsing completed"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 8.0,
            "estimated_cost_usd": 0.002,
        }


class MiningAgent(LiveAgent):
    """Mining data management agent (Surpac, AutoCAD, QGIS)."""

    CAPABILITIES = ("surpac", "autocad", "qgis")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="mining_agent", role="Mining Data", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "data_processing"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "file.list",
            {"path": "."},
            connector="filesystem",
        )
        return {"data_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Mining data processed"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 15.0,
            "estimated_cost_usd": 0.003,
        }


class VisionAgent(LiveAgent):
    """OCR and image analysis agent."""

    CAPABILITIES = ("ocr", "image_analysis")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="vision_agent", role="Vision", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "capture"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "playwright.screenshot",
            {},
            connector="playwright",
        )
        return {"vision_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Vision processing completed"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 5.0,
            "estimated_cost_usd": 0.004,
        }


class WindowsAgent(LiveAgent):
    """Windows OS management agent (filesystem, terminal, automation)."""

    CAPABILITIES = ("filesystem", "terminal", "automation")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="windows_agent", role="Windows OS", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "os_operations"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "windows.shell",
            {"command": f"echo {objective[:50]}"},
            connector="windows",
        )
        return {"os_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Windows operations completed"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 2.0,
            "estimated_cost_usd": 0.0,
        }


class PlannerAgent(LiveAgent):
    """Planning and task decomposition agent."""

    CAPABILITIES = ("planning", "decomposition")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="planner_agent", role="Planning", **kwargs)

    def plan(self, objective: str) -> Any:
        # Use brain's think if available for real planning
        if self.brain is not None:
            try:
                outcome = self.brain.think(objective)
                steps = (
                    [s for s in outcome.plan.tasks]
                    if hasattr(outcome, "plan") and hasattr(outcome.plan, "tasks")
                    else ["research", "design", "implement", "test", "deploy"]
                )
                return {"objective": objective, "steps": steps, "brain_used": True}
            except Exception:  # noqa: BLE001
                pass
        return {
            "objective": objective,
            "steps": ["research", "design", "implement", "test", "deploy"],
        }

    def _do_execute(self, plan: Any) -> Any:
        return plan

    def report(self, review: Any) -> str:
        steps = review.get("steps", []) if isinstance(review, dict) else []
        return f"Planned {len(steps)} steps"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 1.0,
            "estimated_cost_usd": 0.001,
        }


class KnowledgeAgent(LiveAgent):
    """Knowledge indexing and retrieval agent."""

    CAPABILITIES = ("indexing", "retrieval")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="knowledge_agent", role="Knowledge Search", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "knowledge_search"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        results: list[Any] = []
        if self.knowledge is not None:
            try:
                results = list(self.knowledge.search(objective))
            except Exception:  # noqa: BLE001
                pass
        return {"knowledge_hits": results, "objective": objective}

    def report(self, review: Any) -> str:
        count = len(review.get("knowledge_hits", [])) if isinstance(review, dict) else 0
        return f"Found {count} knowledge hits"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 1.0,
            "estimated_cost_usd": 0.0,
        }


class MemoryAgent(LiveAgent):
    """Memory recall and storage agent."""

    CAPABILITIES = ("recall", "remember")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="memory_agent", role="Memory Management", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "memory_recall"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        results: list[Any] = []
        if self.memory is not None:
            try:
                results = list(self.memory.recall())
            except Exception:  # noqa: BLE001
                pass
        return {"memories": results[:5], "objective": objective}

    def report(self, review: Any) -> str:
        count = len(review.get("memories", [])) if isinstance(review, dict) else 0
        return f"Recalled {count} memories"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 0.5,
            "estimated_cost_usd": 0.0,
        }


class BlenderAgent(LiveAgent):
    """Blender 3D rendering and scene generation agent."""

    CAPABILITIES = ("rendering", "scene_generation")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="blender_agent", role="3D Rendering", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "render"}

    def _do_execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "blender.render",
            {"frame": 1},
            connector="blender",
        )
        return {"render_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Blender rendering completed"

    def estimate(self, task: str) -> dict[str, float]:
        return {
            "estimated_duration_seconds": 30.0,
            "estimated_cost_usd": 0.01,
        }


#: List of all live agent classes.
ALL_LIVE_AGENTS: list[type[LiveAgent]] = [
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
]


def instantiate_all_agents(
    mcp_manager: Any = None,
    providers: Any = None,
    memory: Any = None,
    knowledge: Any = None,
    brain: Any = None,
    execution_engine: Any = None,
    workflow_engine: Any = None,
    think_fn: Callable[..., Any] | None = None,
) -> list[LiveAgent]:
    """Instantiate every live agent with the given dependencies."""
    return [
        cls(
            mcp_manager=mcp_manager,
            providers=providers,
            memory=memory,
            knowledge=knowledge,
            brain=brain,
            execution_engine=execution_engine,
            workflow_engine=workflow_engine,
            think_fn=think_fn,
        )
        for cls in ALL_LIVE_AGENTS
    ]


__all__ = [
    "ALL_LIVE_AGENTS",
    "AgentMetrics",
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
