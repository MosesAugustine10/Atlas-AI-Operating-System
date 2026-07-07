"""Plugin controller — manages pluggable Studio pages.

The :class:`PluginController` tracks the set of registered
:class:`~atlas.studio.models.PluginInfo` descriptors and their enabled /
disabled state. It is the registry consulted by the navigation model
when building the sidebar (plugins may contribute extra pages).

The controller keeps its own in-memory registry; it does not import or
instantiate the plugin page classes themselves (that is the View
layer's job).
"""

from __future__ import annotations

from dataclasses import replace as _dc_replace
from typing import Any

from atlas.studio.models.studio_models import PluginInfo


class PluginController:
    """In-memory registry of Studio plugins.

    Parameters:
        initial: Optional iterable of :class:`PluginInfo` to seed the
            registry with.
    """

    def __init__(self, initial: Any = None) -> None:
        self._plugins: dict[str, PluginInfo] = {}
        if initial is not None:
            for plugin in initial:
                self.register(plugin)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def plugins(self) -> list[PluginInfo]:
        """Return every registered plugin (a copy of the list)."""
        return list(self._plugins.values())

    def enabled(self) -> list[PluginInfo]:
        """Return only the enabled plugins."""
        return [p for p in self._plugins.values() if p.enabled]

    def disabled(self) -> list[PluginInfo]:
        """Return only the disabled plugins."""
        return [p for p in self._plugins.values() if not p.enabled]

    def get(self, plugin_id: str) -> PluginInfo | None:
        """Return the plugin with ``plugin_id`` or ``None``."""
        return self._plugins.get(plugin_id)

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, plugin_id: object) -> bool:
        return isinstance(plugin_id, str) and plugin_id in self._plugins

    def __repr__(self) -> str:
        return f"<PluginController plugins={len(self._plugins)}>"

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, plugin: PluginInfo) -> PluginController:
        """Register (or replace) a plugin. Returns ``self`` for chaining."""
        if not isinstance(plugin, PluginInfo):
            raise TypeError("plugin must be a PluginInfo")
        self._plugins[plugin.id] = plugin
        return self

    def unregister(self, plugin_id: str) -> bool:
        """Remove a plugin by id. Returns ``True`` if it was registered."""
        return self._plugins.pop(plugin_id, None) is not None

    def enable(self, plugin_id: str) -> PluginInfo | None:
        """Enable ``plugin_id``. Returns the updated plugin or ``None``."""
        return self._set_enabled(plugin_id, True)

    def disable(self, plugin_id: str) -> PluginInfo | None:
        """Disable ``plugin_id``. Returns the updated plugin or ``None``."""
        return self._set_enabled(plugin_id, False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_enabled(self, plugin_id: str, enabled: bool) -> PluginInfo | None:
        """Return a copy of the plugin with ``enabled`` toggled."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return None
        updated = _dc_replace(plugin, enabled=enabled)
        self._plugins[plugin_id] = updated
        return updated


__all__ = ["PluginController"]
