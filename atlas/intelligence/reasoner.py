"""Reasoner — produces reasoning chains using injected subsystems.

The :class:`Reasoner` builds :class:`~atlas.intelligence.models.ReasoningChain`
instances by combining information from the :class:`KnowledgeEngine`,
:class:`MemoryEngine`, and :class:`ProviderManager`. It is
**provider-agnostic**: it never hardcodes provider names or capabilities.
All subsystems are injected.

The current implementation is deterministic: it queries the injected
subsystems (if available) and assembles a fixed reasoning chain. Future
LLM-backed reasoning can replace :meth:`reason` without changing the
contract.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.models import (
    ReasoningChain,
    ReasoningStep,
    ReasoningStepType,
)


class Reasoner:
    """Produces reasoning chains from knowledge, memory, and providers.

    Parameters:
        knowledge: Optional :class:`KnowledgeEngine` (or compatible).
            When present, the reasoner searches for relevant documents.
        memory: Optional :class:`MemoryEngine` (or compatible). When
            present, the reasoner recalls relevant memories.
        providers: Optional :class:`ProviderManager` (or compatible).
            When present, the reasoner can generate hypotheses via the
            provider.
    """

    def __init__(
        self,
        knowledge: Any = None,
        memory: Any = None,
        providers: Any = None,
    ) -> None:
        self.knowledge = knowledge
        self.memory = memory
        self.providers = providers
        self.logger = get_logger("intelligence.reasoner")

    def reason(
        self,
        goal_description: str,
        context: dict[str, Any] | None = None,
    ) -> ReasoningChain:
        """Produce a :class:`ReasoningChain` for ``goal_description``.

        The chain follows a fixed pattern:

        1. **Observe** — search knowledge and recall memory.
        2. **Hypothesize** — form a hypothesis about how to achieve the goal.
        3. **Deduce** — deduce required steps from the hypothesis.
        4. **Infer** — infer potential issues / risks.
        5. **Evaluate** — evaluate the approach.
        6. **Decide** — conclude with a recommended approach.
        """
        dict(context or {})
        steps: list[ReasoningStep] = []

        # 1. Observe
        evidence: list[str] = []
        knowledge_hits = self._search_knowledge(goal_description)
        if knowledge_hits:
            evidence.extend(f"knowledge:{hit}" for hit in knowledge_hits[:3])
        memory_hits = self._recall_memory(goal_description)
        if memory_hits:
            evidence.extend(f"memory:{hit}" for hit in memory_hits[:3])
        steps.append(
            ReasoningStep(
                step_type=ReasoningStepType.OBSERVE,
                content=(
                    f"Observed {len(evidence)} relevant items for: "
                    f"{goal_description[:60]}"
                ),
                evidence=evidence,
                confidence=0.9 if evidence else 0.5,
            )
        )

        # 2. Hypothesize
        hypothesis = self._generate_hypothesis(goal_description, evidence)
        steps.append(
            ReasoningStep(
                step_type=ReasoningStepType.HYPOTHESIZE,
                content=hypothesis,
                evidence=evidence,
                confidence=0.7,
            )
        )

        # 3. Deduce
        deduction = (
            "Based on the hypothesis, the goal can be achieved by "
            "breaking it into ordered sub-tasks and executing them "
            "with the available capabilities."
        )
        steps.append(
            ReasoningStep(
                step_type=ReasoningStepType.DEDUCE,
                content=deduction,
                confidence=0.8,
            )
        )

        # 4. Infer
        inferences = self._infer_risks(goal_description, evidence)
        steps.append(
            ReasoningStep(
                step_type=ReasoningStepType.INFER,
                content=inferences,
                confidence=0.6,
            )
        )

        # 5. Evaluate
        evaluation = (
            "The approach is feasible with the available subsystems. "
            "Confidence is moderate due to potential unknowns."
        )
        steps.append(
            ReasoningStep(
                step_type=ReasoningStepType.EVALUATE,
                content=evaluation,
                confidence=0.7,
            )
        )

        # 6. Decide
        conclusion = (
            f"Proceed with decomposing '{goal_description[:60]}' into "
            f"ordered sub-tasks and executing them adaptively."
        )
        steps.append(
            ReasoningStep(
                step_type=ReasoningStepType.DECIDE,
                content=conclusion,
                confidence=0.75,
            )
        )

        overall = sum(s.confidence for s in steps) / len(steps) if steps else 0.0
        chain = ReasoningChain(
            steps=steps,
            conclusion=conclusion,
            overall_confidence=overall,
            metadata={
                "goal": goal_description,
                "evidence_count": len(evidence),
                "knowledge_hits": len(knowledge_hits),
                "memory_hits": len(memory_hits),
            },
        )
        self.logger.info(
            "Reasoned about goal: %r (steps=%d, confidence=%.2f)",
            goal_description[:60],
            len(steps),
            overall,
        )
        return chain

    # ------------------------------------------------------------------
    # Subsystem queries
    # ------------------------------------------------------------------

    def _search_knowledge(self, query: str) -> list[str]:
        """Search the knowledge engine (if injected)."""
        if self.knowledge is None:
            return []
        try:
            search_fn = getattr(self.knowledge, "search", None)
            if callable(search_fn):
                results = search_fn(query)
                return [
                    (
                        getattr(r, "chunk", r).content
                        if hasattr(getattr(r, "chunk", r), "content")
                        else str(r)
                    )
                    for r in results
                ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Knowledge search failed: %s", exc)
        return []

    def _recall_memory(self, query: str) -> list[str]:
        """Recall from the memory engine (if injected)."""
        if self.memory is None:
            return []
        try:
            recall_fn = getattr(self.memory, "recall", None)
            if callable(recall_fn):
                results = recall_fn()
                return [str(getattr(r, "content", r)) for r in results[:5]]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Memory recall failed: %s", exc)
        return []

    def _generate_hypothesis(self, goal: str, evidence: list[str]) -> str:
        """Generate a hypothesis about how to achieve ``goal``."""
        if evidence:
            return (
                f"Based on {len(evidence)} evidence item(s), the goal "
                f"'{goal[:50]}' can likely be achieved through a "
                f"structured plan."
            )
        return (
            f"The goal '{goal[:50]}' appears achievable but lacks "
            f"supporting evidence — proceeding with caution."
        )

    def _infer_risks(self, goal: str, evidence: list[str]) -> str:
        """Infer potential risks."""
        risks: list[str] = []
        if not evidence:
            risks.append("No supporting evidence found")
        if len(evidence) < 2:
            risks.append("Limited evidence may lead to suboptimal planning")
        risks.append("External dependencies may be unavailable")
        return "Potential risks: " + "; ".join(risks)


__all__ = ["Reasoner"]
