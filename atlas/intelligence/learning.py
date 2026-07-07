"""Learning engine — learns from execution history without code changes.

The :class:`LearningEngine` stores :class:`Lesson` items extracted by
the :class:`ReflectionEngine` and produces a :class:`LearningSummary`
that the :class:`Brain` and :class:`AdaptivePlanner` can consult to
improve future planning.

The engine is in-memory and append-only. For persistence, wrap it in
a concrete adapter that forwards to the :class:`MemoryEngine` or a
database.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.models import LearningSummary, Lesson


class LearningEngine:
    """Stores and retrieves lessons learned from execution.

    Parameters:
        memory: Optional :class:`MemoryEngine` (or compatible). When
            present, lessons are also written to memory so they persist
            across sessions.
        max_lessons: Maximum number of lessons to store. Defaults to
            1000. Older lessons are evicted when the limit is reached.
    """

    def __init__(
        self,
        memory: Any = None,
        max_lessons: int = 1000,
    ) -> None:
        if max_lessons < 1:
            raise ValueError("max_lessons must be >= 1")
        self.memory = memory
        self.max_lessons = max_lessons
        self._lessons: list[Lesson] = []
        self.logger = get_logger("intelligence.learning")

    def learn(self, lesson: Lesson) -> Lesson:
        """Store ``lesson`` and optionally write it to memory."""
        self._lessons.append(lesson)
        # Evict oldest if over limit.
        if len(self._lessons) > self.max_lessons:
            evicted = self._lessons.pop(0)
            self.logger.debug("Evicted old lesson: %s", evicted.id)
        # Write to memory if available.
        if self.memory is not None:
            try:
                remember_fn = getattr(self.memory, "remember", None)
                if callable(remember_fn):
                    remember_fn(
                        content={
                            "lesson_id": lesson.id,
                            "content": lesson.content,
                            "category": lesson.category,
                            "confidence": lesson.confidence,
                        },
                        source="intelligence.learning",
                        tags=["lesson", lesson.category],
                    )
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Failed to write lesson to memory: %s", exc)
        self.logger.info("Learned lesson %s: %s", lesson.id, lesson.content[:60])
        return lesson

    def learn_many(self, lessons: list[Lesson]) -> list[Lesson]:
        """Store multiple lessons."""
        return [self.learn(lesson) for lesson in lessons]

    def lessons(
        self,
        category: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[Lesson]:
        """Return lessons, optionally filtered by category / confidence."""
        result = [
            lesson
            for lesson in self._lessons
            if (category is None or lesson.category == category)
            and lesson.confidence >= min_confidence
        ]
        return result[-limit:] if limit > 0 else result

    def get(self, lesson_id: str) -> Lesson | None:
        """Return the lesson with ``lesson_id`` or ``None``."""
        for lesson in self._lessons:
            if lesson.id == lesson_id:
                return lesson
        return None

    def categories(self) -> list[str]:
        """Return every lesson category, sorted."""
        return sorted({lesson.category for lesson in self._lessons})

    def summary(self) -> LearningSummary:
        """Return a :class:`LearningSummary` of everything learned."""
        if not self._lessons:
            return LearningSummary()
        cat_counts: dict[str, int] = defaultdict(int)
        for lesson in self._lessons:
            cat_counts[lesson.category] += 1
        avg_conf = sum(lesson.confidence for lesson in self._lessons) / len(
            self._lessons
        )
        top = sorted(self._lessons, key=lambda x: x.confidence, reverse=True)[:5]
        return LearningSummary(
            total_lessons=len(self._lessons),
            categories=dict(cat_counts),
            avg_confidence=avg_conf,
            top_lessons=top,
        )

    def clear(self) -> None:
        """Drop every stored lesson."""
        self._lessons.clear()

    def __len__(self) -> int:
        return len(self._lessons)

    def __iter__(self):
        return iter(self._lessons)

    def __repr__(self) -> str:
        return f"<LearningEngine lessons={len(self._lessons)}>"


__all__ = ["LearningEngine"]
