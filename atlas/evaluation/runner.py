"""Evaluation runner — executes benchmarks using injected callbacks.

The :class:`EvaluationRunner` takes a :class:`Benchmark` and its
scenarios, runs each scenario via an injected ``run_fn`` callback,
and produces :class:`EvaluationResult` instances.

The runner NEVER imports Brain, Pipeline, or any Atlas subsystem
directly — it receives a ``run_fn`` callable (typically bound to
``Brain.think`` or ``Pipeline.run``) and calls it.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from atlas.evaluation.models import (
    Benchmark,
    EvaluationResult,
    EvaluationRun,
    RunStatus,
    Scenario,
    _new_id,
    _utcnow,
)
from atlas.evaluation.scoring import ScoringEngine


class EvaluationRunner:
    """Executes benchmarks via an injected callback.

    Parameters:
        run_fn: Optional callback invoked with ``(prompt, **kwargs)``
            and returning a result string. When omitted, a deterministic
            placeholder is produced.
        scoring: Optional :class:`ScoringEngine`. Created fresh when omitted.
    """

    def __init__(
        self,
        run_fn: Callable[..., str] | None = None,
        scoring: ScoringEngine | None = None,
    ) -> None:
        self._run_fn = run_fn
        self.scoring = scoring or ScoringEngine()

    def run_benchmark(
        self,
        benchmark: Benchmark,
        scenarios: list[Scenario],
        version: str = "0.0.0",
    ) -> EvaluationRun:
        """Run a full benchmark and return an :class:`EvaluationRun`."""
        run = EvaluationRun(
            id=_new_id("run"),
            benchmark_id=benchmark.id,
            version=version,
            status=RunStatus.RUNNING.value,
            started_at=_utcnow(),
        )
        results: list[EvaluationResult] = []
        scenario_map = {s.id: s for s in scenarios}
        for scenario_id in benchmark.scenario_ids:
            scenario = scenario_map.get(scenario_id)
            if scenario is None:
                continue
            result = self.run_scenario(scenario, run.id)
            results.append(result)
        # Compute overall score
        scores = [r.overall_score for r in results if r.overall_score > 0]
        overall = sum(scores) / len(scores) if scores else 0.0
        return EvaluationRun(
            id=run.id,
            benchmark_id=benchmark.id,
            version=version,
            status=RunStatus.COMPLETED.value,
            results=tuple(results),
            started_at=run.started_at,
            completed_at=_utcnow(),
            overall_score=overall,
        )

    def run_scenario(
        self,
        scenario: Scenario,
        run_id: str = "",
    ) -> EvaluationResult:
        """Run a single scenario and return its :class:`EvaluationResult`."""
        start = time.monotonic()
        output = ""
        error = ""
        success = True
        try:
            if self._run_fn is not None:
                output = str(
                    self._run_fn(
                        prompt=scenario.prompt,
                        scenario=scenario,
                    )
                )
            else:
                output = f"[deterministic] {scenario.prompt[:80]}"
        except Exception as exc:  # noqa: BLE001 — surface any error
            error = str(exc)
            success = False
            output = ""
        elapsed = time.monotonic() - start
        result = self.scoring.score(
            scenario=scenario,
            output=output,
            success=success,
            error=error,
            elapsed_seconds=elapsed,
            run_id=run_id,
        )
        return result


__all__ = ["EvaluationRunner"]
