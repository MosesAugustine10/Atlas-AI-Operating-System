"""Coordinator — coordinates every Atlas subsystem.

The :class:`Coordinator` is the wiring layer between the Intelligence
Layer and the rest of Atlas. It holds injected handles to the Execution
Engine, Workflow Engine, Runtime, Provider Layer, Agent Framework, MCP,
Memory, and Knowledge — and exposes convenience methods that the
:class:`Brain` calls during the thinking pipeline.

The coordinator never imports concrete subsystem implementations; it
accepts duck-typed handles and calls standard methods (``handle``,
``run``, ``generate``, ``execute``, ``search``, ``recall``, etc.).
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.models import (
    DecisionCandidate,
)


class Coordinator:
    """Coordinates every Atlas subsystem.

    Parameters:
        execution: Optional Execution Engine (or compatible). Must
            have a ``run(goal)`` method.
        workflows: Optional Workflow Engine (or compatible). Must have
            ``create_run`` / ``start`` methods.
        runtime: Optional Runtime (or compatible). Must have a
            ``handle(request)`` method.
        providers: Optional Provider Manager (or compatible). Must have
            a ``generate(prompt)`` method.
        agents: Optional agent manager / router (or compatible).
        mcp: Optional MCP Manager (or compatible). Must have
            ``execute_capability`` method.
        memory: Optional Memory Engine (or compatible). Must have
            ``remember`` / ``recall`` methods.
        knowledge: Optional Knowledge Engine (or compatible). Must have
            a ``search`` method.
    """

    def __init__(
        self,
        execution: Any = None,
        workflows: Any = None,
        runtime: Any = None,
        providers: Any = None,
        agents: Any = None,
        mcp: Any = None,
        memory: Any = None,
        knowledge: Any = None,
    ) -> None:
        self.execution = execution
        self.workflows = workflows
        self.runtime = runtime
        self.providers = providers
        self.agents = agents
        self.mcp = mcp
        self.memory = memory
        self.knowledge = knowledge
        self.logger = get_logger("intelligence.coordinator")

    # ------------------------------------------------------------------
    # Availability checks
    # ------------------------------------------------------------------

    def has_execution(self) -> bool:
        return self.execution is not None

    def has_workflows(self) -> bool:
        return self.workflows is not None

    def has_runtime(self) -> bool:
        return self.runtime is not None

    def has_providers(self) -> bool:
        return self.providers is not None

    def has_agents(self) -> bool:
        return self.agents is not None

    def has_mcp(self) -> bool:
        return self.mcp is not None

    def has_memory(self) -> bool:
        return self.memory is not None

    def has_knowledge(self) -> bool:
        return self.knowledge is not None

    # ------------------------------------------------------------------
    # Knowledge & Memory
    # ------------------------------------------------------------------

    def search_knowledge(self, query: str) -> list[Any]:
        """Search the knowledge engine (if available)."""
        if self.knowledge is None:
            return []
        try:
            search_fn = getattr(self.knowledge, "search", None)
            if callable(search_fn):
                return list(search_fn(query))
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Knowledge search failed: %s", exc)
        return []

    def recall_memory(self, query: str | None = None) -> list[Any]:
        """Recall from the memory engine (if available)."""
        if self.memory is None:
            return []
        try:
            recall_fn = getattr(self.memory, "recall", None)
            if callable(recall_fn):
                return list(recall_fn())
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Memory recall failed: %s", exc)
        return []

    def remember(self, content: Any, **metadata: Any) -> None:
        """Write to the memory engine (if available)."""
        if self.memory is None:
            return
        try:
            remember_fn = getattr(self.memory, "remember", None)
            if callable(remember_fn):
                remember_fn(content=content, **metadata)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Memory write failed: %s", exc)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_goal(self, goal: str) -> Any:
        """Execute ``goal`` via the Execution Engine (if available)."""
        if self.execution is None:
            return {"error": "execution engine not available"}
        try:
            run_fn = getattr(self.execution, "run", None)
            if callable(run_fn):
                return run_fn(goal)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"error": "execution engine has no run method"}

    def run_runtime(self, request: str) -> Any:
        """Run ``request`` via the Runtime (if available)."""
        if self.runtime is None:
            return {"error": "runtime not available"}
        try:
            handle_fn = getattr(self.runtime, "handle", None)
            if callable(handle_fn):
                return handle_fn(request)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"error": "runtime has no handle method"}

    def generate(self, prompt: str, **kwargs: Any) -> Any:
        """Generate text via the Provider Layer (if available)."""
        if self.providers is None:
            return {"error": "providers not available"}
        try:
            gen_fn = getattr(self.providers, "generate", None)
            if callable(gen_fn):
                return gen_fn(prompt, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"error": "providers have no generate method"}

    def execute_mcp(
        self,
        capability: str,
        params: dict[str, Any] | None = None,
        connector: str | None = None,
    ) -> Any:
        """Execute an MCP capability (if available)."""
        if self.mcp is None:
            return {"error": "MCP not available"}
        try:
            exec_fn = getattr(self.mcp, "execute_capability", None)
            if callable(exec_fn):
                return exec_fn(capability, params or {}, connector=connector)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}
        return {"error": "MCP has no execute_capability method"}

    # ------------------------------------------------------------------
    # Candidate discovery (for DecisionEngine)
    # ------------------------------------------------------------------

    def provider_candidates(self) -> list[DecisionCandidate]:
        """Return provider candidates from the Provider Layer."""
        if self.providers is None:
            return []
        candidates: list[DecisionCandidate] = []
        try:
            registry = getattr(self.providers, "registry", None)
            if registry is not None:
                all_fn = getattr(registry, "all", None)
                if callable(all_fn):
                    for provider in all_fn():
                        name = getattr(provider, "name", str(provider))
                        info = getattr(provider, "info", None)
                        caps = ()
                        cost = 0.0
                        if info is not None:
                            caps = tuple(getattr(info, "capabilities", ()) or ())
                            cost = getattr(info, "cost_per_1k", 0.0) or 0.0
                        candidates.append(
                            DecisionCandidate(
                                name=name,
                                kind="provider",
                                capabilities=caps,
                                cost=cost,
                                availability=(
                                    1.0 if getattr(provider, "available", True) else 0.0
                                ),
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Provider discovery failed: %s", exc)
        return candidates

    def mcp_candidates(self) -> list[DecisionCandidate]:
        """Return MCP connector candidates."""
        if self.mcp is None:
            return []
        candidates: list[DecisionCandidate] = []
        try:
            registry = getattr(self.mcp, "registry", None)
            if registry is not None:
                all_fn = getattr(registry, "all", None)
                if callable(all_fn):
                    for connector in all_fn():
                        name = getattr(connector, "name", str(connector))
                        caps = (
                            tuple(c.name for c in connector.capabilities())
                            if hasattr(connector, "capabilities")
                            else ()
                        )
                        candidates.append(
                            DecisionCandidate(
                                name=name,
                                kind="mcp",
                                capabilities=caps,
                                availability=(
                                    1.0
                                    if getattr(connector, "is_connected", False)
                                    else 0.0
                                ),
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("MCP discovery failed: %s", exc)
        return candidates

    def all_candidates(self) -> list[DecisionCandidate]:
        """Return every candidate from every available subsystem."""
        return [*self.provider_candidates(), *self.mcp_candidates()]

    def __repr__(self) -> str:
        parts = []
        if self.has_execution():
            parts.append("execution")
        if self.has_workflows():
            parts.append("workflows")
        if self.has_runtime():
            parts.append("runtime")
        if self.has_providers():
            parts.append("providers")
        if self.has_mcp():
            parts.append("mcp")
        if self.has_memory():
            parts.append("memory")
        if self.has_knowledge():
            parts.append("knowledge")
        return f"<Coordinator subsystems=[{', '.join(parts)}]>"


__all__ = ["Coordinator"]
