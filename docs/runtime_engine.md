# Atlas Runtime Engine

The Atlas Runtime Engine is the execution heart of the Atlas AI Operating System. It accepts user requests, builds an execution context, opens a session, dispatches workflows and agents, executes steps, selects providers, invokes tools, emits lifecycle events, updates the Memory and Knowledge engines, triggers Reflection, and returns the final response.

The runtime is **provider-agnostic**, **tool-agnostic**, **agent-agnostic**, and **workflow-agnostic**. Every concrete concern (which LLM provider to call, which tool manager to dispatch to, which agent to invoke, which workflow engine to drive) is injected through an abstract base class. The default configuration uses deterministic in-memory placeholders so the runtime works out-of-the-box with zero external dependencies.

---

## Architecture

```mermaid
flowchart TB
    User([User]) --> Runtime

    subgraph Runtime["Runtime"]
        Handle["handle() / submit()"]
        Queue["ExecutionQueue"]
        Dispatcher["Dispatcher"]
        Pipeline["Pipeline"]
        Executor["PlaceholderExecutor"]
        Bus["EventBus"]
        Hooks["HookManager"]
        Telemetry["TelemetryCollector"]
        Monitor["SystemMonitor"]
        Recovery["RecoveryManager"]
        Scheduler["RuntimeScheduler"]
    end

    subgraph Stages["Pipeline Stages"]
        S1["PlanningStage"]
        S2["DispatchStage"]
        S3["ExecutionStage"]
        S4["ReviewStage"]
        S5["CompleteStage"]
    end

    subgraph Engines["Atlas Engines (injected)"]
        Memory[(Memory Engine)]
        Knowledge[(Knowledge Engine)]
        Providers[(Provider Layer)]
        Tools[(Tool System)]
        Agents[(Agents)]
        Workflows[(Workflow Engine)]
    end

    Handle --> Queue
    Queue --> Dispatcher
    Dispatcher --> Pipeline
    Pipeline --> S1
    S1 --> S2
    S2 --> S3
    S3 --> Executor
    S3 --> S4
    S4 --> S5
    S5 --> User

    Pipeline -.->|events| Bus
    Bus -.-> Telemetry
    Bus -.-> Recovery
    Telemetry --> Monitor
    Scheduler -.->|enqueue| Queue

    S2 -.->|select| Providers
    S2 -.->|select| Agents
    S2 -.->|select| Workflows
    S3 -.->|invoke| Tools
    S3 -.->|update| Memory
    S3 -.->|update| Knowledge
    S4 -.->|trigger| Memory
```

## Runtime lifecycle

Every execution moves through an explicit state machine. Transitions are validated against a fixed transition table; illegal moves raise `InvalidRuntimeTransitionError`. Terminal states cannot be left except that a `FAILED` execution can be retried (which resets the state to `PENDING`).

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> PLANNING: handle()
    PENDING --> WAITING: schedule
    PENDING --> PAUSED: pause
    PENDING --> CANCELLED: cancel
    PLANNING --> DISPATCHING: plan_ready
    PLANNING --> WAITING: external_signal
    PLANNING --> FAILED: plan_error
    PLANNING --> CANCELLED: cancel
    DISPATCHING --> EXECUTING: dispatched
    DISPATCHING --> WAITING: external_signal
    DISPATCHING --> FAILED: dispatch_error
    DISPATCHING --> CANCELLED: cancel
    EXECUTING --> PAUSED: pause
    EXECUTING --> WAITING: wait_signal
    EXECUTING --> REVIEWING: steps_done
    EXECUTING --> COMPLETED: direct_complete
    EXECUTING --> FAILED: step_failed
    EXECUTING --> CANCELLED: cancel
    REVIEWING --> COMPLETED: review_ok
    REVIEWING --> FAILED: review_failed
    REVIEWING --> EXECUTING: rework
    REVIEWING --> CANCELLED: cancel
    WAITING --> PLANNING: resume
    WAITING --> DISPATCHING: resume
    WAITING --> EXECUTING: resume
    WAITING --> PAUSED: pause
    WAITING --> CANCELLED: cancel
    PAUSED --> PLANNING: resume
    PAUSED --> EXECUTING: resume
    PAUSED --> FAILED: abort
    PAUSED --> CANCELLED: cancel
    FAILED --> PENDING: retry (reset)
    FAILED --> CANCELLED: abort
    COMPLETED --> [*]
    CANCELLED --> [*]
