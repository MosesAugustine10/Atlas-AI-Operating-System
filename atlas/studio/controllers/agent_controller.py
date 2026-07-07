"""Agent controller — wraps the Atlas agent registry for the Studio UI.

The :class:`AgentController` adapts an agent registry (a mapping, an
iterable, or any object exposing ``all()`` / ``get()``) into a list of
:class:`~atlas.studio.models.AgentStatus` snapshots. All access is
defensive: a ``None`` registry yields an empty list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.studio.models.studio_models import AgentStatus


class AgentController:
    """ViewModel for the Agents page.

    Parameters:
        registry: Optional agent registry. Accepts any of:

            * a mapping ``{name: agent}``
            * an iterable of agent objects (each with a ``name``)
            * an object exposing ``all()`` / ``names()`` / ``get(name)``
    """

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry
        self._statuses: list[AgentStatus] = []
        self._selected: str | None = None
        self._last_refresh: datetime | None = None
        self.refresh()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def agents(self) -> list[AgentStatus]:
        """Return the cached agent status snapshots (a copy)."""
        return list(self._statuses)

    def refresh(self) -> list[AgentStatus]:
        """Re-read statuses from the wrapped registry and cache them."""
        self._statuses = self._collect()
        self._last_refresh = datetime.now(UTC)
        return list(self._statuses)

    def select(self, name: str) -> AgentStatus | None:
        """Mark ``name`` as the selected agent. Returns its status."""
        self._selected = name
        for status in self._statuses:
            if status.name == name:
                return status
        return None

    def selected(self) -> str | None:
        """Return the currently selected agent name, if any."""
        return self._selected

    @property
    def last_refresh(self) -> datetime | None:
        """When :meth:`refresh` last ran (UTC), or ``None``."""
        return self._last_refresh

    def __len__(self) -> int:
        return len(self._statuses)

    def __repr__(self) -> str:
        return (
            f"<AgentController agents={len(self._statuses)} "
            f"selected={self._selected!r}>"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect(self) -> list[AgentStatus]:
        """Build :class:`AgentStatus` objects for every registered agent."""
        agents = self._iterate_agents()
        statuses: list[AgentStatus] = []
        for agent in agents:
            name = getattr(agent, "name", None) or repr(agent)
            role = getattr(agent, "role", "") or name
            status_text = self._derive_status(agent)
            current_task = getattr(agent, "current_task", "") or ""
            started_at = getattr(agent, "started_at", None)
            duration = _as_float(getattr(agent, "duration", 0.0))
            statuses.append(
                AgentStatus(
                    name=str(name),
                    role=str(role),
                    status=status_text,
                    current_task=str(current_task),
                    started_at=started_at,
                    duration=duration,
                )
            )
        return statuses

    def _iterate_agents(self) -> list[Any]:
        """Return the agent objects from the registry as a list."""
        if self._registry is None:
            return []
        # Object with .all()
        all_method = getattr(self._registry, "all", None)
        if callable(all_method):
            try:
                return list(all_method())
            except Exception:  # noqa: BLE001
                pass
        # Object with .names() + .get()
        names_method = getattr(self._registry, "names", None)
        get_method = getattr(self._registry, "get", None)
        if callable(names_method) and callable(get_method):
            try:
                resolved = []
                for name in names_method():
                    agent = get_method(name)
                    if agent is not None:
                        resolved.append(agent)
                if resolved:
                    return resolved
            except Exception:  # noqa: BLE001
                pass
        # Mapping-like
        try:
            values = list(self._registry.values())
            return values
        except (AttributeError, TypeError):
            pass
        # Iterable of agents
        try:
            return list(self._registry)
        except TypeError:
            return []

    @staticmethod
    def _derive_status(agent: Any) -> str:
        """Derive a status string from common agent attributes."""
        for attr in ("status", "state"):
            value = getattr(agent, attr, None)
            if isinstance(value, str) and value:
                return value
        # If the agent exposes an ``is_running`` flag, prefer that.
        is_running = getattr(agent, "is_running", None)
        if isinstance(is_running, bool):
            return "running" if is_running else "idle"
        return "idle"


def _as_float(value: Any) -> float:
    """Coerce a numeric value to ``float``; return ``0.0`` on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["AgentController"]
