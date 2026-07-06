"""Tests for the Atlas Evaluation & Self-Improvement System (Phase 8).

Covers every module: models, scenarios, benchmark, runner, scoring,
regression, optimizer, dashboard, orchestrator. All tests are
deterministic and headless.
"""

from __future__ import annotations

import pytest

from atlas.evaluation import (
    REGRESSION_THRESHOLD,
    Benchmark,
    BenchmarkSuite,
    CostScore,
    DashboardGenerator,
    EvaluationOrchestrator,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunner,
    ExecutionScore,
    ImprovementSuggestion,
    KnowledgeScore,
    LatencyScore,
    MemoryScore,
    OptimizationReport,
    Optimizer,
    QualityScore,
    ReasoningScore,
    RegressionDetector,
    RegressionReport,
    RunStatus,
    Scenario,
    ScenarioCategory,
    ScenarioStore,
    ScoringEngine,
    SeverityLevel,
    SuggestionKind,
    __version__,
)

# ===========================================================================
# Package
# ===========================================================================


class TestPackage:
    def test_version(self) -> None:
        assert __version__ == "1.0.0"

    def test_exports(self) -> None:
        from atlas.evaluation import __all__

        assert "EvaluationOrchestrator" in __all__
        assert "ScoringEngine" in __all__
        assert "ScenarioStore" in __all__


# ===========================================================================
# Enums
# ===========================================================================


class TestEnums:
    def test_scenario_category_count(self) -> None:
        assert len(list(ScenarioCategory)) == 10

    def test_run_status_count(self) -> None:
        assert len(list(RunStatus)) == 5

    def test_severity_level_count(self) -> None:
        assert len(list(SeverityLevel)) == 5

    def test_suggestion_kind_count(self) -> None:
        assert len(list(SuggestionKind)) == 9


# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    def test_execution_score_default(self) -> None:
        s = ExecutionScore()
        assert s.success is True
        assert s.score == 1.0

    def test_execution_score_frozen(self) -> None:
        s = ExecutionScore()
        with pytest.raises(Exception):
            s.score = 0.5  # type: ignore[misc]

    def test_reasoning_score_default(self) -> None:
        s = ReasoningScore()
        assert s.coherence == 0.8

    def test_quality_score_default(self) -> None:
        s = QualityScore()
        assert s.relevance == 0.85

    def test_cost_score_default(self) -> None:
        s = CostScore()
        assert s.tokens_in == 0
        assert s.cost_efficiency == 0.8

    def test_latency_score_default(self) -> None:
        s = LatencyScore()
        assert s.total_duration_seconds == 0.0

    def test_memory_score_default(self) -> None:
        s = MemoryScore()
        assert s.entries_stored == 0

    def test_knowledge_score_default(self) -> None:
        s = KnowledgeScore()
        assert s.documents_retrieved == 0

    def test_scenario_default(self) -> None:
        s = Scenario(id="s1")
        assert s.category == ScenarioCategory.REASONING.value
        assert s.difficulty == 3

    def test_benchmark_default(self) -> None:
        b = Benchmark(id="b1")
        assert b.scenario_ids == ()
        assert b.version == "1.0.0"

    def test_evaluation_result_default(self) -> None:
        r = EvaluationResult(id="r1", scenario_id="s1")
        assert r.overall_score == 0.0
        assert r.error == ""

    def test_evaluation_run_default(self) -> None:
        r = EvaluationRun(id="run1")
        assert r.status == RunStatus.PENDING.value
        assert r.results == ()

    def test_regression_report_default(self) -> None:
        r = RegressionReport(id="rr1")
        assert r.has_regression is False
        assert r.regressions == ()

    def test_improvement_suggestion_default(self) -> None:
        s = ImprovementSuggestion(id="is1")
        assert s.kind == SuggestionKind.CONFIGURATION.value
        assert s.severity == SeverityLevel.LOW.value

    def test_optimization_report_default(self) -> None:
        r = OptimizationReport(id="or1")
        assert r.suggestions == ()
        assert r.overall_potential == 0.0


# ===========================================================================
# ScenarioStore
# ===========================================================================


