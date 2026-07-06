"""Atlas Evaluation & Self-Improvement data models — frozen dataclasses and enums.

This module is a *leaf* in the evaluation package dependency graph. It
defines every value object exchanged between the benchmark, scenarios,
runner, scoring, regression, optimizer, dashboard, and orchestrator
layers. Nothing here imports Brain, Workforce, or any other Atlas
subsystem — the models are pure, immutable and dependency-free.

The Evaluation Layer sits ABOVE Brain and Workforce:

    User
      ↓
    Evaluation  ← this package
      ↓
    Brain / Workforce / Collaboration / Creator Pipeline
      ↓
    Execution / Runtime / Providers / MCP / Memory / Knowledge

The evaluation package NEVER imports concrete implementations. It
receives callbacks (e.g. ``run_fn``, ``think_fn``) via dependency
injection and calls them.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "eval") -> str:
    """Return a new unique identifier prefixed with ``prefix``."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ===========================================================================
# Enumerations
# ===========================================================================


class ScenarioCategory(enum.StrEnum):
    """Categories of evaluation scenarios.

    Attributes:
        WEBSITE_GENERATION: Generate a complete website.
        RESEARCH: Research a topic and produce a report.
        VIDEO_CREATION: Create a video from a prompt.
        CODING: Write code for a task.
        MINING: Mining-engineering analysis.
        AUTOMATION: Automate a multi-step workflow.
        REASONING: Pure reasoning / problem-solving.
        COLLABORATION: Multi-agent collaboration task.
        KNOWLEDGE: Knowledge retrieval / synthesis.
        MEMORY: Memory recall / integration.
    """

    WEBSITE_GENERATION = "website_generation"
    RESEARCH = "research"
    VIDEO_CREATION = "video_creation"
    CODING = "coding"
    MINING = "mining"
    AUTOMATION = "automation"
    REASONING = "reasoning"
    COLLABORATION = "collaboration"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"


class RunStatus(enum.StrEnum):
    """Lifecycle status of an evaluation run.

    Attributes:
        PENDING: The run has been created but not started.
        RUNNING: The run is executing.
        COMPLETED: The run completed successfully.
        FAILED: The run failed.
        CANCELLED: The run was cancelled.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SeverityLevel(enum.StrEnum):
    """Severity levels for regressions and suggestions.

    Attributes:
        INFO: Informational — no action needed.
        LOW: Low severity — minor impact.
        MEDIUM: Medium severity — noticeable impact.
        HIGH: High severity — significant impact.
        CRITICAL: Critical — must be fixed.
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestionKind(enum.StrEnum):
    """Kinds of improvement suggestions.

    Attributes:
        ROUTING: Provider routing improvement.
        PROVIDER_SELECTION: Switch to a different provider.
        WORKFLOW: Workflow structure change.
        PROMPT: Prompt engineering improvement.
        AGENT_COLLABORATION: Agent collaboration improvement.
        PLANNING: Planning / decomposition improvement.
        MEMORY: Memory usage improvement.
        KNOWLEDGE: Knowledge indexing improvement.
        CONFIGURATION: Configuration tuning.
    """

    ROUTING = "routing"
    PROVIDER_SELECTION = "provider_selection"
    WORKFLOW = "workflow"
    PROMPT = "prompt"
    AGENT_COLLABORATION = "agent_collaboration"
    PLANNING = "planning"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    CONFIGURATION = "configuration"


# ===========================================================================
# Score models
# ===========================================================================


@dataclass(frozen=True)
class ExecutionScore:
    """Score for execution quality.

    Parameters:
        success: Whether the execution succeeded.
        completeness: Fraction of steps completed (0.0 to 1.0).
        error_count: Number of errors encountered.
        retry_count: Number of retries needed.
        score: Overall execution score (0.0 to 1.0).
    """

    success: bool = True
    completeness: float = 1.0
    error_count: int = 0
    retry_count: int = 0
    score: float = 1.0


@dataclass(frozen=True)
class ReasoningScore:
    """Score for reasoning quality.

    Parameters:
        coherence: How coherent the reasoning is (0.0 to 1.0).
        depth: Reasoning depth (0.0 to 1.0).
        accuracy: Factual accuracy of conclusions (0.0 to 1.0).
        step_count: Number of reasoning steps.
        score: Overall reasoning score (0.0 to 1.0).
    """

    coherence: float = 0.8
    depth: float = 0.7
    accuracy: float = 0.85
    step_count: int = 0
    score: float = 0.8


