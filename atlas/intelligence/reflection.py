"""Reflection engine — compares expected vs actual and extracts lessons.

The :class:`ReflectionEngine` runs after every execution. It compares
what was expected to happen with what actually happened, detects
mistakes, and extracts :class:`Lesson` items that the
:class:`LearningEngine` stores for future improvement.

The current implementation is deterministic: it uses simple heuristics
to detect common mistakes (empty output, high latency, retries, etc.).
Future LLM-backed reflection can replace :meth:`reflect` without
changing the contract.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.models import (
    Lesson,
    Reflection,
)


class ReflectionEngine:
    """Evaluates execution outcomes and extracts lessons.

    Parameters:
        knowledge: Optional :class:`KnowledgeEngine` (for checking
            whether outputs are consistent with known facts).
        memory: Optional :class:`MemoryEngine` (for recalling past
            lessons that are relevant to the current execution).
    """

    def __init__(
        self,
        knowledge: Any = None,
        memory: Any = None,
    ) -> None:
        self.knowledge = knowledge
        self.memory = memory
        self.logger = get_logger("intelligence.reflection")

    def reflect(
        self,
        goal_id: str,
        expected: str,
        actual: str,
        success: bool,
        quality_score: float = 0.0,
        duration_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> Reflection:
        """Compare ``expected`` vs ``actual`` and extract lessons.

        Args:
            goal_id: The goal that was executed.
            expected: What was expected to happen.
            actual: What actually happened.
            success: Whether the execution succeeded.
            quality_score: 0.0 - 1.0 quality score from the critic.
            duration_seconds: Wall-clock duration.
            metadata: Free-form metadata from the execution.

        Returns:
            A :class:`Reflection` with mistakes, lessons, and a
            recommendation on whether to retry.
        """
        mistakes: list[str] = []
        lessons: list[Lesson] = []

        # Detect common mistakes.
        if not success:
            mistakes.append("execution failed")
            lessons.append(
                Lesson(
                    content=(
                        f"Goal '{expected[:50]}' failed — consider alternative "
                        f"approaches or retry with adjusted parameters."
                    ),
                    category="execution",
                    source="reflection",
                    confidence=0.7,
                )
            )

        if success and not actual.strip():
            mistakes.append("execution succeeded but produced no output")
            lessons.append(
                Lesson(
                    content=(
                        "Empty output detected — verify that the execution "
                        "produced meaningful results."
                    ),
                    category="quality",
                    source="reflection",
                    confidence=0.6,
                )
            )

        if quality_score < 0.5:
            mistakes.append(f"low quality score: {quality_score:.2f}")
            lessons.append(
                Lesson(
                    content=(
                        f"Quality score {quality_score:.2f} is below 0.5 — "
                        f"consider improving the plan or selecting a different "
                        f"approach."
                    ),
                    category="quality",
                    source="reflection",
                    confidence=0.8,
                )
            )

        if duration_seconds > 60.0:
            mistakes.append(f"high latency: {duration_seconds:.1f}s")
            lessons.append(
                Lesson(
                    content=(
                        f"Execution took {duration_seconds:.1f}s — consider "
                        f"optimising or parallelising tasks."
                    ),
                    category="performance",
                    source="reflection",
                    confidence=0.5,
                )
            )

        # Detect mismatch between expected and actual.
        if success and expected.strip() and actual.strip():
            expected_lower = expected.lower().strip()
            actual_lower = actual.lower().strip()
            if (
                expected_lower not in actual_lower
                and actual_lower not in expected_lower
            ):
                # Simple word-overlap check.
                expected_words = set(expected_lower.split())
                actual_words = set(actual_lower.split())
                overlap = len(expected_words & actual_words)
                total = len(expected_words | actual_words)
                if total > 0 and overlap / total < 0.3:
                    mistakes.append("expected and actual outputs differ significantly")
                    lessons.append(
                        Lesson(
                            content=(
                                "Expected and actual outputs have low word "
                                "overlap — verify that the goal was correctly "
                                "understood."
                            ),
                            category="planning",
                            source="reflection",
                            confidence=0.6,
                        )
                    )

        should_retry = not success and quality_score < 0.5
        final_quality = quality_score if success else 0.0

        reflection = Reflection(
            goal_id=goal_id,
            expected=expected,
            actual=actual,
            mistakes=mistakes,
            lessons=lessons,
            quality_score=final_quality,
            should_retry=should_retry,
            metadata=dict(metadata or {}),
        )
        self.logger.info(
            "Reflected on goal %s: mistakes=%d, lessons=%d, retry=%s",
            goal_id,
            len(mistakes),
            len(lessons),
            should_retry,
        )
        return reflection


__all__ = ["ReflectionEngine"]