class TestScenarioStore:
    def test_create(self) -> None:
        store = ScenarioStore()
        s = store.create(name="Test", prompt="Hello")
        assert s.name == "Test"
        assert store.count() == 1

    def test_get(self) -> None:
        store = ScenarioStore()
        s = store.create(name="Test")
        assert store.get(s.id) is s

    def test_get_missing(self) -> None:
        store = ScenarioStore()
        assert store.get("missing") is None

    def test_list_scenarios(self) -> None:
        store = ScenarioStore()
        store.create(name="A")
        store.create(name="B")
        assert len(store.list_scenarios()) == 2

    def test_list_by_category(self) -> None:
        store = ScenarioStore()
        store.create(name="A", category=ScenarioCategory.CODING.value)
        store.create(name="B", category=ScenarioCategory.RESEARCH.value)
        assert len(store.list_scenarios(category=ScenarioCategory.CODING.value)) == 1

    def test_list_by_tag(self) -> None:
        store = ScenarioStore()
        store.create(name="A", tags=("python",))
        store.create(name="B", tags=("rust",))
        assert len(store.list_scenarios(tag="python")) == 1

    def test_list_by_difficulty(self) -> None:
        store = ScenarioStore()
        store.create(name="A", difficulty=2)
        store.create(name="B", difficulty=4)
        assert len(store.list_scenarios(difficulty=2)) == 1

    def test_count(self) -> None:
        store = ScenarioStore()
        store.create(name="A")
        assert store.count() == 1

    def test_categories(self) -> None:
        store = ScenarioStore()
        store.create(name="A", category=ScenarioCategory.CODING.value)
        store.create(name="B", category=ScenarioCategory.RESEARCH.value)
        cats = store.categories()
        assert ScenarioCategory.CODING.value in cats
        assert ScenarioCategory.RESEARCH.value in cats

    def test_remove(self) -> None:
        store = ScenarioStore()
        s = store.create(name="A")
        assert store.remove(s.id) is True
        assert store.count() == 0

    def test_load_builtins(self) -> None:
        store = ScenarioStore()
        builtins = store.load_builtins()
        assert len(builtins) == 10
        assert store.count() == 10

    def test_builtins_have_all_categories(self) -> None:
        store = ScenarioStore()
        store.load_builtins()
        cats = store.categories()
        assert ScenarioCategory.WEBSITE_GENERATION.value in cats
        assert ScenarioCategory.RESEARCH.value in cats
        assert ScenarioCategory.VIDEO_CREATION.value in cats
        assert ScenarioCategory.CODING.value in cats
        assert ScenarioCategory.MINING.value in cats
        assert ScenarioCategory.AUTOMATION.value in cats


# ===========================================================================
# BenchmarkSuite
# ===========================================================================


class TestBenchmarkSuite:
    def test_create(self) -> None:
        suite = BenchmarkSuite()
        b = suite.create(name="Test", scenario_ids=("s1", "s2"))
        assert b.name == "Test"
        assert len(b.scenario_ids) == 2

    def test_get(self) -> None:
        suite = BenchmarkSuite()
        b = suite.create(name="Test")
        assert suite.get(b.id) is b

    def test_list(self) -> None:
        suite = BenchmarkSuite()
        suite.create(name="A")
        suite.create(name="B")
        assert len(suite.list_benchmarks()) == 2

    def test_add_scenario(self) -> None:
        suite = BenchmarkSuite()
        b = suite.create(name="Test")
        updated = suite.add_scenario(b.id, "s1")
        assert "s1" in updated.scenario_ids

    def test_remove_scenario(self) -> None:
        suite = BenchmarkSuite()
        b = suite.create(name="Test", scenario_ids=("s1", "s2"))
        updated = suite.remove_scenario(b.id, "s1")
        assert "s1" not in updated.scenario_ids

    def test_count(self) -> None:
        suite = BenchmarkSuite()
        suite.create(name="A")
        assert suite.count() == 1

    def test_delete(self) -> None:
        suite = BenchmarkSuite()
        b = suite.create(name="A")
        assert suite.delete(b.id) is True

    def test_unknown_benchmark_raises(self) -> None:
        suite = BenchmarkSuite()
        with pytest.raises(KeyError):
            suite.add_scenario("missing", "s1")


# ===========================================================================
# ScoringEngine
# ===========================================================================


