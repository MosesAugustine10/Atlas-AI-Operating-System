"""Optimizer — generate improvement suggestions.

The :class:`Optimizer` analyses an :class:`EvaluationRun` and produces
an :class:`OptimizationReport` containing :class:`ImprovementSuggestion`
instances. Suggestions cover routing, provider selection, workflow,
prompt engineering, agent collaboration, planning, memory, knowledge,
and configuration.
"""

from __future__ import annotations

from atlas.evaluation.models import (
    EvaluationResult,
    EvaluationRun,
    ImprovementSuggestion,
    OptimizationReport,
    SeverityLevel,
    SuggestionKind,
    _new_id,
)


class Optimizer:
    """Generates improvement suggestions from evaluation results."""

    def __init__(self, threshold: float = 0.6) -> None:
        self._threshold = threshold

    def analyse(self, run: EvaluationRun) -> OptimizationReport:
        """Analyse ``run`` and return an :class:`OptimizationReport`."""
        suggestions: list[ImprovementSuggestion] = []
        for result in run.results:
            suggestions.extend(self._analyse_result(result))
        # Also generate run-level suggestions
        if run.overall_score < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.CONFIGURATION.value,
                    severity=SeverityLevel.HIGH.value,
                    title="Overall score below threshold",
                    description=(
                        f"The overall score ({run.overall_score:.2f}) is below "
                        f"the threshold ({self._threshold:.2f}). Consider "
                        f"reviewing the top-scoring suggestions."
                    ),
                    expected_impact=0.1,
                    recommendation="Review and apply the top individual suggestions.",
                )
            )
        overall_potential = sum(s.expected_impact for s in suggestions)
        return OptimizationReport(
            id=_new_id("optimization"),
            run_id=run.id,
            suggestions=tuple(suggestions),
            overall_potential=overall_potential,
        )

    def _analyse_result(self, result: EvaluationResult) -> list[ImprovementSuggestion]:
        """Generate suggestions for a single result."""
        suggestions: list[ImprovementSuggestion] = []
        # Execution
        if not result.execution.success:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.WORKFLOW.value,
                    severity=SeverityLevel.CRITICAL.value,
                    title=f"Execution failed: {result.scenario_id[:20]}",
                    description=f"Execution error: {result.error}",
                    expected_impact=0.2,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Add error handling and retry logic to the workflow.",
                )
            )
        if result.execution.completeness < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.PLANNING.value,
                    severity=SeverityLevel.MEDIUM.value,
                    title=f"Incomplete execution: {result.scenario_id[:20]}",
                    description=(
                        f"Completeness is {result.execution.completeness:.2f}. "
                        "The execution did not complete all steps."
                    ),
                    expected_impact=0.1,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Improve task decomposition to ensure all steps are attempted.",
                )
            )
        # Reasoning
        if result.reasoning.score < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.PROMPT.value,
                    severity=SeverityLevel.MEDIUM.value,
                    title=f"Low reasoning quality: {result.scenario_id[:20]}",
                    description=(
                        f"Reasoning score is {result.reasoning.score:.2f}. "
                        f"Coherence={result.reasoning.coherence:.2f}, "
                        f"depth={result.reasoning.depth:.2f}, "
                        f"accuracy={result.reasoning.accuracy:.2f}."
                    ),
                    expected_impact=0.15,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Improve the system prompt to encourage deeper, more structured reasoning.",
                )
            )
        # Quality
        if result.quality.relevance < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.PROMPT.value,
                    severity=SeverityLevel.HIGH.value,
                    title=f"Low relevance: {result.scenario_id[:20]}",
                    description=(
                        f"Relevance is {result.quality.relevance:.2f}. "
                        "The output does not sufficiently match expected keywords."
                    ),
                    expected_impact=0.15,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Refine the prompt to more explicitly request the expected content.",
                )
            )
        # Cost
        if result.cost.score < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.PROVIDER_SELECTION.value,
                    severity=SeverityLevel.LOW.value,
                    title=f"High cost: {result.scenario_id[:20]}",
                    description=(
                        f"Cost score is {result.cost.score:.2f}. "
                        f"Tokens in={result.cost.tokens_in}, out={result.cost.tokens_out}."
                    ),
                    expected_impact=0.1,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Switch to a cheaper provider or reduce max_tokens for this scenario type.",
                )
            )
        # Latency
        if result.latency.score < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.ROUTING.value,
                    severity=SeverityLevel.MEDIUM.value,
                    title=f"High latency: {result.scenario_id[:20]}",
                    description=(
                        f"Latency score is {result.latency.score:.2f}. "
                        f"Duration={result.latency.total_duration_seconds:.2f}s."
                    ),
                    expected_impact=0.1,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Route to a faster provider or enable response streaming.",
                )
            )
        # Memory
        if result.memory.score < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.MEMORY.value,
                    severity=SeverityLevel.LOW.value,
                    title=f"Low memory usage: {result.scenario_id[:20]}",
                    description=(
                        f"Memory score is {result.memory.score:.2f}. "
                        "Memory was not effectively used."
                    ),
                    expected_impact=0.1,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Enable memory recall before execution to provide more context.",
                )
            )
        # Knowledge
        if result.knowledge.score < self._threshold:
            suggestions.append(
                ImprovementSuggestion(
                    id=_new_id("suggestion"),
                    kind=SuggestionKind.KNOWLEDGE.value,
                    severity=SeverityLevel.LOW.value,
                    title=f"Low knowledge usage: {result.scenario_id[:20]}",
                    description=(
                        f"Knowledge score is {result.knowledge.score:.2f}. "
                        "Knowledge retrieval was not effectively used."
                    ),
                    expected_impact=0.1,
                    affected_scenarios=(result.scenario_id,),
                    recommendation="Index more relevant documents and enable knowledge search before execution.",
                )
            )
        return suggestions

    def top_suggestions(
        self,
        report: OptimizationReport,
        limit: int = 5,
    ) -> list[ImprovementSuggestion]:
        """Return the ``limit`` highest-impact suggestions."""
        sorted_suggestions = sorted(
            report.suggestions,
            key=lambda s: s.expected_impact,
            reverse=True,
        )
        return sorted_suggestions[:limit]

    def by_kind(
        self,
        report: OptimizationReport,
        kind: str,
    ) -> list[ImprovementSuggestion]:
        """Return suggestions of a specific kind."""
        return [s for s in report.suggestions if s.kind == kind]

    def by_severity(
        self,
        report: OptimizationReport,
        severity: str,
    ) -> list[ImprovementSuggestion]:
        """Return suggestions of a specific severity."""
        return [s for s in report.suggestions if s.severity == severity]


__all__ = ["Optimizer"]