```

| State | Description | Terminal? |
|-------|-------------|-----------|
| `PENDING` | Execution created but not started. | No |
| `PLANNING` | Planner is decomposing the goal. | No |
| `DISPATCHING` | Dispatcher is selecting agents / providers / tools. | No |
| `EXECUTING` | Executor is running steps. | No |
| `REVIEWING` | Post-execution review / reflection is running. | No |
| `WAITING` | Execution blocked on an external signal or schedule. | No |
| `PAUSED` | Execution suspended; may be resumed. | No |
| `COMPLETED` | Execution finished successfully. | Yes |
| `FAILED` | Execution aborted with an error. Retriable. | Yes |
| `CANCELLED` | Operator cancelled the execution. | Yes |

## Execution pipeline

The pipeline is composed of five default stages, each of which is a small, replaceable callable:

```mermaid
flowchart LR
    Request[/"User request"/] --> Planning
    subgraph Planning["PlanningStage"]
        P1["Decompose goal"]
        P2["Produce ExecutionPlan"]
    end
    Planning --> Dispatch
    subgraph Dispatch["DispatchStage"]
        D1["Select agents"]
        D2["Select providers"]
        D3["Select tools"]
    end
    Dispatch --> Execution
    subgraph Execution["ExecutionStage"]
        E1["Run plan via Executor"]
        E2["Collect results"]
    end
    Execution --> Review
    subgraph Review["ReviewStage"]
        R1["Trigger Reflection"]
        R2["Update Memory"]
    end
    Review --> Complete
    subgraph Complete["CompleteStage"]
        C1["Assemble response"]
    end
    Complete --> Response[/"Final response"/]