class TestScoringEngine:
    def test_score_basic(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="Hello world")
        assert result.overall_score > 0.0
        assert result.execution.success is True

    def test_score_failed(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="", success=False, error="boom")
        assert result.execution.success is False
        assert result.error == "boom"

    def test_score_empty_output(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="")
        assert result.execution.completeness < 1.0

    def test_score_with_keywords(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(
            id="s1",
            prompt="Test",
            expected_keywords=("hello", "world"),
        )
        result = engine.score(scenario, output="hello world")
        assert result.quality.relevance == 1.0

    def test_score_partial_keywords(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(
            id="s1",
            prompt="Test",
            expected_keywords=("hello", "world", "foo"),
        )
        result = engine.score(scenario, output="hello world")
        assert 0.0 < result.quality.relevance < 1.0

    def test_score_no_keywords(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="Some output")
        assert result.quality.relevance == 0.8

    def test_score_expected_output_match(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(
            id="s1",
            prompt="Test",
            expected_output="Exact answer",
        )
        result = engine.score(scenario, output="Exact answer")
        assert result.quality.correctness == 1.0

    def test_score_cost_no_tokens(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="x")
        assert result.cost.cost_efficiency == 1.0

    def test_score_cost_with_tokens(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="x", tokens_in=500, tokens_out=200)
        assert result.cost.tokens_in == 500
        assert result.cost.score < 1.0

    def test_score_latency_fast(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="x", elapsed_seconds=0.5)
        assert result.latency.score == 1.0

    def test_score_latency_slow(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="x", elapsed_seconds=45.0)
        assert result.latency.score == 0.2

    def test_weights_sum_to_one(self) -> None:
        weights = ScoringEngine.weights()
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_overall_score_in_range(self) -> None:
        engine = ScoringEngine()
        scenario = Scenario(id="s1", prompt="Test")
        result = engine.score(scenario, output="Some output")
        assert 0.0 <= result.overall_score <= 1.0


# ===========================================================================
# EvaluationRunner
# ===========================================================================


class TestRunner:
    def test_run_scenario_no_fn(self) -> None:
        runner = EvaluationRunner()
        scenario = Scenario(id="s1", prompt="Test", name="Test")
        result = runner.run_scenario(scenario)
        assert result.execution.success is True
        assert len(result.output) > 0

    def test_run_scenario_with_fn(self) -> None:
        calls: list[str] = []

        def fake_run(**kwargs: object) -> str:
            calls.append(str(kwargs.get("prompt", "")))
            return "Result"

        runner = EvaluationRunner(run_fn=fake_run)
        scenario = Scenario(id="s1", prompt="Test")
        result = runner.run_scenario(scenario)
        assert result.output == "Result"
        assert len(calls) == 1

    def test_run_scenario_failure(self) -> None:
        def failing_run(**kwargs: object) -> str:
            raise RuntimeError("boom")

        runner = EvaluationRunner(run_fn=failing_run)
        scenario = Scenario(id="s1", prompt="Test")
        result = runner.run_scenario(scenario)
        assert result.execution.success is False
        assert "boom" in result.error

    def test_run_benchmark(self) -> None:
        runner = EvaluationRunner()
        benchmark = Benchmark(id="b1", scenario_ids=("s1", "s2"))
        scenarios = [
            Scenario(id="s1", prompt="A", name="A"),
            Scenario(id="s2", prompt="B", name="B"),
        ]
        run = runner.run_benchmark(benchmark, scenarios, version="1.0.0")
        assert run.status == RunStatus.COMPLETED.value
        assert len(run.results) == 2
        assert run.overall_score > 0.0

    def test_run_benchmark_skips_missing_scenarios(self) -> None:
        runner = EvaluationRunner()
        benchmark = Benchmark(id="b1", scenario_ids=("s1", "missing"))
        scenarios = [Scenario(id="s1", prompt="A", name="A")]
        run = runner.run_benchmark(benchmark, scenarios)
        assert len(run.results) == 1


# ===========================================================================
# RegressionDetector
# ===========================================================================


class TestRegression:
    def test_compare_no_change(self) -> None:
        detector = RegressionDetector()
        # Two identical runs
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.8)
        run1 = EvaluationRun(id="run1", results=(result,), overall_score=0.8)
        run2 = EvaluationRun(id="run2", results=(result,), overall_score=0.8)
        report = detector.compare(run2, run1)
        assert report.has_regression is False

    def test_compare_regression(self) -> None:
        detector = RegressionDetector(threshold=0.01)
        result1 = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.9)
        result2 = EvaluationResult(id="r2", scenario_id="s1", overall_score=0.5)
        run1 = EvaluationRun(id="run1", results=(result1,), overall_score=0.9)
        run2 = EvaluationRun(id="run2", results=(result2,), overall_score=0.5)
        report = detector.compare(run2, run1)
        assert report.has_regression is True
        assert len(report.regressions) > 0

    def test_compare_improvement(self) -> None:
        detector = RegressionDetector(threshold=0.01)
        result1 = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.5)
        result2 = EvaluationResult(id="r2", scenario_id="s1", overall_score=0.9)
        run1 = EvaluationRun(id="run1", results=(result1,), overall_score=0.5)
        run2 = EvaluationRun(id="run2", results=(result2,), overall_score=0.9)
        report = detector.compare(run2, run1)
        assert len(report.improvements) > 0

    def test_overall_delta(self) -> None:
        detector = RegressionDetector()
        run1 = EvaluationRun(id="run1", overall_score=0.7)
        run2 = EvaluationRun(id="run2", overall_score=0.9)
        report = detector.compare(run2, run1)
        assert report.overall_delta == pytest.approx(0.2)

    def test_regression_count(self) -> None:
        detector = RegressionDetector(threshold=0.01)
        result1 = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.9)
        result2 = EvaluationResult(id="r2", scenario_id="s1", overall_score=0.5)
        run1 = EvaluationRun(id="run1", results=(result1,), overall_score=0.9)
        run2 = EvaluationRun(id="run2", results=(result2,), overall_score=0.5)
        report = detector.compare(run2, run1)
        assert detector.regression_count(report) > 0

    def test_improvement_count(self) -> None:
        detector = RegressionDetector(threshold=0.01)
        result1 = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.5)
        result2 = EvaluationResult(id="r2", scenario_id="s1", overall_score=0.9)
        run1 = EvaluationRun(id="run1", results=(result1,), overall_score=0.5)
        run2 = EvaluationRun(id="run2", results=(result2,), overall_score=0.9)
        report = detector.compare(run2, run1)
        assert detector.improvement_count(report) > 0

    def test_threshold_default(self) -> None:
        detector = RegressionDetector()
        assert detector.threshold == REGRESSION_THRESHOLD


