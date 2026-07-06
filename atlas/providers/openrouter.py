"""OpenRouter provider — production implementation.

Re-exports :class:`~atlas.providers.real.openrouter.RealOpenRouterProvider`
as :class:`OpenRouterProvider`. Real HTTP calls when ``OPENROUTER_API_KEY``
is set; deterministic fallback otherwise.
"""

from __future__ import annotations

from atlas.providers.real.openrouter import (
    RealOpenRouterProvider as OpenRouterProvider,
)

__all__ = ["OpenRouterProvider"]
