"""Dashboard — generate evaluation reports for Atlas Desktop.

The :class:`DashboardGenerator` produces summary dicts and structured
reports suitable for display in the Atlas Desktop UI.
"""

from __future__ import annotations

from typing import Any

from atlas.evaluation.models import (
    EvaluationRun,
    OptimizationReport,
    RegressionReport,
    _new_id,
)


class DashboardGenerator:
    """Generates evaluation dashboards."""

    def run_summary(self, run: EvaluationRun) -> dict[str, Any]:
        """Return a flat dict summary of ``run``."""
        return {
            "run_id": run.id,
            "benchmark_id": run.benchmark_id,
            "version": run.version,
            "status": run.status,
            "scenario_count": len(run.results),
            "overall_score": round(run.overall_score, 4),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }

    def dimension_breakdown(self, run: EvaluationRun) -> dict[str, float]:
        """Return average scores per dimension."""
        if not run.results:
            return {}
        return {
            "execution": round(
                sum(r.execution.score for r in run.results) / len(run.results), 4
            ),
            "reasoning": round(
                sum(r.reasoning.score for r in run.results) / len(run.results), 4
            ),
            "quality": round(
                sum(r.quality.score for r in run.results) / len(run.results), 4
            ),
            "cost": round(sum(r.cost.score for r in run.results) / len(run.results), 4),
            "latency": round(
                sum(r.latency.score for r in run.results) / len(run.results), 4
            ),
            "memory": round(
                sum(r.memory.score for r in run.results) / len(run.results), 4
            ),
            "knowledge": round(
                sum(r.knowledge.score for r in run.results) / len(run.results), 4
            ),
        }

    def scenario_table(self, run: EvaluationRun) -> list[dict[str, Any]]:
        """Return a list of per-scenario summary dicts."""
        return [
            {
                "scenario_id": r.scenario_id,
                "overall": round(r.overall_score, 4),
                "execution": round(r.execution.score, 4),
                "reasoning": round(r.reasoning.score, 4),
                "quality": round(r.quality.score, 4),
                "cost": round(r.cost.score, 4),
                "latency": round(r.latency.score, 4),
                "memory": round(r.memory.score, 4),
                "knowledge": round(r.knowledge.score, 4),
                "success": r.execution.success,
                "error": r.error,
            }
            for r in run.results
        ]

    def regression_summary(self, report: RegressionReport) -> dict[str, Any]:
        """Return a summary of a regression report."""
        return {
            "has_regression": report.has_regression,
            "regression_count": len(report.regressions),
            "improvement_count": len(report.improvements),
            "overall_delta": round(report.overall_delta, 4),
            "regressions": [
                {
                    "scenario_id": sid,
                    "metric": metric,
                    "delta": round(delta, 4),
                }
                for sid, metric, delta in report.regressions
            ],
            "improvements": [
                {
                    "scenario_id": sid,
                    "metric": metric,
                    "delta": round(delta, 4),
                }
                for sid, metric, delta in report.improvements
            ],
        }

    def optimization_summary(self, report: OptimizationReport) -> dict[str, Any]:
        """Return a summary of an optimization report."""
        return {
            "suggestion_count": len(report.suggestions),
            "overall_potential": round(report.overall_potential, 4),
            "by_kind": self._count_by(report.suggestions, "kind"),
            "by_severity": self._count_by(report.suggestions, "severity"),
            "top_suggestions": [
                {
                    "id": s.id,
                    "kind": s.kind,
                    "severity": s.severity,
                    "title": s.title,
                    "expected_impact": round(s.expected_impact, 4),
                    "recommendation": s.recommendation,
                }
                for s in sorted(
                    report.suggestions,
                    key=lambda s: s.expected_impact,
                    reverse=True,
                )[:5]
            ],
        }

    def full_dashboard(
        self,
        run: EvaluationRun,
        regression: RegressionReport | None = None,
        optimization: OptimizationReport | None = None,
    ) -> dict[str, Any]:
        """Return a full dashboard dict combining all reports."""
        dashboard: dict[str, Any] = {
            "id": _new_id("dashboard"),
            "run": self.run_summary(run),
            "dimensions": self.dimension_breakdown(run),
            "scenarios": self.scenario_table(run),
        }
        if regression is not None:
            dashboard["regression"] = self.regression_summary(regression)
        if optimization is not None:
            dashboard["optimization"] = self.optimization_summary(optimization)
        return dashboard

    @staticmethod
    def _count_by(
        suggestions: Any,
        attr: str,
    ) -> dict[str, int]:
        """Count suggestions by attribute."""
        counts: dict[str, int] = {}
        for s in suggestions:
            val = getattr(s, attr)
            counts[val] = counts.get(val, 0) + 1
        return counts


__all__ = ["DashboardGenerator"]
