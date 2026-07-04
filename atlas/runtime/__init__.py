"""The Atlas Runtime Engine.

The runtime is the execution heart of the Atlas AI Operating System. It
accepts user requests, builds an execution context, opens a session,
dispatches workflows and agents, executes steps, selects providers,
invokes tools, emits lifecycle events, updates the memory and knowledge
engines, triggers reflection, and returns the final response.

The runtime is:

* **Provider-agnostic** — any concrete provider can be injected.
* **Tool-agnostic** — any concrete tool manager can be injected.
* **Agent-agnostic** — any concrete agent can be injected.
* **Workflow-agnostic** — any concrete workflow engine can be injected.
* **No external APIs** — every default is deterministic and in-process.
* **Zero circular imports** — modules form a strict acyclic dependency
  graph (see below).

Dependency graph (acyclic):

* ``lifecycle`` — leaf (enum + transition table).
* ``events`` — leaf (event types + EventBus).
* ``hooks`` — depends on ``events``.
* ``telemetry`` — depends on ``events``.
* ``queue`` — leaf.
* ``recovery`` — depends on ``events``, ``lifecycle``.
* ``monitor`` — depends on ``telemetry``, ``queue``.
* ``executor`` — depends on ``events``, ``telemetry``.
* ``pipeline`` — depends on ``executor``, ``events``, ``hooks``,
  ``lifecycle``.
* ``dispatcher`` — depends on ``pipeline``, ``events``, ``queue``.
* ``scheduler`` — depends on ``queue``.
* ``runtime`` — depends on all of the above.
"""

from __future__ import annotations

from atlas.runtime.dispatcher import Dispatcher, PipelineFactory
from atlas.runtime.events import (
    ContextCreated,
    DispatchCompleted,
    DispatchStarted,
    EventBus,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionPaused,
    ExecutionResumed,
    ExecutionStarted,
    KnowledgeUpdated,
    MemoryUpdated,
    PlanningCompleted,
    PlanningStarted,
    ProviderSelected,
    ReflectionTriggered,
    RequestReceived,
    ReviewCompleted,
    ReviewStarted,
    RuntimeEvent,
    SessionOpened,
    StepCompleted,
    StepFailed,
    StepStarted,
    ToolInvoked,
)
from atlas.runtime.executor import (
    Action,
    BaseExecutor,
    ExecutionOutcome,
    ExecutionPlan,
    ExecutionResult,
    ExecutionStep,
    PlaceholderExecutor,
)
from atlas.runtime.hooks import (
    AFTER_COMPLETE,
    AFTER_DISPATCH,
    AFTER_EXECUTE,
    AFTER_PLANNING,
    AFTER_REVIEW,
    ALL_PHASES,
    BEFORE_COMPLETE,
    BEFORE_DISPATCH,
    BEFORE_EXECUTE,
    BEFORE_PLANNING,
    BEFORE_REVIEW,
    ON_CANCEL,
    ON_FAILURE,
    Hook,
    HookAbort,
    HookManager,
    HookRegistration,
)
from atlas.runtime.lifecycle import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    InvalidRuntimeTransitionError,
    RuntimeState,
    all_states,
    assert_transition,
    can_transition,
    is_active,
    is_terminal,
    legal_targets,
)
from atlas.runtime.monitor import HealthReport, SystemMonitor
from atlas.runtime.pipeline import (
    CompleteStage,
    DispatchStage,
    ExecutionStage,
    Pipeline,
    PipelineContext,
    PlanningStage,
    ReviewStage,
    Stage,
    default_pipeline,
)
from atlas.runtime.queue import (
    ExecutionQueue,
    ExecutionRequest,
    QueueFullError,
)
from atlas.runtime.recovery import (
    Compensator,
    RecoveryDecision,
    RecoveryManager,
    RecoveryPolicy,
)
from atlas.runtime.runtime import Runtime, RuntimeError_
from atlas.runtime.scheduler import RuntimeScheduler, ScheduledTask, ScheduleKind
from atlas.runtime.telemetry import (
    BaseTelemetryCollector,
    ExecutionMetrics,
    TelemetryCollector,
)

__all__ = [
    "AFTER_COMPLETE",
    "AFTER_DISPATCH",
    "AFTER_EXECUTE",
    "AFTER_PLANNING",
    "AFTER_REVIEW",
    "ACTIVE_STATES",
    "ALL_PHASES",
    "Action",
    "BaseExecutor",
    "BaseTelemetryCollector",
    "BEFORE_COMPLETE",
    "BEFORE_DISPATCH",
    "BEFORE_EXECUTE",
    "BEFORE_PLANNING",
    "BEFORE_REVIEW",
    "CompleteStage",
    "Compensator",
    "ContextCreated",
    "DispatchCompleted",
    "DispatchStage",
    "DispatchStarted",
    "Dispatcher",
    "EventBus",
    "ExecutionCancelled",
    "ExecutionCompleted",
    "ExecutionFailed",
    "ExecutionMetrics",
    "ExecutionOutcome",
    "ExecutionPaused",
    "ExecutionPlan",
    "ExecutionQueue",
    "ExecutionRequest",
    "ExecutionResumed",
    "ExecutionResult",
    "ExecutionStage",
    "ExecutionStarted",
    "ExecutionStep",
    "HealthReport",
    "Hook",
    "HookAbort",
    "HookManager",
    "HookRegistration",
    "InvalidRuntimeTransitionError",
    "KnowledgeUpdated",
    "MemoryUpdated",
    "ON_CANCEL",
    "ON_FAILURE",
    "Pipeline",
    "PipelineContext",
    "PipelineFactory",
    "PlanningCompleted",
    "PlanningStage",
    "PlanningStarted",
    "PlaceholderExecutor",
    "ProviderSelected",
    "QueueFullError",
    "RecoveryDecision",
    "RecoveryManager",
    "RecoveryPolicy",
    "ReflectionTriggered",
    "RequestReceived",
    "ReviewCompleted",
    "ReviewStarted",
    "ReviewStage",
    "Runtime",
    "RuntimeError_",
    "RuntimeEvent",
    "RuntimeScheduler",
    "RuntimeState",
    "ScheduleKind",
    "ScheduledTask",
    "SessionOpened",
    "Stage",
    "StepCompleted",
    "StepFailed",
    "StepStarted",
    "SystemMonitor",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "TelemetryCollector",
    "ToolInvoked",
    "all_states",
    "assert_transition",
    "can_transition",
    "default_pipeline",
    "is_active",
    "is_terminal",
    "legal_targets",
]
