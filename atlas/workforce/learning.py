"""Learning engine — worker skill improvement and specialisation growth.

The :class:`LearningEngine` tracks lessons learned by workers and
applies them to improve worker skills over time. Each lesson can
boost a skill level (capped at 1.0), record a mistake to avoid, or
note a best practice to follow.

The engine is pure-Python and never imports the Atlas
:class:`~atlas.intelligence.learning.LearningEngine` — it is a
workforce-specific layer that complements the Brain's learning.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    WorkerSkill,
    _new_id,
    _utcnow,
)


@dataclasses.dataclass(frozen=True)
class Lesson:
    """A single lesson learned by a worker.

    Parameters:
        id: Unique lesson identifier.
        worker_id: The worker who learned the lesson.
        skill_name: The skill the lesson relates to (or "" for general).
        kind: "best_practice", "mistake", or "insight".
        description: What was learned.
        impact: How much this lesson should boost the skill (0.0 to 1.0).
        timestamp: When the lesson was recorded.
        applied: Whether the lesson has been applied to the worker's skills.
    """

    id: str
    worker_id: str
    skill_name: str = ""
    kind: str = "insight"
    description: str = ""
    impact: float = 0.0
    timestamp: Any = dataclasses.field(default_factory=_utcnow)
    applied: bool = False


class LearningEngine:
    """Tracks lessons and applies them to worker skills."""

    def __init__(self) -> None:
        self._lessons: dict[str, Lesson] = {}
        self.logger = get_logger("workforce.learning")

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_lesson(
        self,
        worker_id: str,
        description: str,
        skill_name: str = "",
        kind: str = "insight",
        impact: float = 0.0,
    ) -> Lesson:
        """Record a lesson for ``worker_id``."""
        lesson = Lesson(
            id=_new_id("lesson"),
            worker_id=worker_id,
            skill_name=skill_name,
            kind=kind,
            description=description,
            impact=max(0.0, min(1.0, impact)),
        )
        self._lessons[lesson.id] = lesson
        self.logger.info(
            "Recorded lesson %s for worker %s (skill=%s, impact=%.2f)",
            lesson.id,
            worker_id,
            skill_name,
            lesson.impact,
        )
        return lesson

    def get_lesson(self, lesson_id: str) -> Lesson | None:
        """Return the lesson with ``lesson_id`` or ``None``."""
        return self._lessons.get(lesson_id)

    def lessons_for(self, worker_id: str) -> list[Lesson]:
        """Return all lessons for ``worker_id`` (chronological)."""
        lessons = [l for l in self._lessons.values() if l.worker_id == worker_id]
        lessons.sort(key=lambda l: l.timestamp)
        return lessons

    def lessons_for_skill(self, skill_name: str) -> list[Lesson]:
        """Return all lessons for ``skill_name``."""
        return [l for l in self._lessons.values() if l.skill_name == skill_name]

    def pending_lessons(self) -> list[Lesson]:
        """Return all lessons that have not been applied yet."""
        return [l for l in self._lessons.values() if not l.applied]

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply_lesson(
        self, lesson_id: str, skills: tuple[WorkerSkill, ...]
    ) -> tuple[WorkerSkill, ...]:
        """Apply a lesson to ``skills`` and return the updated tuple.

        If the lesson's ``skill_name`` matches a skill, the skill's level
        is boosted by ``lesson.impact`` (capped at 1.0). If the skill
        doesn't exist, it is added.
        """
        lesson = self._require(lesson_id)
        if not lesson.skill_name:
            # General lesson — no skill update
            self._mark_applied(lesson_id)
            return skills
        new_skills: list[WorkerSkill] = []
        found = False
        for skill in skills:
            if skill.name == lesson.skill_name:
                new_level = min(1.0, skill.level + lesson.impact)
                new_skills.append(dataclasses.replace(skill, level=new_level))
                found = True
            else:
                new_skills.append(skill)
        if not found:
            new_skills.append(
                WorkerSkill(
                    name=lesson.skill_name,
                    level=min(1.0, lesson.impact),
                )
            )
        self._mark_applied(lesson_id)
        return tuple(new_skills)

    def apply_all_pending(
        self,
        worker_id: str,
        skills: tuple[WorkerSkill, ...],
    ) -> tuple[WorkerSkill, ...]:
        """Apply all pending lessons for ``worker_id`` to ``skills``."""
        pending = [l for l in self.pending_lessons() if l.worker_id == worker_id]
        for lesson in pending:
            skills = self.apply_lesson(lesson.id, skills)
        return skills

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def lesson_count(self) -> int:
        """Return the total number of lessons."""
        return len(self._lessons)

    def count_for(self, worker_id: str) -> int:
        """Return the number of lessons for ``worker_id``."""
        return sum(1 for l in self._lessons.values() if l.worker_id == worker_id)

    def count_by_kind(self) -> dict[str, int]:
        """Return a dict of lesson counts by kind."""
        counts: dict[str, int] = {}
        for l in self._lessons.values():
            counts[l.kind] = counts.get(l.kind, 0) + 1
        return counts

    def average_impact(self, worker_id: str | None = None) -> float:
        """Return the average lesson impact for ``worker_id`` (or all)."""
        lessons = (
            self.lessons_for(worker_id) if worker_id else list(self._lessons.values())
        )
        if not lessons:
            return 0.0
        return sum(l.impact for l in lessons) / len(lessons)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, lesson_id: str) -> Lesson:
        lesson = self._lessons.get(lesson_id)
        if lesson is None:
            raise KeyError(f"lesson {lesson_id} not found")
        return lesson

    def _mark_applied(self, lesson_id: str) -> None:
        lesson = self._lessons.get(lesson_id)
        if lesson is None:
            return
        self._lessons[lesson_id] = dataclasses.replace(lesson, applied=True)


__all__ = ["LearningEngine", "Lesson"]