# ===========================================================================
# Optimizer
# ===========================================================================


class TestOptimizer:
    def test_analyse_good_run(self) -> None:
        opt = Optimizer()
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.95)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.95)
        report = opt.analyse(run)
        assert len(report.suggestions) == 0

    def test_analyse_bad_run(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.3)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.3)
        report = opt.analyse(run)
        assert len(report.suggestions) > 0

    def test_analyse_failed_execution(self) -> None:
        opt = Optimizer()
        result = EvaluationResult(
            id="r1",
            scenario_id="s1",
            execution=ExecutionScore(success=False, score=0.0),
            overall_score=0.3,
        )
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.3)
        report = opt.analyse(run)
        assert any(s.kind == SuggestionKind.WORKFLOW.value for s in report.suggestions)

    def test_analyse_low_quality(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(
            id="r1",
            scenario_id="s1",
            quality=QualityScore(relevance=0.2, score=0.2),
            overall_score=0.3,
        )
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.3)
        report = opt.analyse(run)
        assert any(s.kind == SuggestionKind.PROMPT.value for s in report.suggestions)

    def test_analyse_high_cost(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(
            id="r1",
            scenario_id="s1",
            cost=CostScore(tokens_in=10000, score=0.3),
            overall_score=0.3,
        )
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.3)
        report = opt.analyse(run)
        assert any(
            s.kind == SuggestionKind.PROVIDER_SELECTION.value
            for s in report.suggestions
        )

    def test_analyse_high_latency(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(
            id="r1",
            scenario_id="s1",
            latency=LatencyScore(score=0.3),
            overall_score=0.3,
        )
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.3)
        report = opt.analyse(run)
        assert any(s.kind == SuggestionKind.ROUTING.value for s in report.suggestions)

    def test_top_suggestions(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.2)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.2)
        report = opt.analyse(run)
        top = opt.top_suggestions(report, limit=2)
        assert len(top) <= 2

    def test_by_kind(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.2)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.2)
        report = opt.analyse(run)
        workflow_suggestions = opt.by_kind(report, SuggestionKind.WORKFLOW.value)
        assert all(
            s.kind == SuggestionKind.WORKFLOW.value for s in workflow_suggestions
        )

    def test_by_severity(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.2)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.2)
        report = opt.analyse(run)
        for severity in (
            SeverityLevel.LOW.value,
            SeverityLevel.MEDIUM.value,
            SeverityLevel.HIGH.value,
            SeverityLevel.CRITICAL.value,
        ):
            filtered = opt.by_severity(report, severity)
            assert all(s.severity == severity for s in filtered)

    def test_overall_potential(self) -> None:
        opt = Optimizer(threshold=0.9)
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.2)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.2)
        report = opt.analyse(run)
        assert report.overall_potential > 0.0


