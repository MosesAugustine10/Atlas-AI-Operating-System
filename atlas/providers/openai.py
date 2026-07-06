"""OpenAI provider — production implementation.

This module re-exports :class:`~atlas.providers.real.openai.RealOpenAIProvider`
as :class:`OpenAIProvider`. When an API key is present, :meth:`generate`
makes a real HTTP call to the OpenAI Chat Completions API. When no key
is available, it falls back to deterministic mode so the pipeline
always works in tests and on air-gapped hosts.

Set the ``OPENAI_API_KEY`` environment variable to enable real API calls.
"""

from __future__ import annotations

from atlas.providers.real.openai import RealOpenAIProvider as OpenAIProvider

__all__ = ["OpenAIProvider"]
