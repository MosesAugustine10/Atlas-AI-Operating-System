"""Workflow engine — the orchestrator of the Atlas Workflow Engine.

The :class:`WorkflowEngine` is the single entry point through which the
rest of Atlas interacts with workflows. It owns a :class:`WorkflowRegistry`
(definitions), a :class:`BaseExecutor` (step execution), a
:class:`BaseScheduler` (scheduled triggers), a :class:`WorkflowHistory`
(run snapshots), a :class:`WorkflowValidator` (definition validation), and
a :class:`TemplateRegistry` (reusable templates). Every dependency is
injectable, with sensible deterministic defaults, so the engine can be
constructed in one line and exercised end-to-end without external
resources.

Public API surface:

* **Definitions**: :meth:`register_workflow`, :meth:`get_workflow`,
  :meth:`list_workflows`.
* **Runs**: :meth:`create_run`, :meth:`get_run`, :meth:`list_runs`.
* **Execution control**: :meth:`start`, :meth:`pause`, :meth:`resume`,
  :meth:`retry`, :meth:`cancel`.
* **Scheduling**: :meth:`register_schedule`, :meth:`unregister_schedule`,
  :meth:`tick`.
* **Templates**: :meth:`register_template`, :meth:`instantiate_template`.

The engine never mutates a :class:`WorkflowRun` in place — every state
change produces a new immutable snapshot via :func:`dataclasses.replace`,
and every snapshot is recorded in :class:`WorkflowHistory`.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.workflows.base import BaseExecutor, BaseScheduler
from atlas.workflows.executor import PlaceholderExecutor, WaitSignal
from atlas.workflows.history import WorkflowHistory
from atlas.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowSchedule,
    WorkflowStep,
)
from atlas.workflows.registry import WorkflowRegistry
from atlas.workflows.scheduler import InMemoryScheduler
from atlas.workflows.state import (
    TERMINAL_STATES,
    WorkflowState,
)
from atlas.workflows.templates import TemplateRegistry
from atlas.workflows.validator import WorkflowValidator


class WorkflowEngineError(RuntimeError):
    """Raised when the engine cannot perform the requested operation."""


class WorkflowNotFound(KeyError):
    """Raised when a referenced workflow definition is not registered."""


class RunNotFound(KeyError):
    """Raised when a referenced workflow run is not recorded."""


class WorkflowEngine:
    """Orchestrates workflow definitions, runs, and schedules.

    Parameters:
        registry: Workflow definition registry. A new one is created if
            omitted.
        executor: Step executor. Defaults to :class:`PlaceholderExecutor`.
        scheduler: Schedule tracker. Defaults to :class:`InMemoryScheduler`.
        history: Run history store. A new one is created if omitted.
        validator: Definition validator. A new one is created if omitted.
        templates: Template registry. A new one is created if omitted.
    """

    def __init__(
        self,
        registry: WorkflowRegistry | None = None,
        executor: BaseExecutor | None = None,
        scheduler: BaseScheduler | None = None,
        history: WorkflowHistory | None = None,
        validator: WorkflowValidator | None = None,
        templates: TemplateRegistry | None = None,
    ) -> None:
        # NOTE: use explicit ``is None`` checks (not ``or``) because every
        # injected dependency defines ``__len__`` and would otherwise be
        # treated as falsy when empty.
        self.registry = registry if registry is not None else WorkflowRegistry()
        self.executor = executor if executor is not None else PlaceholderExecutor()
        self.scheduler = scheduler if scheduler is not None else InMemoryScheduler()
        self.history = history if history is not None else WorkflowHistory()
        self.validator = validator if validator is not None else WorkflowValidator()
        self.templates = templates if templates is not None else TemplateRegistry()
        self.logger = get_logger("workflow.engine")
        # Internal flags for cross-call coordination (e.g. request_pause).
        self._pause_requests: set[str] = set()

    # ------------------------------------------------------------------
    # Definitions
    # ------------------------------------------------------------------

    def register_workflow(
        self,
        definition: WorkflowDefinition,
        validate: bool = True,
    ) -> WorkflowDefinition:
        """Register a workflow definition.

        Args:
            definition: The definition to register.
            validate: If ``True`` (default), the definition is validated
                before registration. Invalid definitions raise
                :class:`atlas.workflows.validator.WorkflowValidationError`.

        Raises:
            WorkflowValidationError: If validation fails.
            ValueError: If a definition with the same id already exists.
        """
        if validate:
            self.validator.validate_or_raise(definition)
        self.registry.register(definition)
        self.logger.info(
            "Registered workflow %s (%s) with %d step(s)",
            definition.id,
            definition.name,
            len(definition.steps),
        )
        return definition

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition:
        """Return a registered workflow definition.

        Raises:
            WorkflowNotFound: If the workflow is not registered.
        """
        definition = self.registry.get(workflow_id)
        if definition is None:
            raise WorkflowNotFound(workflow_id)
        return definition

    def list_workflows(self) -> list[WorkflowDefinition]:
        """Return every registered workflow definition."""
        return self.registry.all()

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        workflow_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Create a new :class:`WorkflowRun` for ``workflow_id``.

        The run is recorded in history but not started. Call :meth:`start`
        to begin execution.

        Raises:
            WorkflowNotFound: If ``workflow_id`` is not registered.
        """
        definition = self.get_workflow(workflow_id)
        merged_inputs = {**definition.inputs, **(inputs or {})}
        run = WorkflowRun(
            definition_id=definition.id,
            name=definition.name,
            inputs=merged_inputs,
            metadata={"workflow_version": definition.version},
        )
        self.history.record(run)
        self.logger.info("Created run %s for workflow %s", run.id, definition.id)
        return run

    def get_run(self, run_id: str) -> WorkflowRun:
        """Return the latest snapshot of ``run_id``.

        Raises:
            RunNotFound: If the run is not recorded.
        """
        run = self.history.get(run_id)
        if run is None:
            raise RunNotFound(run_id)
        return run

    def list_runs(
        self,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowRun]:
        """Return recorded runs, optionally filtered by workflow id."""
        return self.history.list_runs(workflow_id=workflow_id, limit=limit)

    # ------------------------------------------------------------------
    # Execution control
    # ------------------------------------------------------------------

    def start(
        self,
        run_id: str,
        max_steps: int | None = None,
    ) -> WorkflowRun:
        """Start (or resume) execution of a workflow run.

        Transitions ``PENDING -> PLANNING -> RUNNING`` (or
        ``PAUSED/WAITING -> RUNNING`` for resumption) and then executes
        remaining steps until one of:

        * All remaining steps complete successfully → ``COMPLETED``.
        * A step fails (and is not optional) → ``FAILED``.
        * A step returns a :class:`WaitSignal` → ``WAITING``.
        * A pause is requested via :meth:`request_pause` → ``PAUSED``.
        * ``max_steps`` is reached → ``PAUSED``.

        Args:
            run_id: The run to start.
            max_steps: If given, execute at most this many steps before
                pausing. Useful for deterministic mid-execution pause tests.

        Raises:
            RunNotFound: If the run is not recorded.
            WorkflowEngineError: If the run is already terminal.
            InvalidStateTransitionError: If the run cannot legally start.
        """
        run = self.get_run(run_id)
        run = self._begin_running(run)
        self.history.record(run)

        steps_taken = 0
        while run.state is WorkflowState.RUNNING:
            if self._is_pause_requested(run_id):
                self._clear_pause_request(run_id)
                run = run.with_transition(
                    WorkflowState.PAUSED, reason="pause_requested"
                )
                self.history.record(run)
                return run

            if max_steps is not None and steps_taken >= max_steps:
                run = run.with_transition(
                    WorkflowState.PAUSED, reason="max_steps_reached"
                )
                self.history.record(run)
                return run

            next_step = self._next_step(run)
            if next_step is None:
                run = run.with_transition(
                    WorkflowState.COMPLETED, reason="all_steps_complete"
                )
                self.history.record(run)
                self.logger.info("Run %s completed", run.id)
                return run

            run = dataclasses.replace(run, current_step_id=next_step.id)
            self.history.record(run)

            context = self._build_context(run)
            result = self.executor.execute_step(next_step, context)
            run = run.with_step_result(result)
            self.history.record(run)

            steps_taken += 1

            if not result.success:
                if next_step.optional:
                    self.logger.info(
                        "Optional step %s failed; continuing", next_step.id
                    )
                    continue
                run = dataclasses.replace(
                    run,
                    error=result.error,
                )
                run = run.with_transition(
                    WorkflowState.FAILED,
                    reason=f"step_failed:{next_step.id}",
                )
                self.history.record(run)
                self.logger.warning(
                    "Run %s failed at step %s: %s",
                    run.id,
                    next_step.id,
                    result.error,
                )
                return run

            if isinstance(result.output, WaitSignal):
                run = run.with_transition(
                    WorkflowState.WAITING,
                    reason=f"wait_requested:{next_step.id}",
                )
                self.history.record(run)
                self.logger.info("Run %s waiting after step %s", run.id, next_step.id)
                return run

        return run

    def pause(self, run_id: str) -> WorkflowRun:
        """Pause a run.

        Behaviour depends on the current state:

        * ``PENDING`` / ``PLANNING`` / ``WAITING`` → transitions directly
          to ``PAUSED``.
        * ``RUNNING`` → sets a pause-request flag that :meth:`start` checks
          between steps. The run will be paused at the next step boundary.

        Raises:
            WorkflowEngineError: If the run is in a state that cannot be
                paused (e.g. terminal).
        """
        run = self.get_run(run_id)
        if run.state in TERMINAL_STATES:
            raise WorkflowEngineError(
                f"Cannot pause run in terminal state {run.state.value}"
            )
        if run.state is WorkflowState.RUNNING:
            self._pause_requests.add(run_id)
            self.logger.info("Pause requested for run %s", run_id)
            return run
        run = run.with_transition(WorkflowState.PAUSED, reason="pause_called")
        self.history.record(run)
        return run

    def request_pause(self, run_id: str) -> None:
        """Mark ``run_id`` for pause at the next step boundary.

        This is the async-style pause API: it sets an intent flag that
        :meth:`start` checks between steps. Useful for pausing from outside
        the engine in cooperative scenarios.
        """
        self._pause_requests.add(run_id)

    def resume(self, run_id: str) -> WorkflowRun:
        """Resume a paused or waiting run.

        Equivalent to calling :meth:`start` on a ``PAUSED`` or ``WAITING``
        run. Provided for API symmetry with :meth:`pause`.
        """
        run = self.get_run(run_id)
        if run.state not in (WorkflowState.PAUSED, WorkflowState.WAITING):
            raise WorkflowEngineError(f"Cannot resume run in state {run.state.value}")
        return self.start(run_id)

    def retry(self, run_id: str, inputs: dict[str, Any] | None = None) -> WorkflowRun:
        """Create a fresh run that retries ``run_id``.

        The new run inherits the original's inputs (overridden by
        ``inputs`` if supplied) and references the original via
        :attr:`WorkflowRun.parent_run_id`. The new run is recorded but not
        started; call :meth:`start` to execute it.

        Args:
            run_id: The run to retry. Must be in the ``FAILED`` state.
            inputs: Optional overrides for the inherited inputs.

        Raises:
            WorkflowEngineError: If ``run_id`` is not in the ``FAILED``
                state.
        """
        original = self.get_run(run_id)
        if original.state is not WorkflowState.FAILED:
            raise WorkflowEngineError(
                "Cannot retry run in state "
                f"{original.state.value}; only FAILED runs can be retried."
            )
        merged_inputs = {**original.inputs, **(inputs or {})}
        new_run = WorkflowRun(
            definition_id=original.definition_id,
            name=original.name,
            inputs=merged_inputs,
            attempts=original.attempts + 1,
            parent_run_id=original.id,
            metadata=dict(original.metadata),
        )
        self.history.record(new_run)
        self.logger.info(
            "Created retry run %s for parent %s (attempt %d)",
            new_run.id,
            original.id,
            new_run.attempts,
        )
        return new_run

    def cancel(self, run_id: str, reason: str = "cancelled") -> WorkflowRun:
        """Cancel a run.

        Terminal runs cannot be cancelled.

        Raises:
            WorkflowEngineError: If the run is already terminal.
        """
        run = self.get_run(run_id)
        if run.state in TERMINAL_STATES:
            raise WorkflowEngineError(
                f"Cannot cancel run in terminal state {run.state.value}"
            )
        run = run.with_transition(WorkflowState.CANCELLED, reason=reason)
        self.history.record(run)
        self.logger.info("Run %s cancelled: %s", run.id, reason)
        return run

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def register_schedule(
        self,
        schedule: WorkflowSchedule,
    ) -> WorkflowSchedule:
        """Register a schedule with the scheduler.

        Raises:
            WorkflowNotFound: If the referenced workflow is not registered.
            ValueError: If a schedule with the same id already exists.
        """
        if not self.registry.contains(schedule.workflow_id):
            raise WorkflowNotFound(schedule.workflow_id)
        self.scheduler.register(schedule)
        self.logger.info(
            "Registered schedule %s for workflow %s",
            schedule.id,
            schedule.workflow_id,
        )
        return schedule

    def unregister_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by id. Return ``True`` if it existed."""
        return self.scheduler.unregister(schedule_id)

    def list_schedules(self) -> list[WorkflowSchedule]:
        """Return every registered schedule."""
        return self.scheduler.all()

    def tick(self, now: datetime | None = None) -> list[WorkflowRun]:
        """Fire every schedule that is due and return the started runs.

        For each due schedule, the engine:

        1. Creates a new run from the schedule's workflow definition.
        2. Starts the run synchronously.
        3. Marks the schedule as having fired (advancing ``next_run_at``).

        Args:
            now: Reference timestamp. Defaults to the current UTC time.
        """
        moment = now or datetime.now(UTC)
        started: list[WorkflowRun] = []
        for schedule in self.scheduler.due(moment):
            if not self.registry.contains(schedule.workflow_id):
                self.logger.warning(
                    "Schedule %s references unknown workflow %s; skipping",
                    schedule.id,
                    schedule.workflow_id,
                )
                continue
            run = self.create_run(schedule.workflow_id, inputs=dict(schedule.inputs))
            run = self.start(run.id)
            started.append(run)
            self.scheduler.mark_run(schedule.id, moment)
        return started

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def register_template(self, template: object) -> object:
        """Register a :class:`WorkflowTemplate` with the template registry."""
        return self.templates.register(template)  # type: ignore[arg-type]

    def instantiate_template(
        self, template_id: str, **params: Any
    ) -> WorkflowDefinition:
        """Instantiate a registered template by id and register the workflow.

        Returns the registered :class:`WorkflowDefinition`.
        """
        definition = self.templates.instantiate(template_id, **params)
        return self.register_workflow(definition)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _begin_running(self, run: WorkflowRun) -> WorkflowRun:
        """Move ``run`` into the ``RUNNING`` state from a legal source state."""
        if run.state in TERMINAL_STATES:
            raise WorkflowEngineError(
                f"Cannot start run in terminal state {run.state.value}"
            )
        if run.state is WorkflowState.RUNNING:
            raise WorkflowEngineError(
                "Run is already running; pause or wait for completion first."
            )
        if run.state is WorkflowState.PENDING:
            run = run.with_transition(WorkflowState.PLANNING, reason="start_called")
            run = run.with_transition(WorkflowState.RUNNING, reason="planning_complete")
            return run
        # PAUSED or WAITING
        run = run.with_transition(WorkflowState.RUNNING, reason="resume")
        return run

    def _next_step(self, run: WorkflowRun) -> WorkflowStep | None:
        """Return the next step to execute for ``run``.

        Steps are executed in declaration order, skipping any whose
        dependencies have not yet completed successfully.
        """
        definition = self.get_workflow(run.definition_id)
        completed = {
            step_id for step_id, result in run.step_results.items() if result.success
        }
        for step in definition.steps:
            if step.id in run.step_results:
                # Already attempted — skip (even if it failed).
                continue
            if all(dep in completed for dep in step.depends_on):
                return step
        return None

    def _build_context(self, run: WorkflowRun) -> dict[str, Any]:
        """Build the execution context for a step.

        The context starts with the run's inputs and is augmented with the
        outputs of every successfully completed step. The executor may
        write additional keys to the context for later steps to observe.
        """
        context: dict[str, Any] = dict(run.inputs)
        for step_id, result in run.step_results.items():
            if result.success:
                context[step_id] = result.output
        return context

    def _is_pause_requested(self, run_id: str) -> bool:
        return run_id in self._pause_requests

    def _clear_pause_request(self, run_id: str) -> None:
        self._pause_requests.discard(run_id)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<WorkflowEngine workflows={len(self.registry)} "
            f"runs={len(self.history)} schedules={len(self.scheduler)}>"
        )


__all__ = [
    "RunNotFound",
    "WorkflowEngine",
    "WorkflowEngineError",
    "WorkflowNotFound",
]
