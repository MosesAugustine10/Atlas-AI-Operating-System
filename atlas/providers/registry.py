"""Provider registry for the Atlas Provider Layer.

The :class:`ProviderRegistry` holds the set of registered
:class:`BaseProvider` instances and supports lookup by name. Registration
is explicit so that providers are only available when deliberately added.
"""

from __future__ import annotations

from collections.abc import Iterator

from atlas.core.logger import get_logger
from atlas.providers.base import BaseProvider


class ProviderRegistry:
    """In-memory catalog of registered providers.

    Providers are keyed by their unique ``name``. Registering a duplicate
    name raises :class:`ValueError` to prevent silent shadowing.
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._default: str | None = None
        self.logger = get_logger("provider.registry")

    def register(
        self, provider: BaseProvider, make_default: bool = False
    ) -> ProviderRegistry:
        """Register a provider. Returns self for chaining.

        Raises:
            ValueError: If a provider with the same name is already registered.
        """
        if provider.name in self._providers:
            raise ValueError(f"Provider already registered: {provider.name!r}")
        self._providers[provider.name] = provider
        if make_default or self._default is None:
            self._default = provider.name
        self.logger.info("Registered provider: %s", provider.name)
        return self

    def unregister(self, name: str) -> ProviderRegistry:
        """Remove a provider by name. Returns self for chaining."""
        self._providers.pop(name, None)
        if self._default == name:
            self._default = next(iter(self._providers), None)
        return self

    def get(self, name: str) -> BaseProvider | None:
        """Look up a provider by name, returning ``None`` if not found."""
        return self._providers.get(name)

    def contains(self, name: str) -> bool:
        """Return ``True`` if a provider with ``name`` is registered."""
        return name in self._providers

    def names(self) -> list[str]:
        """Return a sorted list of all registered provider names."""
        return sorted(self._providers)

    def all(self) -> list[BaseProvider]:
        """Return every registered provider, ordered by name."""
        return [self._providers[name] for name in self.names()]

    def default(self) -> BaseProvider | None:
        """Return the default provider, or ``None`` if registry is empty."""
        if self._default is None:
            return None
        return self._providers.get(self._default)

    def set_default(self, name: str) -> ProviderRegistry:
        """Set the default provider by name.

        Raises:
            KeyError: If ``name`` is not registered.
        """
        if name not in self._providers:
            raise KeyError(f"Provider not registered: {name!r}")
        self._default = name
        return self

    def __iter__(self) -> Iterator[BaseProvider]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._providers)