```

1. **PlanningStage** — Decomposes the user request into an `ExecutionPlan` (a list of `ExecutionStep` items). The default planner produces a single `noop` step carrying the request; inject a custom planner for real decomposition.
2. **DispatchStage** — Selects agents, providers, and tools. The default dispatcher is a no-op; inject a custom dispatcher to populate `context.artifacts` with selected resources.
3. **ExecutionStage** — Runs the `ExecutionPlan` via the injected `BaseExecutor`. Each step emits `StepStarted` / `StepCompleted` / `StepFailed` events.
4. **ReviewStage** — Runs post-execution review / reflection. The default reviewer is a no-op; inject a custom reviewer to trigger reflection and update memory.
5. **CompleteStage** — Assembles the final response from the execution outcome. The default assembler returns the `final_output` of the execution outcome.

Each stage receives the mutable `PipelineContext` and may read from or write to it. Stages run sequentially; a stage that sets `context.error` or raises an exception short-circuits the pipeline and publishes an `ExecutionFailed` event.

## Component responsibilities

| Component | Responsibility |
|-----------|----------------|
| `Runtime` | Top-level orchestrator. Public API: `handle`, `submit`, `drain`, `pause`, `resume`, `cancel`, `retry`, `register_schedule`, `tick`, `health`, `metrics`, `events`. |
| `ExecutionQueue` | Priority-ordered FIFO queue of `ExecutionRequest` items. Higher priority dequeues first; FIFO within priority. Optional capacity. |
| `Dispatcher` | Pulls requests off the queue and runs each through a fresh `Pipeline`. Tracks processed / failed counts. |
| `Pipeline` | Ordered sequence of `Stage` callables. Runs hooks around every stage; short-circuits on error or `HookAbort`. |
| `PlanningStage` | Decomposes the request into an `ExecutionPlan`. Emits `PlanningStarted` / `PlanningCompleted`. |
| `DispatchStage` | Selects agents / providers / tools. Emits `DispatchStarted` / `DispatchCompleted`. |
| `ExecutionStage` | Runs the plan via the `BaseExecutor`. Stores the `ExecutionOutcome` on the context. |
| `ReviewStage` | Runs post-execution review / reflection. Emits `ReviewStarted` / `ReviewCompleted`. |
| `CompleteStage` | Assembles the final response from the execution outcome. |
| `BaseExecutor` | Abstract contract: `execute_plan(plan, execution_id, context) -> ExecutionOutcome`. |
| `PlaceholderExecutor` | Deterministic default executor with `noop`, `echo`, `fail`, `identity`, `context_read` built-ins. Custom actions injectable. |
| `EventBus` | Synchronous in-process pub/sub with topic filtering. Listeners are exception-isolated. |
| `HookManager` | Registry and dispatcher for pre/post stage hooks. Supports short-circuit and `HookAbort`. |
| `TelemetryCollector` | Subscribes to the event bus and records per-execution metrics (durations, counts, providers, tools). |
| `SystemMonitor` | Pulls telemetry and queue state to produce `HealthReport` snapshots with `healthy` / `degraded` / `unhealthy` status. |
| `RecoveryManager` | Owns retry and compensation strategy. Exponential backoff with configurable max retries and retryable error filters. |
| `RuntimeScheduler` | Triggers executions on a cadence (one_time, interval, cron). Enqueues `ExecutionRequest` items on tick. |
| `RuntimeState` | Ten-state lifecycle enum with explicit transition table. |
| `PipelineContext` | Mutable state carried through every stage: request, plan, outcome, response, state, artifacts. |
| `ExecutionPlan` | Frozen dataclass: ordered list of `ExecutionStep` items plus inputs and metadata. |
| `ExecutionStep` | Frozen dataclass: `id`, `action`, `params`, `optional`. |
| `ExecutionResult` | Frozen dataclass: `step_id`, `success`, `output`, `error`, timing. |
| `ExecutionOutcome` | Frozen dataclass: `success`, `results`, `final_output`, `error`. |
| `ExecutionRequest` | Frozen dataclass: `request`, `user`, `priority`, `metadata`. |
| `ScheduledTask` | Frozen dataclass: `request`, `kind`, cadence params, `next_run_at`, `enabled`. |

## Event flow

Every significant runtime action emits an event on the `EventBus`. The bus dispatches synchronously to every matching listener in registration order. Listeners are exception-isolated: a raising listener is logged and skipped but does not stop the dispatch to subsequent listeners.

```mermaid
sequenceDiagram
    participant User
    participant Runtime
    participant Dispatcher
    participant Pipeline
    participant Executor
    participant Bus as EventBus
    participant Telemetry
    participant Recovery

    User->>Runtime: handle("hello")
    Runtime->>Bus: RequestReceived
    Runtime->>Dispatcher: dispatch_request
    Dispatcher->>Bus: SessionOpened
    Dispatcher->>Pipeline: run(context)
    Pipeline->>Bus: ExecutionStarted

    rect rgba(200, 220, 255, 0.3)
        Pipeline->>Bus: PlanningStarted
        Pipeline->>Bus: PlanningCompleted
    end

    rect rgba(200, 255, 220, 0.3)
        Pipeline->>Bus: DispatchStarted
        Pipeline->>Bus: DispatchCompleted
    end

    rect rgba(255, 220, 200, 0.3)
        Pipeline->>Executor: execute_plan
        loop each step
            Executor->>Bus: StepStarted
            Executor->>Bus: StepCompleted (or StepFailed)
        end
    end

    rect rgba(255, 240, 200, 0.3)
        Pipeline->>Bus: ReviewStarted
        Pipeline->>Bus: ReviewCompleted
    end

    Pipeline->>Bus: ExecutionCompleted
    Pipeline-->>Dispatcher: context (completed)
    Dispatcher-->>Runtime: context
    Runtime-->>User: response

    Bus-->>Telemetry: record(event)
    Bus-->>Recovery: record(event)
