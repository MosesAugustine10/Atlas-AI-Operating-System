"""Atlas Evaluation & Self-Improvement System.

This package sits ABOVE the Brain and Workforce in the Atlas stack:

    User
      ↓
    Evaluation  ← this package
      ↓
    Brain / Workforce / Collaboration / Creator Pipeline
      ↓
    Execution / Runtime / Providers / MCP / Memory / Knowledge

The evaluation package NEVER imports concrete implementations. It
receives callbacks (e.g. ``run_fn``) via dependency injection and
calls them.

Modules:

* :mod:`atlas.evaluation.models` — frozen dataclasses and enums (leaf).
* :mod:`atlas.evaluation.scenarios` — :class:`ScenarioStore`.
* :mod:`atlas.evaluation.benchmark` — :class:`BenchmarkSuite`.
* :mod:`atlas.evaluation.runner` — :class:`EvaluationRunner`.
* :mod:`atlas.evaluation.scoring` — :class:`ScoringEngine`.
* :mod:`atlas.evaluation.regression` — :class:`RegressionDetector`.
* :mod:`atlas.evaluation.optimizer` — :class:`Optimizer`.
* :mod:`atlas.evaluation.dashboard` — :class:`DashboardGenerator`.
* :mod:`atlas.evaluation.orchestrator` — :class:`EvaluationOrchestrator`.

Usage::

    from atlas.evaluation import EvaluationOrchestrator

    orch = EvaluationOrchestrator()
    orch.load_builtin_scenarios()
    benchmark = orch.create_full_benchmark()
    run = orch.benchmark(benchmark, version="1.0.0")
    print(f"Overall score: {run.overall_score:.2f}")

    # Check for regressions
    if len(orch.list_runs()) >= 2:
        report = orch.compare(current_run_id, baseline_run_id)

    # Generate improvement suggestions
    opt = orch.improve(run.id)
    print(f"{len(opt.suggestions)} suggestions found")
"""

from __future__ import annotations

__version__ = "1.0.0"


# Re-export models (pure Python, always available)
# Re-export engines (pure Python, always available)
from atlas.evaluation.benchmark import BenchmarkSuite  # noqa: E402
from atlas.evaluation.dashboard import DashboardGenerator  # noqa: E402
from atlas.evaluation.models import (  # noqa: E402
    Benchmark,
    CostScore,
    EvaluationResult,
    EvaluationRun,
    ExecutionScore,
    GenerateFn,
    ImprovementSuggestion,
    KnowledgeScore,
    LatencyScore,
    MemoryScore,
    OptimizationReport,
    QualityScore,
    ReasoningScore,
    RegressionReport,
    RunFn,
    RunStatus,
    Scenario,
    ScenarioCategory,
    SeverityLevel,
    SuggestionKind,
)
from atlas.evaluation.optimizer import Optimizer  # noqa: E402
from atlas.evaluation.orchestrator import EvaluationOrchestrator  # noqa: E402
from atlas.evaluation.regression import (
    REGRESSION_THRESHOLD,
    RegressionDetector,
)  # noqa: E402
from atlas.evaluation.runner import EvaluationRunner  # noqa: E402
from atlas.evaluation.scenarios import ScenarioStore  # noqa: E402
from atlas.evaluation.scoring import ScoringEngine  # noqa: E402

__all__ = [
    "__version__",
    # Models
    "Benchmark",
    "CostScore",
    "EvaluationResult",
    "EvaluationRun",
    "ExecutionScore",
    "GenerateFn",
    "ImprovementSuggestion",
    "KnowledgeScore",
    "LatencyScore",
    "MemoryScore",
    "OptimizationReport",
    "QualityScore",
    "ReasoningScore",
    "RegressionReport",
    "RunFn",
    "RunStatus",
    "Scenario",
    "ScenarioCategory",
    "SeverityLevel",
    "SuggestionKind",
    # Engines
    "BenchmarkSuite",
    "DashboardGenerator",
    "Optimizer",
    "EvaluationOrchestrator",
    "REGRESSION_THRESHOLD",
    "RegressionDetector",
    "EvaluationRunner",
    "ScenarioStore",
    "ScoringEngine",
]
