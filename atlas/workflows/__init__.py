"""The Atlas Workflow Engine.

A provider-agnostic workflow orchestration framework providing:

* Immutable dataclasses for workflow models (:mod:`atlas.workflows.models`).
* An explicit lifecycle state machine (:mod:`atlas.workflows.state`).
* Abstract contracts for executors and schedulers (:mod:`atlas.workflows.base`).
* A deterministic placeholder executor (:mod:`atlas.workflows.executor`).
* A deterministic in-memory scheduler (:mod:`atlas.workflows.scheduler`).
* Definition validation with cycle detection (:mod:`atlas.workflows.validator`).
* A workflow definition registry (:mod:`atlas.workflows.registry`).
* Append-only run history tracking (:mod:`atlas.workflows.history`).
* Reusable workflow templates (:mod:`atlas.workflows.templates`).
* A top-level orchestrator that wires everything together
  (:mod:`atlas.workflows.engine`).

The dependency graph is acyclic:

* ``state`` — leaf (enum + transition table).
* ``models`` — leaf (frozen dataclasses).
* ``base`` — abstract contracts (depends on ``models``).
* ``validator`` — depends on ``models``.
* ``registry`` — depends on ``models``.
* ``history`` — depends on ``models``.
* ``templates`` — depends on ``models``.
* ``executor`` — depends on ``base``, ``models``.
* ``scheduler`` — depends on ``base``, ``models``.
* ``engine`` — depends on all of the above.
"""

from __future__ import annotations

from atlas.workflows.base import BaseExecutor, BaseScheduler
from atlas.workflows.engine import (
    RunNotFound,
    WorkflowEngine,
    WorkflowEngineError,
    WorkflowNotFound,
)
from atlas.workflows.executor import Action, PlaceholderExecutor, WaitSignal
from atlas.workflows.history import WorkflowHistory
from atlas.workflows.models import (
    ScheduleKind,
    StateTransition,
    StepResult,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowRun,
    WorkflowSchedule,
    WorkflowStep,
)
from atlas.workflows.registry import WorkflowRegistry
from atlas.workflows.scheduler import InMemoryScheduler
from atlas.workflows.state import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    InvalidStateTransitionError,
    WorkflowState,
    all_states,
    assert_transition,
    can_transition,
    is_active,
    is_terminal,
    legal_targets,
)
from atlas.workflows.templates import (
    Builder,
    TemplateRegistry,
    WorkflowTemplate,
    linear_template,
    retry_template,
    sequential_template,
)
from atlas.workflows.validator import (
    ValidationError,
    WorkflowValidationError,
    WorkflowValidator,
)

__all__ = [
    "ACTIVE_STATES",
    "Action",
    "BaseExecutor",
    "BaseScheduler",
    "Builder",
    "InMemoryScheduler",
    "InvalidStateTransitionError",
    "PlaceholderExecutor",
    "RunNotFound",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "TemplateRegistry",
    "ValidationError",
    "WaitSignal",
    "WorkflowDefinition",
    "WorkflowEngine",
    "WorkflowEngineError",
    "WorkflowHistory",
    "WorkflowNotFound",
    "WorkflowRegistry",
    "WorkflowResult",
    "WorkflowRun",
    "WorkflowSchedule",
    "WorkflowState",
    "WorkflowStep",
    "WorkflowTemplate",
    "WorkflowValidationError",
    "WorkflowValidator",
    "all_states",
    "assert_transition",
    "can_transition",
    "is_active",
    "is_terminal",
    "legal_targets",
    "linear_template",
    "retry_template",
    "sequential_template",
    "ScheduleKind",
    "StateTransition",
    "StepResult",
]
