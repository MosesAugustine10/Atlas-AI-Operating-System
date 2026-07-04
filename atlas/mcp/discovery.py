"""Connector discovery for the Atlas MCP Layer.

The :class:`ConnectorDiscovery` service finds connectors from a
configurable set of sources:

* **Filesystem** — scan a directory for connector descriptor files
  (placeholder: returns descriptors from a supplied list).
* **Manual registration** — the caller hands the discovery service a
  list of connector descriptors directly.
* **Future network discovery** — placeholder; will discover connectors
  advertised on the local network or via a registry service.

The discovery service returns :class:`~atlas.mcp.base.BaseConnector`
instances (or subclasses thereof). It does not register them — that is
the caller's job (typically the :class:`~atlas.mcp.manager.MCPManager`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from atlas.core.logger import get_logger
from atlas.mcp.base import BaseConnector, PlaceholderConnector
from atlas.mcp.exceptions import MCPDiscoveryError
from atlas.mcp.models import MCPCapability, TransportKind


@dataclass(frozen=True)
class ConnectorDescriptor:
    """A description of a connector discovered by a discovery source.

    Attributes:
        name: Connector name.
        description: Human-readable description.
        module: Python module path that contains the connector class.
        class_name: Name of the connector class within ``module``.
        capabilities: Tuple of capability names the connector exposes.
        transports: Tuple of :class:`TransportKind` values the connector
            supports.
        metadata: Free-form metadata.
    """

    name: str
    description: str = ""
    module: str = ""
    class_name: str = ""
    capabilities: tuple[str, ...] = ()
    transports: tuple[TransportKind, ...] = (TransportKind.IN_PROCESS,)
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectorDiscovery:
    """Discovers MCP connectors from multiple sources.

    Parameters:
        descriptors: Optional initial list of :class:`ConnectorDescriptor`
            items (manual registration source).
    """

    def __init__(
        self,
        descriptors: list[ConnectorDescriptor] | None = None,
    ) -> None:
        self._descriptors: dict[str, ConnectorDescriptor] = {}
        self.logger = get_logger("mcp.discovery")
        for desc in descriptors or []:
            self.register(desc)

    def register(self, descriptor: ConnectorDescriptor) -> ConnectorDiscovery:
        """Manually register a connector descriptor."""
        if not descriptor.name or not descriptor.name.strip():
            raise MCPDiscoveryError("descriptor name must be non-empty")
        self._descriptors[descriptor.name] = descriptor
        self.logger.debug("Registered descriptor: %s", descriptor.name)
        return self

    def unregister(self, name: str) -> bool:
        """Remove a manually-registered descriptor."""
        return self._descriptors.pop(name, None) is not None

    def descriptors(self) -> list[ConnectorDescriptor]:
        """Return every known descriptor."""
        return list(self._descriptors.values())

    def descriptor(self, name: str) -> ConnectorDescriptor | None:
        """Return the descriptor for ``name`` or ``None``."""
        return self._descriptors.get(name)

    def contains(self, name: str) -> bool:
        """Return ``True`` if ``name`` is a known descriptor."""
        return name in self._descriptors

    def names(self) -> list[str]:
        """Return every known descriptor name."""
        return sorted(self._descriptors)

    # ------------------------------------------------------------------
    # Source: filesystem (placeholder)
    # ------------------------------------------------------------------

    def scan_filesystem(self, path: str) -> list[ConnectorDescriptor]:
        """Placeholder filesystem scan.

        A real implementation would walk ``path`` looking for connector
        descriptor files (JSON / YAML). The placeholder simply returns
        the currently-registered descriptors so tests can exercise the
        API without real I/O.
        """
        self.logger.info("Filesystem scan (placeholder) at %s", path)
        return self.descriptors()

    # ------------------------------------------------------------------
    # Source: network (placeholder)
    # ------------------------------------------------------------------

    def scan_network(self, network: str = "local") -> list[ConnectorDescriptor]:
        """Placeholder network scan.

        A real implementation would query a registry service or use
        mDNS / UDP broadcast to discover connectors. The placeholder
        returns an empty list.
        """
        self.logger.info("Network scan (placeholder) on %s", network)
        return []

    # ------------------------------------------------------------------
    # Instantiate
    # ------------------------------------------------------------------

    def instantiate(self, name: str) -> BaseConnector:
        """Instantiate the connector described by ``name``.

        The current implementation returns a
        :class:`~atlas.mcp.base.PlaceholderConnector` configured with
        the descriptor's name, description, and capabilities. A future
        implementation will dynamically import ``module.class_name``.
        """
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            raise MCPDiscoveryError(f"unknown connector descriptor: {name!r}")
        capabilities = tuple(MCPCapability(name=cap) for cap in descriptor.capabilities)
        return PlaceholderConnector(
            name=descriptor.name,
            description=descriptor.description,
            capabilities=capabilities,
            supported_transports=descriptor.transports,
            metadata=dict(descriptor.metadata),
        )

    def instantiate_all(self) -> list[BaseConnector]:
        """Instantiate every known descriptor."""
        return [self.instantiate(name) for name in self.names()]

    def __len__(self) -> int:
        return len(self._descriptors)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._descriptors

    def __repr__(self) -> str:
        return f"<ConnectorDiscovery descriptors={len(self)}>"


__all__ = ["ConnectorDescriptor", "ConnectorDiscovery"]
