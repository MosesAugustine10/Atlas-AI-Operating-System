"""Atlas tool adapters — connectors to external systems.

An *adapter* bridges a :class:`~atlas.tools.services.BaseService` to an
external system or transport (an MCP server, REST API, subprocess, etc.).
Adapters depend on services; services never depend on adapters, keeping the
dependency graph acyclic.

This package exposes the :class:`BaseAdapter` contract that every concrete
adapter implements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger
from atlas.tools.services import BaseService


class BaseAdapter(ABC):
    """Abstract foundation for all Atlas tool adapters.

    An adapter owns the *transport* concerns for a capability area. It wraps
    a :class:`BaseService` and translates between Atlas and the external
    system. Subclasses implement :meth:`open`, :meth:`close`, and
    :meth:`is_open`.

    Parameters:
        service: The domain service this adapter connects to the outside world.
    """

    def __init__(self, service: BaseService) -> None:
        self.service = service
        self.logger = get_logger(f"adapter.{service.name}")

    @abstractmethod
    def open(self, **config: Any) -> None:
        """Open the connection to the external system."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection to the external system."""

    @abstractmethod
    def is_open(self) -> bool:
        """Return ``True`` if the adapter's connection is open."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} service={self.service.name!r}>"
