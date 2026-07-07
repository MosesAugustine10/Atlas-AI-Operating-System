"""Atlas MCP connectors.

Every connector inherits :class:`atlas.mcp.base.BaseConnector` and
exposes a deterministic placeholder implementation. Future real
implementations can be slotted in without changing the connector
contract.

Available connectors:

* :class:`FilesystemConnector`
* :class:`GitHubConnector`
* :class:`BrowserConnector`
* :class:`PlaywrightConnector`
* :class:`BlenderConnector`
* :class:`OllamaConnector`
* :class:`WindowsConnector`
* :class:`OpenRouterConnector`
* :class:`SurpacConnector`
* :class:`AutoCADConnector`
* :class:`QGISConnector`
* :class:`PhotoshopConnector`
* :class:`CanvaConnector`
* :class:`GoogleFormsConnector`
* :class:`ExcelConnector`
* :class:`WordConnector`
* :class:`PowerPointConnector`
"""

from __future__ import annotations

from atlas.mcp.connectors.autocad import AutoCADConnector
from atlas.mcp.connectors.blender import BlenderConnector
from atlas.mcp.connectors.browser import BrowserConnector
from atlas.mcp.connectors.canva import CanvaConnector
from atlas.mcp.connectors.excel import ExcelConnector
from atlas.mcp.connectors.filesystem import FilesystemConnector
from atlas.mcp.connectors.github import GitHubConnector
from atlas.mcp.connectors.google_forms import GoogleFormsConnector
from atlas.mcp.connectors.ollama import OllamaConnector
from atlas.mcp.connectors.openrouter import OpenRouterConnector
from atlas.mcp.connectors.photoshop import PhotoshopConnector
from atlas.mcp.connectors.playwright import PlaywrightConnector
from atlas.mcp.connectors.powerpoint import PowerPointConnector
from atlas.mcp.connectors.qgis import QGISConnector
from atlas.mcp.connectors.surpac import SurpacConnector
from atlas.mcp.connectors.windows import WindowsConnector
from atlas.mcp.connectors.word import WordConnector

#: Tuple of every connector class shipped with the MCP layer.
ALL_CONNECTORS: tuple[type, ...] = (
    FilesystemConnector,
    GitHubConnector,
    BrowserConnector,
    PlaywrightConnector,
    BlenderConnector,
    OllamaConnector,
    WindowsConnector,
    OpenRouterConnector,
    SurpacConnector,
    AutoCADConnector,
    QGISConnector,
    PhotoshopConnector,
    CanvaConnector,
    GoogleFormsConnector,
    ExcelConnector,
    WordConnector,
    PowerPointConnector,
)

#: Mapping of connector name -> connector class.
CONNECTOR_MAP: dict[str, type] = {cls.__name__: cls for cls in ALL_CONNECTORS}


def all_connector_classes() -> list[type]:
    """Return every connector class."""
    return list(ALL_CONNECTORS)


def connector_class_for(name: str) -> type | None:
    """Return the connector class for ``name`` or ``None``."""
    return CONNECTOR_MAP.get(name)


def instantiate_all() -> list:
    """Instantiate every connector and return them as a list."""
    return [cls() for cls in ALL_CONNECTORS]


__all__ = [
    "ALL_CONNECTORS",
    "AutoCADConnector",
    "BlenderConnector",
    "BrowserConnector",
    "CONNECTOR_MAP",
    "CanvaConnector",
    "ExcelConnector",
    "FilesystemConnector",
    "GitHubConnector",
    "GoogleFormsConnector",
    "OllamaConnector",
    "OpenRouterConnector",
    "PhotoshopConnector",
    "PlaywrightConnector",
    "PowerPointConnector",
    "QGISConnector",
    "SurpacConnector",
    "WindowsConnector",
    "WordConnector",
    "all_connector_classes",
    "connector_class_for",
    "instantiate_all",
]
