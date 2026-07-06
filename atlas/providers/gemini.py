"""Gemini provider — production implementation.

Re-exports :class:`~atlas.providers.real.gemini.RealGeminiProvider`
as :class:`GeminiProvider`. Real HTTP calls when ``GEMINI_API_KEY``
is set; deterministic fallback otherwise.
"""

from __future__ import annotations

from atlas.providers.real.gemini import RealGeminiProvider as GeminiProvider

__all__ = ["GeminiProvider"]
