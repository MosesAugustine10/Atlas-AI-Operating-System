"""Benchmark suites — repeatable benchmark collections.

The :class:`BenchmarkSuite` manages :class:`Benchmark` instances.
Each benchmark is a named collection of scenario ids that can be
run together to produce an :class:`EvaluationRun`.
"""

from __future__ import annotations

from atlas.evaluation.models import (
    Benchmark,
    _new_id,
)


class BenchmarkSuite:
    """Manages benchmark definitions."""

    def __init__(self) -> None:
        self._benchmarks: dict[str, Benchmark] = {}

    def create(
        self,
        name: str,
        description: str = "",
        scenario_ids: tuple[str, ...] = (),
        version: str = "1.0.0",
    ) -> Benchmark:
        """Create and register a new benchmark."""
        benchmark = Benchmark(
            id=_new_id("benchmark"),
            name=name,
            description=description,
            scenario_ids=scenario_ids,
            version=version,
        )
        self._benchmarks[benchmark.id] = benchmark
        return benchmark

    def get(self, benchmark_id: str) -> Benchmark | None:
        """Return the benchmark with ``benchmark_id`` or ``None``."""
        return self._benchmarks.get(benchmark_id)

    def list_benchmarks(self) -> list[Benchmark]:
        """Return all benchmarks."""
        return list(self._benchmarks.values())

    def add_scenario(self, benchmark_id: str, scenario_id: str) -> Benchmark:
        """Add a scenario to a benchmark."""
        benchmark = self._require(benchmark_id)
        new_ids = (*benchmark.scenario_ids, scenario_id)
        updated = Benchmark(
            id=benchmark.id,
            name=benchmark.name,
            description=benchmark.description,
            scenario_ids=new_ids,
            version=benchmark.version,
            created_at=benchmark.created_at,
            metadata=benchmark.metadata,
        )
        self._benchmarks[benchmark_id] = updated
        return updated

    def remove_scenario(self, benchmark_id: str, scenario_id: str) -> Benchmark:
        """Remove a scenario from a benchmark."""
        benchmark = self._require(benchmark_id)
        new_ids = tuple(sid for sid in benchmark.scenario_ids if sid != scenario_id)
        updated = Benchmark(
            id=benchmark.id,
            name=benchmark.name,
            description=benchmark.description,
            scenario_ids=new_ids,
            version=benchmark.version,
            created_at=benchmark.created_at,
            metadata=benchmark.metadata,
        )
        self._benchmarks[benchmark_id] = updated
        return updated

    def count(self) -> int:
        """Return the total number of benchmarks."""
        return len(self._benchmarks)

    def delete(self, benchmark_id: str) -> bool:
        """Delete a benchmark. Returns ``True`` if deleted."""
        return self._benchmarks.pop(benchmark_id, None) is not None

    def _require(self, benchmark_id: str) -> Benchmark:
        benchmark = self._benchmarks.get(benchmark_id)
        if benchmark is None:
            raise KeyError(f"benchmark {benchmark_id} not found")
        return benchmark


__all__ = ["BenchmarkSuite"]
