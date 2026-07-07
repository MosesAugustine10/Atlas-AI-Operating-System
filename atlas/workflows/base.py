"""Abstract base classes for the Atlas Workflow Engine.

This module defines the contracts that concrete workflow components
implement. It depends only on :mod:`atlas.workflows.models` and
:mod:`atlas.core.logger` — both acyclic. By programming against these
abstractions, the engine remains provider-agnostic: any concrete executor
or scheduler can be injected without changing engine code.

Contracts:

* :class:`BaseExecutor` — runs a single :class:`WorkflowStep` and returns a
  :class:`StepResult`. The executor is the *only* component that knows how to
  actually perform work (call a function, hit an API, invoke a tool, etc.).
* :class:`BaseScheduler` — tracks :class:`WorkflowSchedule` objects and
  reports which are due to fire at a given moment.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.workflows.models import StepResult, WorkflowSchedule, WorkflowStep


class BaseExecutor(ABC):
    """Abstract contract for executing a single workflow step.

    Implementations are free to dispatch the step's :attr:`action` string
    to anything: a local function, a tool-manager call, an LLM provider,
    a remote service, etc. The engine never inspects *how* the work is
    done — it only consumes the returned :class:`StepResult`.

    Parameters:
        name: Identifier for this executor (used in logs).
    """

    def __init__(self, name: str = "executor") -> None:
        self.name = name
        self.logger = get_logger(f"workflow.executor.{name}")

    @abstractmethod
    def execute_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute ``step`` against the supplied ``context``.

        Args:
            step: The step to execute. The executor decides how to dispatch
                :attr:`step.action`.
            context: A mutable mapping of run inputs and prior step
                outputs. Implementations may read from it (and may write
                additional keys to be consumed by later steps).

        Returns:
            A :class:`StepResult` describing the outcome. Implementations
            should set :attr:`StepResult.completed_at`.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class BaseScheduler(ABC):
    """Abstract contract for tracking and triggering workflow schedules.

    A scheduler owns a set of :class:`WorkflowSchedule` objects and answers
    two questions:

    1. Which schedules are due to fire right now?
    2. What is the next time a given schedule should fire?

    Concrete schedulers may persist schedules to a database, query a cron
    daemon, integrate with an external job queue, or simply keep everything
    in memory (the default :class:`InMemoryScheduler`).

    Parameters:
        name: Identifier for this scheduler (used in logs).
    """

    def __init__(self, name: str = "scheduler") -> None:
        self.name = name
        self.logger = get_logger(f"workflow.scheduler.{name}")

    @abstractmethod
    def register(self, schedule: WorkflowSchedule) -> None:
        """Add ``schedule`` to the scheduler.

        Raises:
            ValueError: If a schedule with the same id is already registered.
        """

    @abstractmethod
    def unregister(self, schedule_id: str) -> bool:
        """Remove a schedule by id. Return ``True`` if it existed."""

    @abstractmethod
    def get(self, schedule_id: str) -> WorkflowSchedule | None:
        """Look up a schedule by id, returning ``None`` if not found."""

    @abstractmethod
    def all(self) -> list[WorkflowSchedule]:
        """Return every registered schedule, ordered by id."""

    @abstractmethod
    def due(self, now: datetime | None = None) -> list[WorkflowSchedule]:
        """Return all schedules that should fire at or before ``now``."""

    @abstractmethod
    def mark_run(self, schedule_id: str, ran_at: datetime) -> WorkflowSchedule | None:
        """Record that a schedule fired at ``ran_at`` and update its state.

        For ONE_TIME schedules this should disable the schedule. For INTERVAL
        schedules this should advance :attr:`next_run_at` by
        :attr:`interval_seconds`. For CRON schedules this should advance
        :attr:`next_run_at` to the next matching time.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


__all__ = ["BaseExecutor", "BaseScheduler"]
