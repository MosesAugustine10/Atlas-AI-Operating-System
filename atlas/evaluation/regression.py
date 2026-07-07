"""Regression detection — compare current run with baseline.

The :class:`RegressionDetector` compares two :class:`EvaluationRun`
instances and produces a :class:`RegressionReport` listing
regressions (score drops) and improvements (score gains).
"""

from __future__ import annotations

from atlas.evaluation.models import (
    EvaluationResult,
    EvaluationRun,
    RegressionReport,
    _new_id,
)

#: The threshold below which a score change is considered a regression.
REGRESSION_THRESHOLD: float = 0.05


class RegressionDetector:
    """Detects regressions between evaluation runs."""

    def __init__(self, threshold: float = REGRESSION_THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        """Return the regression threshold."""
        return self._threshold

    def compare(
        self,
        current: EvaluationRun,
        baseline: EvaluationRun,
    ) -> RegressionReport:
        """Compare ``current`` with ``baseline`` and return a report."""
        regressions: list[tuple[str, str, float]] = []
        improvements: list[tuple[str, str, float]] = []
        # Map baseline results by scenario id
        baseline_by_scenario: dict[str, EvaluationResult] = {
            r.scenario_id: r for r in baseline.results
        }
        for current_result in current.results:
            scenario_id = current_result.scenario_id
            baseline_result = baseline_by_scenario.get(scenario_id)
            if baseline_result is None:
                continue
            # Compare each dimension
            for metric, current_val, baseline_val in self._metrics(
                current_result, baseline_result
            ):
                delta = current_val - baseline_val
                if delta < -self._threshold:
                    regressions.append((scenario_id, metric, delta))
                elif delta > self._threshold:
                    improvements.append((scenario_id, metric, delta))
        overall_delta = current.overall_score - baseline.overall_score
        has_regression = len(regressions) > 0 or overall_delta < -self._threshold
        return RegressionReport(
            id=_new_id("regression"),
            current_run_id=current.id,
            baseline_run_id=baseline.id,
            regressions=tuple(regressions),
            improvements=tuple(improvements),
            overall_delta=overall_delta,
            has_regression=has_regression,
        )

    def _metrics(
        self,
        current: EvaluationResult,
        baseline: EvaluationResult,
    ) -> list[tuple[str, float, float]]:
        """Return (metric_name, current_value, baseline_value) tuples."""
        return [
            ("overall", current.overall_score, baseline.overall_score),
            ("execution", current.execution.score, baseline.execution.score),
            ("reasoning", current.reasoning.score, baseline.reasoning.score),
            ("quality", current.quality.score, baseline.quality.score),
            ("cost", current.cost.score, baseline.cost.score),
            ("latency", current.latency.score, baseline.latency.score),
            ("memory", current.memory.score, baseline.memory.score),
            ("knowledge", current.knowledge.score, baseline.knowledge.score),
        ]

    def has_regression(self, report: RegressionReport) -> bool:
        """Return ``True`` if ``report`` contains any regression."""
        return report.has_regression

    def regression_count(self, report: RegressionReport) -> int:
        """Return the number of regressions in ``report``."""
        return len(report.regressions)

    def improvement_count(self, report: RegressionReport) -> int:
        """Return the number of improvements in ``report``."""
        return len(report.improvements)


__all__ = ["REGRESSION_THRESHOLD", "RegressionDetector"]
