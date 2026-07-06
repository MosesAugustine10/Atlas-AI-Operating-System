"""Scoring engine — multi-dimensional evaluation scoring.

The :class:`ScoringEngine` produces :class:`EvaluationResult` instances
by scoring an output across seven dimensions:

* :class:`ExecutionScore` — success, completeness, error/retry counts.
* :class:`ReasoningScore` — coherence, depth, accuracy, step count.
* :class:`QualityScore` — relevance, clarity, completeness, correctness.
* :class:`CostScore` — token usage, estimated cost, cost efficiency.
* :class:`LatencyScore` — duration, first-token time, throughput.
* :class:`MemoryScore` — entries stored/recalled, recall accuracy.
* :class:`KnowledgeScore` — docs indexed/retrieved, relevance, citations.

The engine also computes an overall weighted score.
"""

from __future__ import annotations

from atlas.evaluation.models import (
    CostScore,
    EvaluationResult,
    ExecutionScore,
    KnowledgeScore,
    LatencyScore,
    MemoryScore,
    QualityScore,
    ReasoningScore,
    Scenario,
    _new_id,
)

# ---------------------------------------------------------------------------
# Score weights (must sum to 1.0)
# ---------------------------------------------------------------------------

_WEIGHTS: dict[str, float] = {
    "execution": 0.20,
    "reasoning": 0.15,
    "quality": 0.25,
    "cost": 0.10,
    "latency": 0.10,
    "memory": 0.10,
    "knowledge": 0.10,
}


