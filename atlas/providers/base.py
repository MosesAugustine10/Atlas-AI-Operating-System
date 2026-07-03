"""Abstract base provider for the Atlas Provider Layer.

The :class:`BaseProvider` defines the contract every LLM provider
implements. Concrete providers (OpenAI, Anthropic, Ollama, etc.) subclass
it. All methods are abstract; placeholders are provided by concrete
classes, not here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from atlas.core.logger import get_logger
from atlas.providers.models import (
    ProviderCapability,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
)


class BaseProvider(ABC):
    """Abstract foundation for every Atlas LLM provider.

    Parameters:
        info: Static :class:`ProviderInfo` describing this provider.
        api_key: Optional API key (unused by placeholders).
    """

    def __init__(self, info: ProviderInfo, api_key: str | None = None) -> None:
        self.info = info
        self.api_key = api_key
        self.logger = get_logger(f"provider.{info.name}")
        self._available = True

    @property
    def name(self) -> str:
        """Return the provider's unique name."""
        return self.info.name

    @property
    def capabilities(self) -> ProviderCapability:
        """Return the provider's declared capabilities."""
        return self.info.capabilities

    @property
    def available(self) -> bool:
        """Return whether this provider is currently available."""
        return self._available

    def set_available(self, value: bool) -> None:
        """Mark the provider as (un)available — used for testing/failover."""
        self._available = value
        self.logger.debug("Availability set to %s", value)

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate a full response for ``request``."""

    @abstractmethod
    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        """Yield incremental response chunks for ``request``."""

    @abstractmethod
    def health(self) -> bool:
        """Return ``True`` if the provider is healthy and reachable."""

    @abstractmethod
    def available_models(self) -> list[str]:
        """Return the list of model identifiers this provider serves."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