# ===========================================================================
# DashboardGenerator
# ===========================================================================


class TestDashboard:
    def test_run_summary(self) -> None:
        gen = DashboardGenerator()
        run = EvaluationRun(id="run1", overall_score=0.8, version="1.0.0")
        summary = gen.run_summary(run)
        assert summary["run_id"] == "run1"
        assert summary["overall_score"] == 0.8

    def test_dimension_breakdown(self) -> None:
        gen = DashboardGenerator()
        result = EvaluationResult(
            id="r1",
            scenario_id="s1",
            execution=ExecutionScore(score=0.9),
            overall_score=0.8,
        )
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.8)
        dims = gen.dimension_breakdown(run)
        assert "execution" in dims
        assert dims["execution"] == 0.9

    def test_dimension_breakdown_empty(self) -> None:
        gen = DashboardGenerator()
        run = EvaluationRun(id="run1")
        assert gen.dimension_breakdown(run) == {}

    def test_scenario_table(self) -> None:
        gen = DashboardGenerator()
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.8)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.8)
        table = gen.scenario_table(run)
        assert len(table) == 1
        assert table[0]["scenario_id"] == "s1"

    def test_regression_summary(self) -> None:
        gen = DashboardGenerator()
        report = RegressionReport(
            id="rr1", has_regression=True, regressions=(("s1", "overall", -0.1),)
        )
        summary = gen.regression_summary(report)
        assert summary["has_regression"] is True
        assert summary["regression_count"] == 1

    def test_optimization_summary(self) -> None:
        gen = DashboardGenerator()
        suggestion = ImprovementSuggestion(
            id="is1",
            kind=SuggestionKind.ROUTING.value,
            severity=SeverityLevel.HIGH.value,
            expected_impact=0.2,
        )
        report = OptimizationReport(
            id="or1", suggestions=(suggestion,), overall_potential=0.2
        )
        summary = gen.optimization_summary(report)
        assert summary["suggestion_count"] == 1
        assert summary["overall_potential"] == 0.2

    def test_full_dashboard(self) -> None:
        gen = DashboardGenerator()
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.8)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.8)
        dash = gen.full_dashboard(run)
        assert "run" in dash
        assert "dimensions" in dash
        assert "scenarios" in dash

    def test_full_dashboard_with_reports(self) -> None:
        gen = DashboardGenerator()
        result = EvaluationResult(id="r1", scenario_id="s1", overall_score=0.8)
        run = EvaluationRun(id="run1", results=(result,), overall_score=0.8)
        regression = RegressionReport(id="rr1")
        optimization = OptimizationReport(id="or1")
        dash = gen.full_dashboard(run, regression, optimization)
        assert "regression" in dash
        assert "optimization" in dash


# ===========================================================================
# EvaluationOrchestrator
# ===========================================================================


