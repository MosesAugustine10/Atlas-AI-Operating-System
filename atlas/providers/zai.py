"""Z.ai provider — production implementation.

Re-exports :class:`~atlas.providers.real.zai.RealZAIProvider`
as :class:`ZAIProvider`. Real HTTP calls when ``ZAI_API_KEY``
is set; deterministic fallback otherwise.
"""

from __future__ import annotations

from atlas.providers.real.zai import RealZAIProvider as ZAIProvider

__all__ = ["ZAIProvider"]
