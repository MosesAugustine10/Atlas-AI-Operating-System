"""The Atlas Kernel — orchestrator of every request.

The :class:`Kernel` is the top-level runtime. For each incoming request it:

1. Builds a :class:`~atlas.core.context.Context` bundling the request with
   configuration, memory, and knowledge handles.
2. Opens a :class:`~atlas.core.session.Session` to track the execution.
3. Asks the :class:`~atlas.core.planner.Planner` to decompose the goal into
   tasks.
4. Asks the :class:`~atlas.core.router.Router` to assign each task to an
   agent.
5. Drives execution, collecting results into the session.

Subsystems are injected, so the Kernel is straightforward to test in
isolation.
"""

from __future__ import annotations

from typing import Any

from atlas.core.context import Context
from atlas.core.logger import get_logger
from atlas.core.planner import Planner, Task
from atlas.core.router import Router
from atlas.core.session import Session


class Kernel:
    """Orchestrates every request through the Atlas pipeline.

    Parameters:
        planner: The planner used to decompose goals. Defaults to a new
            :class:`~atlas.core.planner.Planner`.
        router: The router used to assign agents. Defaults to a new
            :class:`~atlas.core.router.Router`.
        config: System configuration mapping.
        memory: Handle to the persistent memory store (placeholder).
        knowledge: Handle to the knowledge / retrieval store (placeholder).
    """

    def __init__(
        self,
        planner: Planner | None = None,
        router: Router | None = None,
        config: dict[str, Any] | None = None,
        memory: Any = None,
        knowledge: Any = None,
    ) -> None:
        self.planner = planner or Planner()
        self.router = router or Router()
        self.config = config or {}
        self.memory = memory
        self.knowledge = knowledge
        self.logger = get_logger("kernel")

    def build_context(self, request: str, user: str | None = None) -> Context:
        """Assemble a :class:`Context` for a new request."""
        return Context(
            request=request,
            config=self.config,
            memory=self.memory,
            knowledge=self.knowledge,
            user=user,
        )

    def open_session(self, request: str, user: str | None = None) -> Session:
        """Create a :class:`Session` for a new request."""
        context = self.build_context(request, user=user)
        return Session(context=context)

    def handle(self, request: str, user: str | None = None) -> Session:
        """Process a request end-to-end through the pipeline.

        .. note::
            Placeholder orchestration. It plans tasks, routes each to an
            agent, and records a stub result, then marks the session
            complete. Real agent invocation (via the Tool Manager and MCP
            servers) is wired in later.

        Returns:
            The completed :class:`Session`, holding tasks and results.
        """
        session = self.open_session(request, user=user)
        session.begin()
        self.logger.info("Kernel handling request: %s", request)

        tasks: list[Task] = self.planner.plan(request, session.context)
        session.set_tasks(tasks)

        for task in tasks:
            agent = self.router.select(task, session.context)
            self.logger.info("Routed task %s -> %s", task.id, agent.name)
            # Placeholder: real agent execution would happen here, invoking
            # the Tool Manager and downstream MCP servers as needed.
            session.record_result({"task": task.id, "agent": agent.name})

        session.complete()
        return session