```

### Event types

| Event | Emitted by | When |
|-------|-----------|------|
| `RequestReceived` | Dispatcher | A new request is pulled from the queue. |
| `SessionOpened` | Dispatcher | A pipeline context has been created. |
| `PlanningStarted` | PlanningStage | Before the planner runs. |
| `PlanningCompleted` | PlanningStage | After the planner produces a plan. |
| `DispatchStarted` | DispatchStage | Before dispatch decisions. |
| `DispatchCompleted` | DispatchStage | After dispatch decisions. |
| `ExecutionStarted` | Executor / Pipeline | Before the first step runs. |
| `StepStarted` | Executor | Before each step. |
| `StepCompleted` | Executor | After a successful step. |
| `StepFailed` | Executor | After a failed step. |
| `ReviewStarted` | ReviewStage | Before the review phase. |
| `ReviewCompleted` | ReviewStage | After the review phase. |
| `ExecutionCompleted` | Pipeline | When the execution finishes successfully. |
| `ExecutionFailed` | Pipeline | When the execution fails terminally. |
| `ExecutionCancelled` | Runtime | When the execution is cancelled. |
| `ExecutionPaused` | Runtime | When the execution is paused. |
| `ExecutionResumed` | Runtime | When the execution is resumed. |
| `MemoryUpdated` | Review / Custom | After the memory engine is updated. |
| `KnowledgeUpdated` | Review / Custom | After the knowledge engine is updated. |
| `ReflectionTriggered` | Review / Custom | When a reflection cycle is requested. |
| `ProviderSelected` | Dispatch / Custom | After a provider has been selected. |
| `ToolInvoked` | Execution / Custom | After a tool has been invoked. |

## Recovery flow

When an execution fails, the `RecoveryManager` decides what to do next. The decision is based on the failure, the number of attempts so far, and the configured `RecoveryPolicy`.

```mermaid
flowchart TB
    Start([Execution fails]) --> CheckRetryable{Error retryable?}
    CheckRetryable -- No --> Abort([Abort])
    CheckRetryable -- Yes --> CheckAttempts{Attempts < max_retries?}
    CheckAttempts -- No --> CheckCompensator{Compensator set?}
    CheckCompensator -- No --> Abort
    CheckCompensator -- Yes --> Compensate{Compensator returns payload?}
    Compensate -- No --> Abort
    Compensate -- Yes --> Compensated([Compensate])
    CheckAttempts -- Yes --> Backoff[Compute backoff delay]
    Backoff --> ScheduleRetry[Schedule retry at wait_until]
    ScheduleRetry --> Retry([Retry])
```

### Recovery policy

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | `3` | Maximum automatic retries. `0` disables retry. |
| `base_delay_seconds` | `1.0` | Initial backoff delay. Doubled on each retry. |
| `max_delay_seconds` | `30.0` | Cap on the backoff delay. |
| `retryable_errors` | `()` | If non-empty, only errors whose message contains one of these substrings are retryable. |

### Compensators

A compensator is a callable that receives the `ExecutionFailed` event and returns an optional payload dict. If the compensator returns a non-`None` payload, the recovery manager returns a `"compensate"` decision carrying the payload; otherwise it returns `"abort"`. Compensators are typically used to fall back to a different provider, return a cached response, or invoke a degraded-mode handler.

## Dependency graph (acyclic)

The runtime package has zero circular imports. Modules form a strict acyclic dependency graph:

```mermaid
flowchart TB
    lifecycle["lifecycle.py<br/>(leaf)"]
    events["events.py<br/>(leaf)"]
    hooks["hooks.py"]
    telemetry["telemetry.py"]
    queue["queue.py<br/>(leaf)"]
    recovery["recovery.py"]
    monitor["monitor.py"]
    executor["executor.py"]
    pipeline["pipeline.py"]
    dispatcher["dispatcher.py"]
    scheduler["scheduler.py"]
    runtime["runtime.py"]
    init["__init__.py"]

    hooks --> events
    telemetry --> events
    recovery --> events
    recovery --> lifecycle
    monitor --> telemetry
    monitor --> queue
    executor --> events
    executor --> telemetry
    pipeline --> executor
    pipeline --> events
    pipeline --> hooks
    pipeline --> lifecycle
    dispatcher --> pipeline
    dispatcher --> events
    dispatcher --> queue
    scheduler --> queue
    runtime --> dispatcher
    runtime --> events
    runtime --> executor
    runtime --> hooks
    runtime --> lifecycle
    runtime --> monitor
    runtime --> queue
    runtime --> recovery
    runtime --> scheduler
    runtime --> telemetry
    init --> runtime
    init --> dispatcher
    init --> events
    init --> executor
    init --> hooks
    init --> lifecycle
    init --> monitor
    init --> pipeline
    init --> queue
    init --> recovery
    init --> scheduler
    init --> telemetry
```

## Usage examples

### Minimal end-to-end execution

```python
from atlas.runtime import Runtime

rt = Runtime()
ctx = rt.handle("hello world")
assert ctx.state.value == "completed"
assert ctx.response is not None
```

### Submitting and draining

```python
rt = Runtime()
rt.submit("first")
rt.submit("second")
results = rt.drain()
assert len(results) == 2
```

### Priority queue

```python
from atlas.runtime import ExecutionQueue, ExecutionRequest

