"""Provider controller — wraps the ProviderManager for the Studio UI.

The :class:`ProviderController` adapts the
:class:`~atlas.providers.manager.ProviderManager` (or any duck-typed
equivalent) into a list of
:class:`~atlas.studio.models.ProviderStatus` snapshots suitable for the
Providers page. All access is defensive: a ``None`` manager yields an
empty list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.studio.models.studio_models import ProviderStatus


class ProviderController:
    """ViewModel for the Providers page.

    Parameters:
        manager: Optional :class:`~atlas.providers.manager.ProviderManager`
            -like object. Expected duck-typed surface:
            ``registry.all()`` / ``registry.names()`` /
            ``list_models()`` / ``health()``. Any subset works.
    """

    def __init__(self, manager: Any = None) -> None:
        self._manager = manager
        self._statuses: list[ProviderStatus] = []
        self._selected: str | None = None
        self._last_refresh: datetime | None = None
        self.refresh()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def providers(self) -> list[ProviderStatus]:
        """Return the cached provider status snapshots (a copy)."""
        return list(self._statuses)

    def refresh(self) -> list[ProviderStatus]:
        """Re-read statuses from the wrapped manager and cache them.

        Returns the freshly cached list. When no manager is wired the
        cache is emptied.
        """
        self._statuses = self._collect()
        self._last_refresh = datetime.now(UTC)
        return list(self._statuses)

    def select(self, name: str) -> ProviderStatus | None:
        """Mark ``name`` as the selected provider. Returns its status."""
        self._selected = name
        for status in self._statuses:
            if status.name == name:
                return status
        return None

    def selected(self) -> str | None:
        """Return the currently selected provider name, if any."""
        return self._selected

    def health(self) -> dict[str, bool]:
        """Return a ``{provider_name: healthy}`` map from the manager."""
        if self._manager is None:
            return {}
        method = getattr(self._manager, "health", None)
        if callable(method):
            try:
                result = method()
            except Exception:  # noqa: BLE001
                return {}
            if isinstance(result, dict):
                return {str(k): bool(v) for k, v in result.items()}
        return {}

    @property
    def last_refresh(self) -> datetime | None:
        """When :meth:`refresh` last ran (UTC), or ``None``."""
        return self._last_refresh

    def __len__(self) -> int:
        return len(self._statuses)

    def __repr__(self) -> str:
        return (
            f"<ProviderController providers={len(self._statuses)} "
            f"selected={self._selected!r}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect(self) -> list[ProviderStatus]:
        """Build :class:`ProviderStatus` objects for every provider."""
        if self._manager is None:
            return []
        registry = getattr(self._manager, "registry", None)
        if registry is None:
            return []
        all_providers = _call(registry, "all", default=[])
        models_map = self._models_map()
        health_map = self.health()
        statuses: list[ProviderStatus] = []
        for index, provider in enumerate(all_providers):
            name = getattr(provider, "name", None) or str(provider)
            display = _display_name(provider, name)
            available = bool(
                getattr(provider, "available", False) or health_map.get(name, False)
            )
            models = models_map.get(name, []) or _call(
                provider, "available_models", default=[]
            )
            statuses.append(
                ProviderStatus(
                    name=name,
                    display_name=display,
                    available=available,
                    models=list(models),
                    latency_ms=_latency(provider),
                    cost_per_1k=_cost_per_1k(provider),
                    priority=index,
                )
            )
        return statuses

    def _models_map(self) -> dict[str, list[str]]:
        """Return a ``{provider_name: [model, ...]}`` map if available."""
        if self._manager is None:
            return {}
        method = getattr(self._manager, "list_models", None)
        if not callable(method):
            return {}
        try:
            result = method()
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(result, dict):
            return {}
        return {str(k): list(v) for k, v in result.items()}


def _call(obj: Any, method_name: str, default: Any) -> Any:
    """Call ``obj.method_name()`` and return the result, or ``default``."""
    method = getattr(obj, method_name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:  # noqa: BLE001
        return default


def _display_name(provider: Any, fallback: str) -> str:
    """Best-effort human-readable name for a provider."""
    info = getattr(provider, "info", None)
    if info is not None:
        for attr in ("display_name", "title", "label", "name"):
            value = getattr(info, attr, None)
            if isinstance(value, str) and value:
                return value
    return str(fallback).replace("_", " ").title()


def _latency(provider: Any) -> float:
    """Return a cached latency if the provider exposes one."""
    for attr in ("latency_ms", "last_latency_ms"):
        value = getattr(provider, attr, None)
        if isinstance(value, int | float):
            return float(value)
    return 0.0


def _cost_per_1k(provider: Any) -> float:
    """Return a cost-per-1k estimate if the provider exposes one."""
    info = getattr(provider, "info", None)
    if info is not None:
        value = getattr(info, "cost_per_1k", None)
        if isinstance(value, int | float):
            return float(value)
    value = getattr(provider, "cost_per_1k", None)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


__all__ = ["ProviderController"]
