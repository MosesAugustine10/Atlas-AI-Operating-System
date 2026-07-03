"""Provider router for the Atlas Provider Layer.

The :class:`ProviderRouter` chooses which provider should serve a given
request based on availability, priority, capabilities, cost, and latency.
It supports four routing strategies:

* ``auto``      — pick the best available provider by priority.
* ``manual``    — use the explicitly named provider.
* ``fallback``  — try a list of providers in order until one succeeds.
* ``round_robin`` — rotate through available providers.

Future implementations may add latency probing and load-aware routing.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator
from itertools import cycle

from atlas.core.logger import get_logger
from atlas.providers.base import BaseProvider
from atlas.providers.models import ProviderCapability, ProviderRequest
from atlas.providers.registry import ProviderRegistry


class RoutingStrategy(enum.StrEnum):
    """Available routing strategies."""

    AUTO = "auto"
    MANUAL = "manual"
    FALLBACK = "fallback"
    ROUND_ROBIN = "round_robin"


class ProviderRouter:
    """Selects the correct provider for a request.

    Parameters:
        registry: The provider registry to route over.
        strategy: Default routing strategy.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        strategy: RoutingStrategy = RoutingStrategy.AUTO,
    ) -> None:
        self.registry = registry
        self.strategy = strategy
        self.logger = get_logger("provider.router")
        self._rr_cycle: Iterator[BaseProvider] | None = None

    def select(
        self,
        request: ProviderRequest | None = None,
        *,
        name: str | None = None,
        strategy: RoutingStrategy | None = None,
        require: ProviderCapability | None = None,
        fallback: list[str] | None = None,
    ) -> BaseProvider | None:
        """Choose a provider honouring the active (or overridden) strategy.

        Returns ``None`` when no suitable provider is available.
        """
        strat = strategy or self.strategy

        if strat is RoutingStrategy.MANUAL:
            if not name:
                raise ValueError("manual strategy requires a provider 'name'")
            return self._select_manual(name, require)

        if strat is RoutingStrategy.FALLBACK:
            return self._select_fallback(fallback or [], require)

        if strat is RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(require)

        return self._select_auto(require)

    def _eligible(
        self, provider: BaseProvider, require: ProviderCapability | None
    ) -> bool:
        """Return ``True`` if a provider is available and meets requirements."""
        if not provider.available:
            return False
        if require is None:
            return True
        cap = provider.capabilities
        return (
            (not require.streaming or cap.streaming)
            and (not require.tools or cap.tools)
            and (not require.images or cap.images)
            and (not require.system_prompt or cap.system_prompt)
        )

    def _select_auto(self, require: ProviderCapability | None) -> BaseProvider | None:
        candidates = [p for p in self.registry.all() if self._eligible(p, require)]
        if not candidates:
            self.logger.warning("No eligible provider for auto routing")
            return None
        candidates.sort(key=lambda p: p.info.priority)
        chosen = candidates[0]
        self.logger.debug("Auto-selected provider: %s", chosen.name)
        return chosen

    def _select_manual(
        self, name: str, require: ProviderCapability | None
    ) -> BaseProvider | None:
        provider = self.registry.get(name)
        if provider is None or not self._eligible(provider, require):
            self.logger.warning("Manual provider unavailable: %s", name)
            return None
        return provider

    def _select_fallback(
        self, names: list[str], require: ProviderCapability | None
    ) -> BaseProvider | None:
        for name in names:
            provider = self.registry.get(name)
            if provider is not None and self._eligible(provider, require):
                self.logger.debug("Fallback selected provider: %s", name)
                return provider
        self.logger.warning("No fallback provider available")
        return None

    def _select_round_robin(
        self, require: ProviderCapability | None
    ) -> BaseProvider | None:
        eligible = [p for p in self.registry.all() if self._eligible(p, require)]
        if not eligible:
            return None
        if self._rr_cycle is None:
            self._rr_cycle = cycle(eligible)
        # Advance to the next eligible provider.
        for _ in range(len(eligible)):
            provider = next(self._rr_cycle)
            if provider in eligible:
                return provider
        return eligible[0]
