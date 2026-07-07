"""Critic — reviews outputs and produces warnings, confidence, and quality scores.

The :class:`Critic` inspects the output of an execution and produces a
:class:`Critique` containing warnings, a confidence score, and a
quality score. The critique feeds into the :class:`ReflectionEngine`
and the :class:`LearningEngine`.

The current implementation is deterministic: it uses simple heuristics
(output length, error markers, completeness checks). Future LLM-backed
critique can replace :meth:`critique` without changing the contract.
"""

from __future__ import annotations

from typing import Any

from atlas.core.logger import get_logger
from atlas.intelligence.models import Critique


class Critic:
    """Reviews execution outputs.

    Parameters:
        min_output_length: Minimum acceptable output length (characters).
            Defaults to 10.
        error_markers: Tuple of substrings that indicate an error in
            the output.
    """

    def __init__(
        self,
        min_output_length: int = 10,
        error_markers: tuple[str, ...] = (
            "error",
            "failed",
            "exception",
            "traceback",
            "null",
            "none",
        ),
    ) -> None:
        self.min_output_length = min_output_length
        self.error_markers = tuple(m.lower() for m in error_markers)
        self.logger = get_logger("intelligence.critic")

    def critique(
        self,
        output: Any,
        expected: str | None = None,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Critique:
        """Review ``output`` and return a :class:`Critique`.

        Args:
            output: The execution output to review.
            expected: Optional description of what was expected.
            success: Whether the execution succeeded.
            metadata: Free-form metadata from the execution.

        Returns:
            A :class:`Critique` with warnings, confidence, and quality.
        """
        warnings: list[str] = []
        confidence = 0.5
        quality = 0.5

        output_str = str(output) if output is not None else ""

        # Check success.
        if not success:
            warnings.append("execution reported failure")
            confidence = 0.0
            quality = 0.0
        else:
            # Check output length.
            if len(output_str) < self.min_output_length:
                warnings.append(
                    f"output is short ({len(output_str)} chars < "
                    f"{self.min_output_length})"
                )
                quality -= 0.2
            else:
                quality += 0.2

            # Check for error markers.
            output_lower = output_str.lower()
            found_markers = [m for m in self.error_markers if m in output_lower]
            if found_markers:
                warnings.append(f"error markers found in output: {found_markers}")
                quality -= 0.3
                confidence -= 0.2

            # Check for None / empty.
            if output is None:
                warnings.append("output is None")
                quality = 0.0
                confidence = 0.0
            elif output_str.strip() == "":
                warnings.append("output is empty")
                quality = 0.0
                confidence = 0.1

            # Check against expected.
            if expected:
                expected_words = set(expected.lower().split())
                output_words = set(output_lower.split())
                if expected_words:
                    overlap = len(expected_words & output_words)
                    coverage = overlap / len(expected_words)
                    if coverage < 0.3:
                        warnings.append(
                            f"output has low coverage of expected terms "
                            f"({coverage:.0%})"
                        )
                        quality -= 0.1
                    else:
                        quality += 0.1 * coverage
                        confidence += 0.2 * coverage

        # Clamp scores.
        quality = max(0.0, min(1.0, quality))
        confidence = max(0.0, min(1.0, confidence))

        # If no warnings, boost confidence.
        if not warnings and success:
            confidence = max(confidence, 0.8)
            quality = max(quality, 0.7)

        critique = Critique(
            warnings=warnings,
            confidence=confidence,
            quality_score=quality,
            notes=f"reviewed output of {len(output_str)} chars",
        )
        self.logger.info(
            "Critiqued output: warnings=%d, confidence=%.2f, quality=%.2f",
            len(warnings),
            confidence,
            quality,
        )
        return critique


__all__ = ["Critic"]
