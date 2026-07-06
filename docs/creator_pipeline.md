# Atlas Creator AI Pipeline

The `atlas/creator_pipeline/` package is the **autonomous content creation pipeline** that transforms ONE user goal into a complete professional media project.

## Overview

```
"Create a YouTube documentary about SpaceX."
  ↓
Research → Fact Check → Script → Storyboard → Shot Plan →
Prompt Gen → Image Gen → Video Gen → Voice Synth → Music Select →
Subtitle Gen → Timeline Assembly → Render → Quality Review →
Thumbnail Gen → Metadata Gen → SEO Optimize → Package
```

The pipeline sits ABOVE the Collaboration Engine:

```mermaid
flowchart TB
    subgraph User["User"]
        Goal["Creative goal"]
    end

    subgraph Pipeline["atlas/creator_pipeline (this package)"]
        Planner["PipelinePlanner"]
        Orchestrator["CreatorPipelineOrchestrator"]
        Stages["18 Stage Coordinators"]
    end

    subgraph Below["Existing Atlas systems (injected)"]
        Collab["Collaboration"]
        Workforce["Workforce"]
        Brain["Brain"]
        Execution["Execution Engine"]
        Runtime["Runtime"]
        Providers["Providers / MCP"]
        Memory["Memory / Knowledge"]
        Artifacts["Artifact Manager"]
    end

    Goal --> Orchestrator
    Orchestrator --> Planner
    Orchestrator --> Stages
    Stages -.->|callbacks| Below
```

## Architecture

The package is split into four layers:

* **Models** (`models.py`) — pure-Python frozen dataclasses and enums. No Atlas subsystem imports.
* **Planner** (`planner.py`) — converts a goal into a dependency-ordered stage graph.
* **Stage Coordinators** (`research.py`, `script.py`, `storyboard.py`, `assets.py`, `voice.py`, `timeline.py`, `render.py`, `review.py`, `publisher.py`) — each coordinator runs one stage via an injected callback.
* **Orchestrator** (`orchestrator.py`) — the top-level facade with `create_project`, `run`, `resume`, `cancel`, `retry`, `export`.

### Dependency injection everywhere

The pipeline NEVER imports Brain, Workforce, Collaboration, or any Atlas subsystem directly. It receives callbacks (`research_fn`, `script_fn`, `image_gen_fn`, etc.) via dependency injection:

```python
from atlas.creator_pipeline import CreatorPipelineOrchestrator

orch = CreatorPipelineOrchestrator(
    research_fn=my_brain.think,       # wire to Brain
    script_fn=my_script_writer,       # wire to Creator Studio
    image_gen_fn=my_image_generator,  # wire to MCP / Provider
    render_fn=my_render_dispatcher,   # wire to HyperFrames/Remotion
)
```

## Execution Flow

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant P as Planner
    participant S as Stage Coordinator
    participant CB as Injected Callback

    U->>O: create_project("Create documentary")
    O->>P: plan(goal)
    P-->>O: PipelineProject (18 stages)
    O-->>U: project (RUNNING)

    U->>O: run(project_id)
    O->>O: _run_streaming(project_id)

    loop For each stage (in dependency order)
        O->>S: execute(goal, stage)
        S->>CB: research_fn / script_fn / ...
        CB-->>S: result
        S-->>O: updated stage + artifacts
    end

    O-->>U: PipelineResult
```

## Stage Graph

The default 18-stage pipeline with dependencies:

```mermaid
graph LR
    R[Research] --> FC[Fact Check]
    FC --> SC[Script]
    SC --> SB[Storyboard]
    SB --> SP[Shot Plan]
    SP --> PG[Prompt Gen]
    PG --> IG[Image Gen]
    PG --> VG[Video Gen]
    SC --> VS[Voice Synth]
    SC --> MS[Music Select]
    VS --> SG[Subtitle Gen]
    IG --> TA[Timeline Assembly]
    VG --> TA
    VS --> TA
    MS --> TA
    SG --> TA
    TA --> RN[Render]
    RN --> QR[Quality Review]
    QR --> TG[Thumbnail Gen]
    QR --> MG[Metadata Gen]
    MG --> SEO[SEO Optimize]
    SEO --> PKG[Package]
