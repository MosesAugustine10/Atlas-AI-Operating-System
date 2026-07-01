"""Atlas tool services — domain logic wrappers.

A *service* encapsulates the domain logic for a capability area (GitHub,
filesystem, browser, Blender). Services are injected into tools and adapters;
they hold no knowledge of how they are connected to the outside world.

This package exposes the :class:`BaseService` contract that every domain
service implements.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from atlas.core.logger import get_logger


class BaseService(ABC):
    """Abstract foundation for all Atlas tool services.

    A service owns the *domain logic* for a capability area. It is
    intentionally unaware of transports (MCP, HTTP) — that is the job of an
    adapter. Subclasses implement :meth:`connect`, :meth:`disconnect`, and
    :meth:`is_connected`.

    Parameters:
        name: Unique service identifier (e.g. ``"github"``).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(f"service.{name}")

    @abstractmethod
    def connect(self, **config: Any) -> None:
        """Establish a connection to the backing system."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release any resources held by the service."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` if the service is ready to handle requests."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