q = ExecutionQueue()
q.enqueue(ExecutionRequest(request="low", priority=1))
q.enqueue(ExecutionRequest(request="high", priority=10))
assert q.dequeue().request == "high"
```

### Subscribing to events

```python
from atlas.runtime import Runtime, StepCompleted

rt = Runtime()
steps: list = []
rt.bus.subscribe(StepCompleted, steps.append)
rt.handle("hello")
assert len(steps) >= 1
```

### Custom executor action

```python
from atlas.runtime import Runtime, PlaceholderExecutor

def greet(params, context):
    return f"Hello, {params['name']}!"

rt = Runtime(executor=PlaceholderExecutor(actions={"greet": greet}))
```

### Scheduled execution

```python
from datetime import datetime, timedelta, UTC
from atlas.runtime import Runtime, ScheduledTask, ScheduleKind

rt = Runtime()
run_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
rt.register_schedule(ScheduledTask(
    id="daily_ping",
    request="ping",
    kind=ScheduleKind.ONE_TIME,
    run_at=run_at,
))
results = rt.tick(now=run_at + timedelta(minutes=1))
assert len(results) == 1
```

### Health monitoring

```python
rt = Runtime()
rt.handle("hello")
health = rt.health()
assert health["status"] == "healthy"
assert health["completed_executions"] >= 1
```

### Recovery with compensation

```python
from atlas.runtime import RecoveryManager, RecoveryPolicy, ExecutionFailed

def fallback(failure: ExecutionFailed):
    return {"fallback": "default response"}

rm = RecoveryManager(
    policy=RecoveryPolicy(max_retries=1),
    compensator=fallback,
)
rm.record_start("e1")
rm.decide(ExecutionFailed(execution_id="e1", error="boom"))  # retry
rm.record_start("e1")
decision = rm.decide(ExecutionFailed(execution_id="e1", error="boom"))
assert decision.action == "compensate"
```

### Custom pipeline stage

```python
from atlas.runtime import Pipeline, PipelineContext, default_pipeline, PlaceholderExecutor

def audit_stage(ctx: PipelineContext) -> None:
    ctx.artifacts["audited"] = True

pipeline = default_pipeline(executor=PlaceholderExecutor())
pipeline.add_stage(audit_stage)
```

## Quality gates

The runtime is verified by:

- **150 pytest tests** in `tests/test_runtime.py` covering the lifecycle state machine, event bus, hooks, telemetry, queue, recovery, monitor, executor, pipeline, dispatcher, scheduler, and the top-level Runtime orchestrator.
- **463 total tests** pass (150 runtime + 130 workflow + 183 existing).
- **Black** clean on all 89 Python files.
- **Ruff** clean on all 89 Python files.
- **Zero circular imports** verified by independent module imports.
- **Frozen dataclasses** for every immutable model (`ExecutionStep`, `ExecutionPlan`, `ExecutionResult`, `ExecutionOutcome`, `ExecutionRequest`, `ScheduledTask`, `RecoveryDecision`, `RecoveryPolicy`, `HealthReport`, `ExecutionMetrics`, every event type).
- **Dependency injection** for every concrete concern (executor, scheduler, bus, hooks, telemetry, monitor, recovery, queue, pipeline factory).
- **Abstract base classes** for `BaseExecutor` and `BaseTelemetryCollector`.

## Future extensions

The runtime is designed to be extended without modification:

- **Concrete executors** — Subclass `BaseExecutor` to dispatch to the Tool System, Provider Layer, or Workflow Engine.
- **Concrete telemetry** — Subclass `BaseTelemetryCollector` to forward to Prometheus, OpenTelemetry, or Datadog.
- **Concrete schedulers** — Wrap `RuntimeScheduler` to delegate to APScheduler, Celery beat, or Kubernetes CronJobs.
- **Concrete queues** — Wrap `ExecutionQueue` to delegate to Redis, Celery, or RabbitMQ.
- **Custom pipeline stages** — Add stages via `pipeline.add_stage()` or inject a custom `pipeline_factory` into the runtime.
- **Custom hooks** — Register hooks at any of the 12 supported phases to short-circuit or augment execution.
- **Custom compensators** — Inject a compensator into `RecoveryManager` for fallback behaviour when retries are exhausted.
