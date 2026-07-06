"""Provider manager - high-level API for LLM access with retry and cost tracking.

The :class:`ProviderManager` is the single entry point through which the
Kernel and agents invoke LLMs. It depends only on the
:class:`ProviderRouter`, which in turn selects the right provider. The
manager exposes convenience methods (``generate``, ``chat``, ``complete``,
``stream``, ``health``, ``list_models``) so callers never touch providers
directly.

Production features:
* **Automatic retry** - failed calls are retried up to ``max_retries`` times.
* **Fallback** - when the selected provider fails, the next available
  provider is tried automatically.
* **Cost tracking** - every call's token usage and estimated cost are
  accumulated in ``total_cost_usd`` and ``total_tokens``.
* **Streaming** - :meth:`stream` yields :class:`ProviderResponse` chunks
  for real-time UI updates.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime

from atlas.core.logger import get_logger
from atlas.providers.base import BaseProvider
from atlas.providers.models import (
    Message,
    ProviderRequest,
    ProviderResponse,
)
from atlas.providers.registry import ProviderRegistry
from atlas.providers.router import ProviderRouter, RoutingStrategy

#: Default maximum retry attempts for a failed call.
DEFAULT_MAX_RETRIES: int = 3

#: Default delay between retries (seconds).
DEFAULT_RETRY_DELAY: float = 1.0


class ProviderManager:
    """High-level facade over the provider routing layer.

    Parameters:
        registry: The provider registry. Created empty if omitted.
        router: The provider router. Defaults to a new AUTO router.
        max_retries: Maximum retry attempts for failed calls.
        retry_delay: Delay between retries in seconds.
    """

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        router: ProviderRouter | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        # NOTE: explicit ``is None`` check because ProviderRegistry defines
        # ``__len__`` and would be falsy when empty.
        self.registry = registry if registry is not None else ProviderRegistry()
        self.router = router if router is not None else ProviderRouter(self.registry)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = get_logger("provider.manager")

        # Cost tracking
        self.total_cost_usd: float = 0.0
        self.total_tokens_in: int = 0
        self.total_tokens_out: int = 0
        self.call_count: int = 0
        self.error_count: int = 0
        self._call_history: list[dict[str, object]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self, provider: BaseProvider, make_default: bool = False
    ) -> ProviderManager:
        """Register a provider with the manager's registry."""
        self.registry.register(provider, make_default=make_default)
        return self

    # ------------------------------------------------------------------
    # Generation (with retry + fallback)
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: str = "default",
        provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        """Generate a completion for ``prompt``.

        Routes to the selected provider via the router. If the call fails,
        it is retried up to ``max_retries`` times. If all retries fail,
        the next available provider is tried (fallback). Raises
        :class:`RuntimeError` if no provider is available.
        """
        request = ProviderRequest(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._generate_with_retry(request, provider)

    def chat(
        self,
        messages: list[Message],
        *,
        model: str = "default",
        provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ProviderResponse:
        """Generate a chat completion for ``messages``."""
        request = ProviderRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._generate_with_retry(request, provider)

    def complete(self, prompt: str, **kwargs: object) -> ProviderResponse:
        """Alias for :meth:`generate` (completion-style API)."""
        return self.generate(prompt, **kwargs)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def stream(
        self,
        prompt: str,
        *,
        model: str = "default",
        provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Iterator[ProviderResponse]:
        """Stream a completion, yielding :class:`ProviderResponse` chunks."""
        request = ProviderRequest(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
        )
        chosen = self._resolve(provider)
        try:
            yield from chosen.stream(request)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Stream from %s failed: %s", chosen.name, exc)
            self.error_count += 1
            yield ProviderResponse(
                text="",
                model=request.model,
                provider=chosen.name,
                finish_reason="error",
                metadata={"error": str(exc)},
            )

    # ------------------------------------------------------------------
    # Health + models
    # ------------------------------------------------------------------

    def health(self) -> dict[str, bool]:
        """Return a ``{provider_name: healthy}`` map for all providers."""
        return {p.name: p.health() for p in self.registry.all()}

    def list_models(self, provider: str | None = None) -> dict[str, list[str]]:
        """Return available models per provider."""
        if provider is not None:
            instance = self.registry.get(provider)
            return {provider: instance.available_models()} if instance else {}
        return {p.name: p.available_models() for p in self.registry.all()}

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    def cost_summary(self) -> dict[str, object]:
        """Return a summary of accumulated costs."""
        return {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "average_cost_per_call": (
                round(self.total_cost_usd / self.call_count, 6)
                if self.call_count > 0
                else 0.0
            ),
        }

    def call_history(self, limit: int = 50) -> list[dict[str, object]]:
        """Return the recent call history."""
        return list(reversed(self._call_history[-limit:]))

    def reset_cost_tracking(self) -> None:
        """Reset all cost counters."""
        self.total_cost_usd = 0.0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.call_count = 0
        self.error_count = 0
        self._call_history.clear()

    # ------------------------------------------------------------------
    # Provider listing
    # ------------------------------------------------------------------

    def provider_names(self) -> list[str]:
        """Return the sorted list of registered provider names."""
        return sorted(p.name for p in self.registry.all())

    def provider_count(self) -> int:
        """Return the number of registered providers."""
        return len(self.registry.all())

    # ------------------------------------------------------------------
    # Internals — retry + fallback
    # ------------------------------------------------------------------

    def _generate_with_retry(
        self,
        request: ProviderRequest,
        preferred_provider: str | None,
    ) -> ProviderResponse:
        """Generate with automatic retry and fallback."""
        # Build the list of providers to try (preferred first, then others)
        providers_to_try: list[BaseProvider] = []
        if preferred_provider is not None:
            explicit = self.registry.get(preferred_provider)
            if explicit is not None and explicit.available:
                providers_to_try.append(explicit)
        # Add all other available providers as fallbacks
        for p in self.registry.all():
            if p not in providers_to_try and p.available:
                providers_to_try.append(p)
        if not providers_to_try:
            raise RuntimeError("No provider available to serve the request")

        last_error: str = ""
        for provider in providers_to_try:
            for attempt in range(self.max_retries):
                try:
                    self.logger.info(
                        "Generating via %s (attempt %d/%d)",
                        provider.name,
                        attempt + 1,
                        self.max_retries,
                    )
                    response = provider.generate(request)
                    self._track_call(provider, request, response, success=True)
                    return response
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)
                    self.logger.warning(
                        "Provider %s attempt %d failed: %s",
                        provider.name,
                        attempt + 1,
                        exc,
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            self.logger.warning(
                "Provider %s exhausted retries, trying fallback", provider.name
            )
        # All providers failed
        self.error_count += 1
        raise RuntimeError(
            f"All providers failed after {self.max_retries} retries each. "
            f"Last error: {last_error}"
        )

    def _track_call(
        self,
        provider: BaseProvider,
        request: ProviderRequest,
        response: ProviderResponse,
        success: bool,
    ) -> None:
        """Track a call's cost and tokens."""
        self.call_count += 1
        usage = response.usage if hasattr(response, "usage") else {}
        tokens_in = usage.get("prompt", usage.get("input_tokens", 0))
        tokens_out = usage.get("completion", usage.get("output_tokens", 0))
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        cost = (tokens_in * provider.info.cost_per_1k / 1000) + (
            tokens_out * provider.info.cost_per_1k / 1000
        )
        self.total_cost_usd += cost
        self._call_history.append(
            {
                "provider": provider.name,
                "model": response.model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": round(cost, 6),
                "success": success,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def _resolve(self, name: str | None) -> BaseProvider:
        """Resolve the provider to use, honouring explicit name or routing."""
        if name is not None:
            instance = self.router.select(strategy=RoutingStrategy.MANUAL, name=name)
        else:
            instance = self.router.select()
        if instance is None:
            raise RuntimeError("No provider available to serve the request")
        return instance


__all__ = ["DEFAULT_MAX_RETRIES", "DEFAULT_RETRY_DELAY", "ProviderManager"]