class TestOrchestrator:
    def test_construct(self) -> None:
        o = EvaluationOrchestrator()
        assert o is not None

    def test_load_builtins(self) -> None:
        o = EvaluationOrchestrator()
        builtins = o.load_builtin_scenarios()
        assert len(builtins) == 10

    def test_create_benchmark(self) -> None:
        o = EvaluationOrchestrator()
        b = o.create_benchmark("Test", scenario_ids=("s1",))
        assert b.name == "Test"

    def test_create_full_benchmark(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        assert len(b.scenario_ids) == 10

    def test_evaluate(self) -> None:
        o = EvaluationOrchestrator()
        scenario = Scenario(id="s1", prompt="Test", name="Test")
        result = o.evaluate(scenario)
        assert result.execution.success is True

    def test_benchmark(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run = o.benchmark(b, version="1.0.0")
        assert run.status == RunStatus.COMPLETED.value
        assert len(run.results) == 10

    def test_compare(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run1 = o.benchmark(b, version="1.0.0")
        run2 = o.benchmark(b, version="2.0.0")
        report = o.compare(run2.id, run1.id)
        assert report.current_run_id == run2.id

    def test_improve(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run = o.benchmark(b, version="1.0.0")
        report = o.improve(run.id)
        assert report.run_id == run.id

    def test_get_run(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run = o.benchmark(b, version="1.0.0")
        assert o.get_run(run.id) is run

    def test_get_run_missing(self) -> None:
        o = EvaluationOrchestrator()
        assert o.get_run("missing") is None

    def test_list_runs(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        o.benchmark(b, version="1.0.0")
        o.benchmark(b, version="2.0.0")
        assert len(o.list_runs()) == 2

    def test_list_runs_by_status(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        o.benchmark(b, version="1.0.0")
        assert len(o.list_runs(status=RunStatus.COMPLETED.value)) == 1

    def test_generate_dashboard(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run = o.benchmark(b, version="1.0.0")
        dash = o.generate_dashboard(run.id)
        assert "run" in dash
        assert "dimensions" in dash

    def test_status(self) -> None:
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        status = o.status()
        assert status["scenarios"] == 10

    def test_with_run_fn(self) -> None:
        calls: list[str] = []

        def fake_run(**kwargs: object) -> str:
            calls.append(str(kwargs.get("prompt", "")))
            return "Result"

        o = EvaluationOrchestrator(run_fn=fake_run)
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        o.benchmark(b, version="1.0.0")
        assert len(calls) == 10

    def test_unknown_run_raises(self) -> None:
        o = EvaluationOrchestrator()
        with pytest.raises(KeyError):
            o.improve("missing")


# ===========================================================================
# No subsystem imports
# ===========================================================================


class TestNoSubsystemImports:
    def test_evaluation_does_not_import_subsystems(self) -> None:
        """The evaluation package must not import any Atlas subsystem."""
        import os
        import re

        import atlas.evaluation

        root = os.path.dirname(atlas.evaluation.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|providers|mcp|memory|knowledge|workflows|tools|integration|agents|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline|workforce|collaboration|creator_pipeline)\b"
        )
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path) as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert (
            not offenders
        ), "atlas.evaluation imports other Atlas subsystems:\n" + "\n".join(offenders)

    def test_reload(self) -> None:
        import importlib

        import atlas.evaluation

        importlib.reload(atlas.evaluation)
        assert atlas.evaluation.__version__ == "1.0.0"


# ===========================================================================
# End-to-end integration
# ===========================================================================


class TestIntegration:
    def test_full_evaluation_cycle(self) -> None:
        """End-to-end: load builtins → benchmark → improve → dashboard."""
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run = o.benchmark(b, version="1.0.0")
        assert run.overall_score > 0.0
        opt = o.improve(run.id)
        dash = o.generate_dashboard(run.id)
        assert "run" in dash
        assert "dimensions" in dash

    def test_regression_detection_cycle(self) -> None:
        """Run two versions and compare for regressions."""
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run1 = o.benchmark(b, version="1.0.0")
        run2 = o.benchmark(b, version="2.0.0")
        report = o.compare(run2.id, run1.id)
        assert report.current_run_id == run2.id
        assert report.baseline_run_id == run1.id

    def test_optimization_suggestions_generated(self) -> None:
        """A low-scoring run should generate suggestions."""

        def bad_run(**kwargs: object) -> str:
            return "x"  # very short output → low scores

        o = EvaluationOrchestrator(run_fn=bad_run)
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run = o.benchmark(b, version="1.0.0")
        opt = o.improve(run.id)
        assert len(opt.suggestions) > 0

    def test_dashboard_with_regression_and_optimization(self) -> None:
        """Generate a dashboard that includes regression + optimization."""
        o = EvaluationOrchestrator()
        o.load_builtin_scenarios()
        b = o.create_full_benchmark()
        run1 = o.benchmark(b, version="1.0.0")
        run2 = o.benchmark(b, version="2.0.0")
        reg = o.compare(run2.id, run1.id)
        opt = o.improve(run2.id)
        dash = o.generate_dashboard(run2.id, reg.id, opt.id)
        assert "regression" in dash
        assert "optimization" in dash
