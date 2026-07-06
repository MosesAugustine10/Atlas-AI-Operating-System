"""Ollama provider — production implementation.

Re-exports :class:`~atlas.providers.real.ollama.RealOllamaProvider`
as :class:`OllamaProvider`. Makes real HTTP calls to a local Ollama
instance at ``http://localhost:11434``; deterministic fallback when
Ollama is not running.
"""

from __future__ import annotations

from atlas.providers.real.ollama import RealOllamaProvider as OllamaProvider

__all__ = ["OllamaProvider"]
