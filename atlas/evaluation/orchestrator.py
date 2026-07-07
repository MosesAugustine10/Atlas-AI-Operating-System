"""Evaluation orchestrator — the top-level facade.

The :class:`EvaluationOrchestrator` wires together every evaluation
component (scenarios, benchmarks, runner, scoring, regression,
optimizer, dashboard) and exposes the public API:

* :meth:`evaluate` — run a single scenario.
* :meth:`benchmark` — run a full benchmark suite.
* :meth:`compare` — compare two runs for regressions.
* :meth:`improve` — generate optimization suggestions.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.evaluation.benchmark import BenchmarkSuite
from atlas.evaluation.dashboard import DashboardGenerator
from atlas.evaluation.models import (
    Benchmark,
    EvaluationResult,
    EvaluationRun,
    OptimizationReport,
    RegressionReport,
    RunStatus,
    Scenario,
)
from atlas.evaluation.optimizer import Optimizer
from atlas.evaluation.regression import RegressionDetector
from atlas.evaluation.runner import EvaluationRunner
from atlas.evaluation.scenarios import ScenarioStore
from atlas.evaluation.scoring import ScoringEngine


class EvaluationOrchestrator:
    """Top-level orchestrator for evaluation and self-improvement.

    Parameters:
        run_fn: Optional callback for running scenarios (typically
            ``Brain.think`` or ``Pipeline.run``).
    """

    def __init__(
        self,
        run_fn: Callable[..., str] | None = None,
    ) -> None:
        self.scenarios = ScenarioStore()
        self.benchmarks = BenchmarkSuite()
        self.scoring = ScoringEngine()
        self.runner = EvaluationRunner(run_fn=run_fn, scoring=self.scoring)
        self.regression = RegressionDetector()
        self.optimizer = Optimizer()
        self.dashboard = DashboardGenerator()
        self._runs: dict[str, EvaluationRun] = {}
        self._regression_reports: dict[str, RegressionReport] = {}
        self._optimization_reports: dict[str, OptimizationReport] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def load_builtin_scenarios(self) -> list[Scenario]:
        """Load the built-in evaluation scenarios."""
        return self.scenarios.load_builtins()

    def create_benchmark(
        self,
        name: str,
        scenario_ids: tuple[str, ...] = (),
        description: str = "",
    ) -> Benchmark:
        """Create a benchmark suite."""
        return self.benchmarks.create(
            name=name,
            scenario_ids=scenario_ids,
            description=description,
        )

    def create_full_benchmark(self, name: str = "Full Suite") -> Benchmark:
        """Create a benchmark containing all registered scenarios."""
        scenario_ids = tuple(s.id for s in self.scenarios.list_scenarios())
        return self.benchmarks.create(
            name=name,
            scenario_ids=scenario_ids,
            description="All registered scenarios",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        scenario: Scenario,
        version: str = "0.0.0",
    ) -> EvaluationResult:
        """Evaluate a single scenario."""
        return self.runner.run_scenario(scenario)

    def benchmark(
        self,
        benchmark: Benchmark,
        version: str = "0.0.0",
    ) -> EvaluationRun:
        """Run a full benchmark suite."""
        scenarios = self.scenarios.list_scenarios()
        run = self.runner.run_benchmark(
            benchmark=benchmark,
            scenarios=scenarios,
            version=version,
        )
        self._runs[run.id] = run
        return run

    def compare(
        self,
        current_run_id: str,
        baseline_run_id: str,
    ) -> RegressionReport:
        """Compare two runs for regressions."""
        current = self._require_run(current_run_id)
        baseline = self._require_run(baseline_run_id)
        report = self.regression.compare(current, baseline)
        self._regression_reports[report.id] = report
        return report

    def improve(
        self,
        run_id: str,
    ) -> OptimizationReport:
        """Generate optimization suggestions for a run."""
        run = self._require_run(run_id)
        report = self.optimizer.analyse(run)
        self._optimization_reports[report.id] = report
        return report

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> EvaluationRun | None:
        """Return the run with ``run_id`` or ``None``."""
        return self._runs.get(run_id)

    def list_runs(self, status: str | None = None) -> list[EvaluationRun]:
        """List runs, optionally filtered by status."""
        runs = list(self._runs.values())
        if status is not None:
            runs = [r for r in runs if r.status == status]
        return runs

    def get_regression_report(self, report_id: str) -> RegressionReport | None:
        """Return the regression report with ``report_id`` or ``None``."""
        return self._regression_reports.get(report_id)

    def get_optimization_report(self, report_id: str) -> OptimizationReport | None:
        """Return the optimization report with ``report_id`` or ``None``."""
        return self._optimization_reports.get(report_id)

    def generate_dashboard(
        self,
        run_id: str,
        regression_report_id: str | None = None,
        optimization_report_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a full dashboard for ``run_id``."""
        run = self._require_run(run_id)
        regression = (
            self._regression_reports.get(regression_report_id)
            if regression_report_id
            else None
        )
        optimization = (
            self._optimization_reports.get(optimization_report_id)
            if optimization_report_id
            else None
        )
        return self.dashboard.full_dashboard(
            run=run,
            regression=regression,
            optimization=optimization,
        )

    def status(self) -> dict[str, Any]:
        """Return a summary of the orchestrator's state."""
        return {
            "scenarios": self.scenarios.count(),
            "benchmarks": self.benchmarks.count(),
            "runs": len(self._runs),
            "completed_runs": len(self.list_runs(status=RunStatus.COMPLETED.value)),
            "regression_reports": len(self._regression_reports),
            "optimization_reports": len(self._optimization_reports),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_run(self, run_id: str) -> EvaluationRun:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"run {run_id} not found")
        return run


__all__ = ["EvaluationOrchestrator"]