```

## Artifact Flow

Each stage produces a `PipelineArtifact` containing an `AssetReference`. Artifacts accumulate across stages and are tracked by the orchestrator:

```mermaid
flowchart LR
    R[Research] -->|document| A1[research_notes.md]
    SC[Script] -->|document| A2[script.md]
    SB[Storyboard] -->|document| A3[storyboard.json]
    IG[Image Gen] -->|image| A4[images/]
    VS[Voice Synth] -->|audio| A5[voice.wav]
    TA[Timeline] -->|timeline| A6[timeline.json]
    RN[Render] -->|render| A7[render.mp4]
    TG[Thumbnail] -->|thumbnail| A8[thumbnail.png]
    PKG[Package] -->|package| A9[package.zip]

    A1 --> Artifacts[Artifact Registry]
    A2 --> Artifacts
    A3 --> Artifacts
    A4 --> Artifacts
    A5 --> Artifacts
    A6 --> Artifacts
    A7 --> Artifacts
    A8 --> Artifacts
    A9 --> Artifacts
```

## Recovery Flow

```mermaid
flowchart TB
    Start([Stage Running]) --> Check{Success?}
    Check -->|Yes| Complete([Stage Completed])
    Check -->|No| Fail([Stage Failed])
    Fail --> ProjectFail([Project Failed])
    ProjectFail --> Retry{User retries?}
    Retry -->|Yes| ResetStage([Stage reset to PENDING])
    ResetStage --> Resume([Project resumed])
    Resume --> Start
    Retry -->|No| End([Project stays failed])
```

## Features

* **Parallel stages** — stages with no dependencies on each other run in parallel groups.
* **Dependency graph** — the planner resolves stage dependencies and topologically sorts them.
* **Resume** — `resume_project()` restarts a paused or failed project from where it left off.
* **Checkpointing** — `checkpoint()` captures a `PipelineState` snapshot; `restore()` reloads it.
* **Artifact tracking** — every stage's output is recorded as a `PipelineArtifact`.
* **Streaming events** — `run(project_id, stream=True)` yields events as a generator.
* **Failure recovery** — failed stages can be retried via `retry_stage()`.
* **Quality scoring** — stages record quality scores; the report aggregates them.
* **Cost estimation** — each stage tracks `cost_usd`; the result totals them.
* **Time estimation** — each stage tracks `duration_seconds`; the result totals them.

## Usage

```python
from atlas.creator_pipeline import CreatorPipelineOrchestrator

# Create the orchestrator (all callbacks optional — defaults are deterministic)
orch = CreatorPipelineOrchestrator()

# Create a project
project = orch.create_project("Create a YouTube documentary about SpaceX")
print(f"Project: {project.id} with {len(project.stages)} stages")

# Run the pipeline
result = orch.run(project.id)
print(f"Completed: {result.stages_completed}/{len(project.stages)} stages")
print(f"Artifacts: {result.total_assets}")

# Generate a report
report = orch.generate_report(project.id)
print(f"Quality: {report.result.quality_score:.2f}")

# Export
orch.export_project(project.id)
```

## Test coverage

The package ships **86 dedicated tests** in `tests/test_creator_pipeline.py`, covering:

* All 6 enums and 16+ frozen dataclasses.
* `PipelinePlanner` — planning, stage ordering, dependency resolution, parallel groups.
* All 9 stage coordinators (research, script, storyboard, assets, voice, timeline, render, review, publisher).
* `CreatorPipelineOrchestrator` — create, run, cancel, resume, retry, export, checkpoint, restore, compute_result, compute_metrics, generate_report.
* End-to-end integration (full YouTube documentary, streaming events, checkpointing, multiple projects, failure recovery, retry after failure).
* A no-subsystem-import test that walks the package source to verify no Atlas-subsystem imports.
