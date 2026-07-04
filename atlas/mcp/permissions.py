"""Permission system for the Atlas MCP Layer.

This module is a *leaf* in the MCP package dependency graph: it depends
only on the standard library. It defines the canonical permission
levels, a permission registry, and a validator that the
:class:`~atlas.mcp.manager.MCPManager` uses to gate every request.

The permission model is intentionally simple — four built-in levels
plus unlimited custom levels — so future operator-approval flows
(confirmation dialogs, rate limits, time windows) can be layered on
top without changing the contract.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class PermissionLevel(enum.IntEnum):
    """Built-in permission levels (higher = more powerful).

    Attributes:
        NONE: No permissions (default for unknown sessions).
        READ: May invoke read-only capabilities.
        WRITE: May invoke read + write capabilities.
        EXECUTE: May invoke read + write + execute capabilities.
        ADMIN: May invoke every capability, including management.
    """

    NONE = 0
    READ = 10
    WRITE = 20
    EXECUTE = 30
    ADMIN = 100


#: Human-readable names for the built-in levels.
BUILTIN_PERMISSIONS: dict[str, PermissionLevel] = {
    "none": PermissionLevel.NONE,
    "read": PermissionLevel.READ,
    "write": PermissionLevel.WRITE,
    "execute": PermissionLevel.EXECUTE,
    "admin": PermissionLevel.ADMIN,
}


@dataclass(frozen=True)
class PermissionGrant:
    """A permission granted to a session, client, or connector.

    Attributes:
        name: Permission identifier (e.g. ``"read"``, ``"custom.git.push"``).
        level: Numeric privilege level (higher = more powerful).
        scope: Optional scope (e.g. ``"connector:github"``).
        description: Human-readable description.
        metadata: Free-form metadata (expiry, rate limits, etc.).
    """

    name: str
    level: int = 0
    scope: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PermissionRegistry:
    """Registry of known permission levels (built-in + custom).

    The registry maps a permission name (string) to a numeric
    :class:`PermissionLevel`. The :class:`PermissionValidator` uses it
    to translate a session's declared permissions into a single
    effective level.
    """

    def __init__(self) -> None:
        self._levels: dict[str, int] = {
            name: level.value for name, level in BUILTIN_PERMISSIONS.items()
        }

    def register(self, name: str, level: int, description: str = "") -> PermissionGrant:
        """Register a custom permission level.

        Raises:
            ValueError: If ``name`` is empty.
        """
        if not name or not name.strip():
            raise ValueError("Permission name must be non-empty.")
        self._levels[name] = level
        return PermissionGrant(name=name, level=level, description=description)

    def unregister(self, name: str) -> bool:
        """Remove a custom permission. Built-ins cannot be removed."""
        if name in BUILTIN_PERMISSIONS:
            return False
        return self._levels.pop(name, None) is not None

    def get(self, name: str) -> int | None:
        """Return the numeric level for ``name`` or ``None`` if unknown."""
        return self._levels.get(name)

    def contains(self, name: str) -> bool:
        """Return ``True`` if ``name`` is a registered permission."""
        return name in self._levels

    def names(self) -> list[str]:
        """Return a sorted list of every registered permission name."""
        return sorted(self._levels)

    def all(self) -> dict[str, int]:
        """Return a copy of every registered permission."""
        return dict(self._levels)

    def __len__(self) -> int:
        return len(self._levels)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._levels


class PermissionValidator:
    """Validates that a session's permissions satisfy a required level.

    Parameters:
        registry: The :class:`PermissionRegistry` to resolve permission
            names against. Defaults to a fresh registry pre-loaded with
            the built-in permissions.
    """

    def __init__(self, registry: PermissionRegistry | None = None) -> None:
        self.registry = registry if registry is not None else PermissionRegistry()

    def effective_level(self, permissions: list[str]) -> int:
        """Return the highest numeric level among ``permissions``.

        Unknown permissions contribute their raw value via
        :meth:`PermissionRegistry.get` (which returns ``None`` for
        unknowns, so they are ignored).
        """
        if not permissions:
            return PermissionLevel.NONE.value
        levels = [
            self.registry.get(p)
            for p in permissions
            if self.registry.get(p) is not None
        ]
        return max(levels) if levels else PermissionLevel.NONE.value

    def can(
        self,
        permissions: list[str],
        required: str | int | PermissionLevel,
    ) -> bool:
        """Return ``True`` if ``permissions`` satisfy ``required``.

        ``required`` may be a permission name (string), a numeric level,
        or a :class:`PermissionLevel` enum value.
        """
        if isinstance(required, PermissionLevel):
            required_level = required.value
        elif isinstance(required, int):
            required_level = required
        elif isinstance(required, str):
            level = self.registry.get(required)
            required_level = level if level is not None else PermissionLevel.NONE.value
        else:
            return False
        return self.effective_level(permissions) >= required_level

    def check(
        self,
        permissions: list[str],
        required: str | int | PermissionLevel,
    ) -> None:
        """Raise :class:`PermissionDeniedError` if ``permissions`` are insufficient.

        Raises:
            PermissionDeniedError: If the effective level is below
                ``required``.
        """
        if not self.can(permissions, required):
            from atlas.mcp.exceptions import MCPPermissionError

            actual = self.effective_level(permissions)
            required_str = (
                required.name
                if isinstance(required, PermissionLevel)
                else str(required)
            )
            raise MCPPermissionError(
                required=required_str,
                actual=str(actual),
            )

    def __repr__(self) -> str:
        return f"<PermissionValidator registry={len(self.registry)}>"


# Alias for backward-compat / shorter imports.
class PermissionDeniedError(Exception):
    """Lightweight permission-denied error (kept here to avoid a circular
    import with :mod:`atlas.mcp.exceptions` at module load time)."""


__all__ = [
    "BUILTIN_PERMISSIONS",
    "PermissionDeniedError",
    "PermissionGrant",
    "PermissionLevel",
    "PermissionRegistry",
    "PermissionValidator",
]