@dataclass(frozen=True)
class QualityScore:
    """Score for output quality.

    Parameters:
        relevance: Relevance to the goal (0.0 to 1.0).
        clarity: Clarity / readability (0.0 to 1.0).
        completeness: Completeness of the output (0.0 to 1.0).
        correctness: Correctness of the output (0.0 to 1.0).
        score: Overall quality score (0.0 to 1.0).
    """

    relevance: float = 0.85
    clarity: float = 0.8
    completeness: float = 0.8
    correctness: float = 0.85
    score: float = 0.82


@dataclass(frozen=True)
class CostScore:
    """Score for cost efficiency.

    Parameters:
        tokens_in: Input tokens consumed.
        tokens_out: Output tokens produced.
        estimated_cost_usd: Estimated cost in USD.
        cost_efficiency: Cost efficiency score (0.0 to 1.0; higher = cheaper).
        score: Overall cost score (0.0 to 1.0).
    """

    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    cost_efficiency: float = 0.8
    score: float = 0.8


@dataclass(frozen=True)
class LatencyScore:
    """Score for latency / speed.

    Parameters:
        total_duration_seconds: Total wall-clock duration.
        first_token_seconds: Time to first token (or 0).
        steps_per_second: Execution throughput.
        latency_score: Latency score (0.0 to 1.0; higher = faster).
        score: Overall latency score (0.0 to 1.0).
    """

    total_duration_seconds: float = 0.0
    first_token_seconds: float = 0.0
    steps_per_second: float = 0.0
    latency_score: float = 0.8
    score: float = 0.8


@dataclass(frozen=True)
class MemoryScore:
    """Score for memory usage.

    Parameters:
        entries_stored: Number of memory entries stored.
        entries_recalled: Number of memory entries recalled.
        recall_accuracy: Fraction of recalled entries that were relevant.
        integration: How well memory was integrated into the output.
        score: Overall memory score (0.0 to 1.0).
    """

    entries_stored: int = 0
    entries_recalled: int = 0
    recall_accuracy: float = 0.8
    integration: float = 0.75
    score: float = 0.78


@dataclass(frozen=True)
class KnowledgeScore:
    """Score for knowledge usage.

    Parameters:
        documents_indexed: Number of knowledge documents indexed.
        documents_retrieved: Number of documents retrieved.
        retrieval_relevance: Fraction of retrieved docs that were relevant.
        citation_accuracy: Accuracy of citations / references.
        score: Overall knowledge score (0.0 to 1.0).
    """

    documents_indexed: int = 0
    documents_retrieved: int = 0
    retrieval_relevance: float = 0.8
    citation_accuracy: float = 0.85
    score: float = 0.82


# ===========================================================================
# Scenario + Benchmark
# ===========================================================================


@dataclass(frozen=True)
class Scenario:
    """A single evaluation scenario.

    Parameters:
        id: Unique scenario id.
        name: Display name.
        category: :class:`ScenarioCategory`.
        description: What the scenario tests.
        prompt: The prompt to evaluate.
        expected_output: Optional expected output for comparison.
        expected_keywords: Tuple of keywords that should appear in the output.
        timeout_seconds: Maximum allowed time.
        difficulty: Difficulty level (1 = easy, 5 = hard).
        tags: Tuple of tags.
        metadata: Immutable metadata mapping.
    """

    id: str
    name: str = ""
    category: str = ScenarioCategory.REASONING.value
    description: str = ""
    prompt: str = ""
    expected_output: str = ""
    expected_keywords: tuple[str, ...] = ()
    timeout_seconds: float = 60.0
    difficulty: int = 3
    tags: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Benchmark:
    """A benchmark suite — a named collection of scenarios.

    Parameters:
        id: Unique benchmark id.
        name: Display name.
        description: What the benchmark measures.
        scenario_ids: Tuple of scenario ids in the suite.
        version: Benchmark version string.
        created_at: When the benchmark was created.
        metadata: Immutable metadata mapping.
    """

    id: str
    name: str = ""
    description: str = ""
    scenario_ids: tuple[str, ...] = ()
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Evaluation result + run
# ===========================================================================