class ScoringEngine:
    """Produces multi-dimensional scores for evaluation results."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        scenario: Scenario,
        output: str,
        success: bool = True,
        error: str = "",
        elapsed_seconds: float = 0.0,
        run_id: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        memory_entries_stored: int = 0,
        memory_entries_recalled: int = 0,
        knowledge_docs_retrieved: int = 0,
    ) -> EvaluationResult:
        """Produce a full :class:`EvaluationResult` for a scenario output."""
        execution = self._score_execution(success, error, output)
        reasoning = self._score_reasoning(output)
        quality = self._score_quality(scenario, output)
        cost = self._score_cost(tokens_in, tokens_out)
        latency = self._score_latency(elapsed_seconds)
        memory = self._score_memory(memory_entries_stored, memory_entries_recalled)
        knowledge = self._score_knowledge(knowledge_docs_retrieved)
        overall = self._overall(
            execution.score,
            reasoning.score,
            quality.score,
            cost.score,
            latency.score,
            memory.score,
            knowledge.score,
        )
        return EvaluationResult(
            id=_new_id("result"),
            scenario_id=scenario.id,
            run_id=run_id,
            output=output,
            execution=execution,
            reasoning=reasoning,
            quality=quality,
            cost=cost,
            latency=latency,
            memory=memory,
            knowledge=knowledge,
            overall_score=overall,
            error=error,
        )

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    def _score_execution(
        self,
        success: bool,
        error: str,
        output: str,
    ) -> ExecutionScore:
        """Score execution quality."""
        completeness = 1.0 if success and output else 0.0
        error_count = 1 if error else 0
        score = 1.0 if success else 0.0
        if success and not output:
            completeness = 0.5
            score = 0.5
        return ExecutionScore(
            success=success,
            completeness=completeness,
            error_count=error_count,
            retry_count=0,
            score=score,
        )

    def _score_reasoning(self, output: str) -> ReasoningScore:
        """Score reasoning quality heuristically."""
        word_count = len(output.split())
        sentence_count = output.count(".") + output.count("!") + output.count("?")
        step_count = (
            output.count("because") + output.count("therefore") + output.count("so")
        )
        # Coherence: more sentences = more coherent (up to a point)
        coherence = min(1.0, sentence_count / 5.0) if output else 0.0
        # Depth: longer outputs tend to have more depth
        depth = min(1.0, word_count / 100.0) if output else 0.0
        # Accuracy: placeholder — real impl would cross-check facts
        accuracy = 0.8 if output else 0.0
        score = (coherence + depth + accuracy) / 3.0
        return ReasoningScore(
            coherence=coherence,
            depth=depth,
            accuracy=accuracy,
            step_count=step_count,
            score=score,
        )

    def _score_quality(self, scenario: Scenario, output: str) -> QualityScore:
        """Score output quality against the scenario's expectations."""
        if not output:
            return QualityScore(
                relevance=0.0,
                clarity=0.0,
                completeness=0.0,
                correctness=0.0,
                score=0.0,
            )
        # Relevance: how many expected keywords appear
        if scenario.expected_keywords:
            found = sum(
                1 for kw in scenario.expected_keywords if kw.lower() in output.lower()
            )
            relevance = found / len(scenario.expected_keywords)
        else:
            relevance = 0.8
        # Clarity: sentence structure heuristic
        clarity = min(1.0, len(output.split()) / 50.0)
        # Completeness: output length relative to a baseline
        completeness = min(1.0, len(output) / 200.0)
        # Correctness: placeholder
        correctness = 0.85
        # Expected-output exact match bonus
        if (
            scenario.expected_output
            and output.strip() == scenario.expected_output.strip()
        ):
            correctness = 1.0
            completeness = 1.0
        score = (relevance + clarity + completeness + correctness) / 4.0
        return QualityScore(
            relevance=relevance,
            clarity=clarity,
            completeness=completeness,
            correctness=correctness,
            score=score,
        )

    def _score_cost(self, tokens_in: int, tokens_out: int) -> CostScore:
        """Score cost efficiency."""
        total = tokens_in + tokens_out
        estimated_cost = (tokens_in * 0.00001) + (tokens_out * 0.00003)
        # Efficiency: fewer tokens = more efficient (normalised)
        if total == 0:
            efficiency = 1.0  # no cost = perfect efficiency
        elif total <= 100:
            efficiency = 1.0
        elif total <= 1000:
            efficiency = 0.8
        elif total <= 5000:
            efficiency = 0.6
        else:
            efficiency = 0.4
        return CostScore(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=estimated_cost,
            cost_efficiency=efficiency,
            score=efficiency,
        )

    def _score_latency(self, elapsed_seconds: float) -> LatencyScore:
        """Score latency."""
        if elapsed_seconds <= 0:
            return LatencyScore(score=1.0)
        if elapsed_seconds <= 1.0:
            score = 1.0
        elif elapsed_seconds <= 5.0:
            score = 0.8
        elif elapsed_seconds <= 15.0:
            score = 0.6
        elif elapsed_seconds <= 30.0:
            score = 0.4
        else:
            score = 0.2
        steps_per_second = 1.0 / elapsed_seconds if elapsed_seconds > 0 else 0.0
        return LatencyScore(
            total_duration_seconds=elapsed_seconds,
            first_token_seconds=elapsed_seconds * 0.1,
            steps_per_second=steps_per_second,
            latency_score=score,
            score=score,
        )

    def _score_memory(
        self,
        entries_stored: int,
        entries_recalled: int,
    ) -> MemoryScore:
        """Score memory usage."""
        integration = min(1.0, entries_recalled / 5.0) if entries_recalled > 0 else 0.5
        recall_accuracy = 0.8 if entries_recalled > 0 else 0.5
        score = (integration + recall_accuracy) / 2.0
        return MemoryScore(
            entries_stored=entries_stored,
            entries_recalled=entries_recalled,
            recall_accuracy=recall_accuracy,
            integration=integration,
            score=score,
        )

    def _score_knowledge(self, docs_retrieved: int) -> KnowledgeScore:
        """Score knowledge usage."""
        relevance = min(1.0, docs_retrieved / 3.0) if docs_retrieved > 0 else 0.5
        citation_accuracy = 0.85 if docs_retrieved > 0 else 0.5
        score = (relevance + citation_accuracy) / 2.0
        return KnowledgeScore(
            documents_retrieved=docs_retrieved,
            retrieval_relevance=relevance,
            citation_accuracy=citation_accuracy,
            score=score,
        )

    # ------------------------------------------------------------------
    # Overall
    # ------------------------------------------------------------------

    @staticmethod
    def _overall(
        execution: float,
        reasoning: float,
        quality: float,
        cost: float,
        latency: float,
        memory: float,
        knowledge: float,
    ) -> float:
        """Compute the weighted overall score."""
        return (
            execution * _WEIGHTS["execution"]
            + reasoning * _WEIGHTS["reasoning"]
            + quality * _WEIGHTS["quality"]
            + cost * _WEIGHTS["cost"]
            + latency * _WEIGHTS["latency"]
            + memory * _WEIGHTS["memory"]
            + knowledge * _WEIGHTS["knowledge"]
        )

    @staticmethod
    def weights() -> dict[str, float]:
        """Return the score weights."""
        return dict(_WEIGHTS)


__all__ = ["ScoringEngine"]
