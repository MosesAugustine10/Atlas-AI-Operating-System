"""Anthropic provider — production implementation.

Re-exports :class:`~atlas.providers.real.anthropic.RealAnthropicProvider`
as :class:`AnthropicProvider`. Real HTTP calls when ``ANTHROPIC_API_KEY``
is set; deterministic fallback otherwise.
"""

from __future__ import annotations

from atlas.providers.real.anthropic import RealAnthropicProvider as AnthropicProvider

__all__ = ["AnthropicProvider"]