@dataclass(frozen=True)
class EvaluationResult:
    """The result of evaluating a single scenario.

    Parameters:
        id: Unique result id.
        scenario_id: The scenario that was evaluated.
        run_id: The evaluation run this result belongs to.
        output: The actual output produced.
        execution: :class:`ExecutionScore`.
        reasoning: :class:`ReasoningScore`.
        quality: :class:`QualityScore`.
        cost: :class:`CostScore`.
        latency: :class:`LatencyScore`.
        memory: :class:`MemoryScore`.
        knowledge: :class:`KnowledgeScore`.
        overall_score: Weighted overall score (0.0 to 1.0).
        error: Error message if the evaluation failed.
        timestamp: When the result was recorded.
    """

    id: str
    scenario_id: str
    run_id: str = ""
    output: str = ""
    execution: ExecutionScore = field(default_factory=ExecutionScore)
    reasoning: ReasoningScore = field(default_factory=ReasoningScore)
    quality: QualityScore = field(default_factory=QualityScore)
    cost: CostScore = field(default_factory=CostScore)
    latency: LatencyScore = field(default_factory=LatencyScore)
    memory: MemoryScore = field(default_factory=MemoryScore)
    knowledge: KnowledgeScore = field(default_factory=KnowledgeScore)
    overall_score: float = 0.0
    error: str = ""
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class EvaluationRun:
    """A single evaluation run (one execution of a benchmark).

    Parameters:
        id: Unique run id.
        benchmark_id: The benchmark that was run.
        version: The Atlas version being evaluated.
        status: :class:`RunStatus`.
        results: Tuple of :class:`EvaluationResult` instances.
        started_at: When the run started.
        completed_at: When the run completed (or None).
        overall_score: Aggregate score across all results.
        metadata: Immutable metadata mapping.
    """

    id: str
    benchmark_id: str = ""
    version: str = "0.0.0"
    status: str = RunStatus.PENDING.value
    results: tuple[EvaluationResult, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    overall_score: float = 0.0
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Regression + Improvement
# ===========================================================================


@dataclass(frozen=True)
class RegressionReport:
    """A report comparing two evaluation runs.

    Parameters:
        id: Unique report id.
        current_run_id: The current run.
        baseline_run_id: The baseline run.
        regressions: Tuple of (scenario_id, metric, delta) tuples.
        improvements: Tuple of (scenario_id, metric, delta) tuples.
        overall_delta: Change in overall score (positive = improvement).
        has_regression: Whether any regression was detected.
        generated_at: When the report was generated.
        metadata: Immutable metadata mapping.
    """

    id: str
    current_run_id: str = ""
    baseline_run_id: str = ""
    regressions: tuple[tuple[str, str, float], ...] = ()
    improvements: tuple[tuple[str, str, float], ...] = ()
    overall_delta: float = 0.0
    has_regression: bool = False
    generated_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ImprovementSuggestion:
    """A single improvement suggestion.

    Parameters:
        id: Unique suggestion id.
        kind: :class:`SuggestionKind`.
        severity: :class:`SeverityLevel`.
        title: Short title.
        description: Detailed description.
        expected_impact: Expected score improvement (0.0 to 1.0).
        affected_scenarios: Tuple of scenario ids affected.
        recommendation: Concrete recommendation text.
        metadata: Immutable metadata mapping.
    """

    id: str
    kind: str = SuggestionKind.CONFIGURATION.value
    severity: str = SeverityLevel.LOW.value
    title: str = ""
    description: str = ""
    expected_impact: float = 0.0
    affected_scenarios: tuple[str, ...] = ()
    recommendation: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OptimizationReport:
    """A report containing optimization suggestions.

    Parameters:
        id: Unique report id.
        run_id: The evaluation run this report is based on.
        suggestions: Tuple of :class:`ImprovementSuggestion` instances.
        overall_potential: Total expected improvement if all suggestions applied.
        generated_at: When the report was generated.
        metadata: Immutable metadata mapping.
    """

    id: str
    run_id: str = ""
    suggestions: tuple[ImprovementSuggestion, ...] = ()
    overall_potential: float = 0.0
    generated_at: datetime = field(default_factory=_utcnow)
    metadata: tuple[tuple[str, str], ...] = ()


# ===========================================================================
# Callback type aliases (for dependency injection)
# ===========================================================================


#: A callback that runs a scenario — typically Brain.think or Pipeline.run.
RunFn = Callable[..., str]

#: A callback that generates text — typically ProviderManager.generate.
GenerateFn = Callable[..., str]


__all__ = [
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
    "_new_id",
    "_utcnow",
]
