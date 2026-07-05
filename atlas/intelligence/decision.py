"""Decision engine — capability-based selection of providers, agents,
tools, workflows, and MCP connectors.

The :class:`DecisionEngine` chooses the best candidate for a task based
on capabilities, cost, availability, latency, quality, and history. It
is **capability-based**: it never hardcodes provider or tool names. All
candidates are injected as :class:`DecisionCandidate` instances.

The scoring formula weights each factor:

* capability match (required — binary)
* availability (0.0 - 1.0, weight 0.3)
* quality (0.0 - 1.0, weight 0.3)
* cost (lower is better, weight 0.2)
* latency (lower is better, weight 0.2)
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.intelligence.models import Decision, DecisionCandidate


class DecisionEngine:
    """Selects the best candidate for a task.

    Parameters:
        history_weight: Weight given to historical performance data.
            Defaults to 0.1. When 0, history is ignored.
    """

    def __init__(self, history_weight: float = 0.1) -> None:
        self.history_weight = history_weight
        self._history: dict[str, list[float]] = {}
        self.logger = get_logger("intelligence.decision")

    def decide(
        self,
        required_capability: str,
        candidates: list[DecisionCandidate],
        kind: str = "",
    ) -> Decision:
        """Select the best candidate for ``required_capability``.

        Args:
            required_capability: The capability the candidate must have.
            candidates: List of :class:`DecisionCandidate` instances.
            kind: Candidate kind (``"provider"``, ``"agent"``, etc.).

        Returns:
            A :class:`Decision` naming the selected candidate.

        Raises:
            ValueError: If no candidate matches the required capability.
        """
        if not required_capability:
            raise ValueError("required_capability must be non-empty")
        if not candidates:
            raise ValueError("candidates must be non-empty")

        # Filter by capability match.
        matching = [
            c
            for c in candidates
            if required_capability in c.capabilities or not c.capabilities
        ]
        if not matching:
            raise ValueError(f"no candidate has capability {required_capability!r}")

        # Score each candidate.
        scored = [(c, self._score(c, required_capability)) for c in matching]
        scored.sort(key=lambda x: x[1], reverse=True)
        best, best_score = scored[0]
        alternatives = [c.name for c, _ in scored[1:]]

        decision = Decision(
            selected=best.name,
            kind=kind or best.kind,
            reason=self._explain(best, best_score, required_capability),
            alternatives=alternatives,
            score=best_score,
            metadata={
                "required_capability": required_capability,
                "candidate_count": len(candidates),
                "matching_count": len(matching),
            },
        )
        self.logger.info(
            "Decided: %s (score=%.2f, kind=%s, capability=%s)",
            decision.selected,
            decision.score,
            decision.kind,
            required_capability,
        )
        return decision

    def record_outcome(
        self,
        candidate_name: str,
        quality: float,
    ) -> None:
        """Record the outcome of using ``candidate_name``.

        Future calls to :meth:`decide` will use this history to adjust
        scores.
        """
        self._history.setdefault(candidate_name, []).append(quality)
        # Keep only the last 100 outcomes.
        if len(self._history[candidate_name]) > 100:
            self._history[candidate_name] = self._history[candidate_name][-100:]

    def history(self, candidate_name: str) -> list[float]:
        """Return the quality history for ``candidate_name``."""
        return list(self._history.get(candidate_name, []))

    def clear_history(self) -> None:
        """Drop all recorded history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _score(
        self,
        candidate: DecisionCandidate,
        required_capability: str,
    ) -> float:
        """Compute a 0.0 - 1.0 score for ``candidate``."""
        # Availability (0.3 weight)
        availability_score = candidate.availability * 0.3
        # Quality (0.3 weight)
        quality_score = candidate.quality * 0.3
        # Cost (0.2 weight — lower is better, so invert)
        cost_score = (1.0 / (1.0 + candidate.cost)) * 0.2
        # Latency (0.2 weight — lower is better)
        latency_score = (1.0 / (1.0 + candidate.latency_ms / 100.0)) * 0.2
        # History bonus
        history = self._history.get(candidate.name, [])
        history_score = (
            (sum(history) / len(history)) * self.history_weight if history else 0.0
        )
        return (
            availability_score
            + quality_score
            + cost_score
            + latency_score
            + history_score
        )

    @staticmethod
    def _explain(
        candidate: DecisionCandidate,
        score: float,
        capability: str,
    ) -> str:
        """Produce a human-readable explanation."""
        return (
            f"Selected {candidate.name!r} for {capability!r} "
            f"(score={score:.2f}, availability={candidate.availability:.1f}, "
            f"quality={candidate.quality:.2f}, cost={candidate.cost:.1f}, "
            f"latency={candidate.latency_ms:.0f}ms)"
        )


__all__ = ["DecisionEngine"]
