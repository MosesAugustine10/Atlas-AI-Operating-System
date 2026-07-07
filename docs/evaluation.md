# Atlas Evaluation & Self-Improvement System

The `atlas/evaluation/` package is the **production-grade evaluation and self-improvement system** for Atlas. It sits ABOVE the Brain and Workforce, running repeatable benchmarks, scoring outputs across seven dimensions, detecting regressions between versions, and generating optimization suggestions.

## Overview

```mermaid
flowchart TB
    subgraph User["User / Operator"]
        Goal["Evaluate Atlas"]
    end

    subgraph Eval["atlas/evaluation (this package)"]
        Orchestrator["EvaluationOrchestrator"]
        Scenarios["ScenarioStore"]
        Benchmarks["BenchmarkSuite"]
        Runner["EvaluationRunner"]
        Scoring["ScoringEngine"]
        Regression["RegressionDetector"]
        Optimizer["Optimizer"]
        Dashboard["DashboardGenerator"]
    end

    subgraph Below["Existing Atlas systems (injected)"]
        Brain["Brain"]
        Workforce["Workforce"]
        Collaboration["Collaboration"]
        Pipeline["Creator Pipeline"]
        Providers["Providers / MCP"]
        Memory["Memory / Knowledge"]
    end

    Goal --> Orchestrator
    Orchestrator --> Scenarios
    Orchestrator --> Benchmarks
    Orchestrator --> Runner
    Runner --> Scoring
    Orchestrator --> Regression
    Orchestrator --> Optimizer
    Orchestrator --> Dashboard
    Runner -.->|run_fn callback| Below
```

## Architecture

The package is split into layers:

* **Models** (`models.py`) — frozen dataclasses and enums. No Atlas subsystem imports.
* **Scenarios** (`scenarios.py`) — `ScenarioStore` with 10 built-in scenarios.
* **Benchmarks** (`benchmark.py`) — `BenchmarkSuite` for named scenario collections.
* **Runner** (`runner.py`) — `EvaluationRunner` executing benchmarks via injected `run_fn`.
* **Scoring** (`scoring.py`) — `ScoringEngine` producing 7-dimensional scores.
* **Regression** (`regression.py`) — `RegressionDetector` comparing runs.
* **Optimizer** (`optimizer.py`) — `Optimizer` generating `ImprovementSuggestion` instances.
* **Dashboard** (`dashboard.py`) — `DashboardGenerator` for UI-ready reports.
* **Orchestrator** (`orchestrator.py`) — `EvaluationOrchestrator` top-level facade.

## Scoring Dimensions

```mermaid
graph LR
    Result[EvaluationResult] --> Exec[ExecutionScore]
    Result --> Reas[ReasoningScore]
    Result --> Qual[QualityScore]
    Result --> Cost[CostScore]
    Result --> Lat[LatencyScore]
    Result --> Mem[MemoryScore]
    Result --> Know[KnowledgeScore]

    Exec -->|20%| Overall[Overall Score]
    Reas -->|15%| Overall
    Qual -->|25%| Overall
    Cost -->|10%| Overall
    Lat -->|10%| Overall
    Mem -->|10%| Overall
    Know -->|10%| Overall
```

| Dimension | Weight | Metrics |
|-----------|--------|---------|
| Execution | 20% | success, completeness, error count, retry count |
| Reasoning | 15% | coherence, depth, accuracy, step count |
| Quality | 25% | relevance, clarity, completeness, correctness |
| Cost | 10% | tokens in/out, estimated cost, cost efficiency |
| Latency | 10% | duration, first-token time, throughput |
| Memory | 10% | entries stored/recalled, recall accuracy, integration |
| Knowledge | 10% | docs indexed/retrieved, retrieval relevance, citation accuracy |

## Built-in Scenarios

| Category | Scenario |
|----------|----------|
| Website Generation | Landing Page for SaaS |
| Research | Climate Impact of Renewables |
| Video Creation | Blockchain Explainer Animation |
| Coding | REST API for Todo App |
| Mining | Open-Pit Optimization |
| Automation | Data ETL Pipeline |
| Reasoning | Logic Puzzle |
| Collaboration | Multi-Agent Code Review |
| Knowledge | Fact Synthesis |
| Memory | Context Recall |

## Regression Detection

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant R as RegressionDetector
    participant C as Current Run
    participant B as Baseline Run

    O->>R: compare(current, baseline)
    R->>C: get results
    R->>B: get results
    R->>R: Compare per-scenario scores
    R->>R: Flag regressions (delta < -threshold)
    R->>R: Flag improvements (delta > +threshold)
    R-->>O: RegressionReport
```

## Improvement Flow

```mermaid
flowchart TB
    Run[EvaluationRun] --> Opt[Optimizer]
    Opt --> Analyse[Analyse each result]
    Analyse --> Check1{Execution failed?}
    Check1 -->|Yes| S1[Workflow suggestion]
    Analyse --> Check2{Low reasoning?}
    Check2 -->|Yes| S2[Prompt suggestion]
    Analyse --> Check3{Low quality?}
    Check3 -->|Yes| S3[Prompt suggestion]
    Analyse --> Check4{High cost?}
    Check4 -->|Yes| S4[Provider selection suggestion]
    Analyse --> Check5{High latency?}
    Check5 -->|Yes| S5[Routing suggestion]
    S1 --> Report[OptimizationReport]
    S2 --> Report
    S3 --> Report
    S4 --> Report
    S5 --> Report
```

## Usage

```python
from atlas.evaluation import EvaluationOrchestrator

orch = EvaluationOrchestrator()
orch.load_builtin_scenarios()
benchmark = orch.create_full_benchmark()

# Run a benchmark
run = orch.benchmark(benchmark, version="1.0.0")
print(f"Overall score: {run.overall_score:.2f}")

# Generate improvement suggestions
opt = orch.improve(run.id)
for s in opt.suggestions:
    print(f"  [{s.severity}] {s.title}: {s.recommendation}")

# Compare with a previous run
if len(orch.list_runs()) >= 2:
    report = orch.compare(current_run_id, baseline_run_id)
    if report.has_regression:
        print(f"REGRESSION DETECTED: {len(report.regressions)} regressions")

# Generate a dashboard
dash = orch.generate_dashboard(run.id)
```

## Test Coverage

106 dedicated tests in `tests/test_evaluation.py`.
