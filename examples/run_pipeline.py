"""Run the live Atlas execution pipeline.

This example shows the simplest way to use the real AI pipeline:

    python examples/run_pipeline.py

The pipeline wires together Brain, Coordinator, ExecutionEngine,
ProviderManager, MemoryEngine, KnowledgeEngine, MCPManager, and
WorkflowEngine. ``brain.think(goal)`` actually executes tasks.

When API keys are present in the environment (OPENAI_API_KEY, etc.),
providers make real HTTP calls. Otherwise they run in deterministic
fallback mode — the pipeline still works, just without real LLM output.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run the pipeline."""
    from atlas.pipeline import build_pipeline

    print("Building Atlas live execution pipeline…")
    pipeline = build_pipeline()

    print(f"  Providers: {[p.name for p in pipeline.providers.registry.all()]}")
    print(f"  Memory: {pipeline.memory}")
    print(f"  Knowledge: {pipeline.knowledge.count()} documents")
    print()

    goals = [
        "Say hello to the user",
        "Write a short poem about the ocean",
        "Summarise the plot of Hamlet in one sentence",
    ]

    for goal in goals:
        print(f"▶ think({goal!r})")
        outcome = pipeline.think(goal)
        print(f"  status: {outcome.status.value}")
        print(f"  duration: {outcome.duration_seconds:.3f}s")
        print(f"  result: {str(outcome.result)[:120]}")
        print()

    print("Pipeline status:")
    for key, value in pipeline.status().items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
