"""Provider manager — high-level API for LLM access.

The :class:`ProviderManager` is the single entry point through which the
Kernel and agents invoke LLMs. It depends only on the
:class:`ProviderRouter`, which in turn selects the right provider. The
manager exposes convenience methods (``generate``, ``chat``, ``complete``,
``health``, ``list_models``) so callers never touch providers directly.
"""

from __future__ import annotations

from atlas.core.logger import get_logger
from atlas.providers.base import BaseProvider
from atlas.providers.models import (
    Message,
    ProviderRequest,
    ProviderResponse,
)
from atlas.providers.registry import ProviderRegistry
from atlas.providers.router import ProviderRouter, RoutingStrategy


class ProviderManager:
    """High-level facade over the provider routing layer.

    Parameters:
        registry: The provider registry. Created empty if omitted.
        router: The provider router. Defaults to a new AUTO router.
    """

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        router: ProviderRouter | None = None,
    ) -> None:
        self.registry = registry or ProviderRegistry()
        self.router = router or ProviderRouter(self.registry)
        self.logger = get_logger("provider.manager")

    def register(
        self, provider: BaseProvider, make_default: bool = False
    ) -> ProviderManager:
        """Register a provider with the manager's registry."""
        self.registry.register(provider, make_default=make_default)
        return self

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

        Routes to the selected provider via the router; raises
        :class:`RuntimeError` if no provider is available.
        """
        request = ProviderRequest(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        chosen = self._resolve(provider)
        self.logger.info("Generating via %s", chosen.name)
        return chosen.generate(request)

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
        chosen = self._resolve(provider)
        return chosen.generate(request)

    def complete(self, prompt: str, **kwargs: object) -> ProviderResponse:
        """Alias for :meth:`generate` (completion-style API)."""
        return self.generate(prompt, **kwargs)  # type: ignore[arg-type]

    def health(self) -> dict[str, bool]:
        """Return a ``{provider_name: healthy}`` map for all providers."""
        return {p.name: p.health() for p in self.registry.all()}

    def list_models(self, provider: str | None = None) -> dict[str, list[str]]:
        """Return available models per provider.

        If ``provider`` is given, returns only that provider's models.
        """
        if provider is not None:
            instance = self.registry.get(provider)
            return {provider: instance.available_models()} if instance else {}
        return {p.name: p.available_models() for p in self.registry.all()}

    def _resolve(self, name: str | None) -> BaseProvider:
        """Resolve the provider to use, honouring explicit name or routing."""
        if name is not None:
            instance = self.router.select(strategy=RoutingStrategy.MANUAL, name=name)
        else:
            instance = self.router.select()
        if instance is None:
            raise RuntimeError("No provider available to serve the request")
        return instance
