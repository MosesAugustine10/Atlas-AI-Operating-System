"""Permission model for the Atlas Tool System.

Permissions gate *whether* a given tool may be invoked by a given caller,
in a given context. They are evaluated before any tool is dispatched, so a
denial never reaches the underlying service or adapter.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Permission(enum.StrEnum):
    """Discrete permissions a caller may hold for a tool.

    The levels are ordered by privilege: a caller holding a higher
    permission implicitly satisfies requests for lower ones.
    """

    DENY = "deny"
    USE = "use"
    CONFIGURE = "configure"
    ADMIN = "admin"


# Ordered from least to most privileged. A granted permission at index *i*
# satisfies any required permission at index *j <= i*.
_PRIVILEGE_ORDER: dict[Permission, int] = {
    Permission.DENY: 0,
    Permission.USE: 1,
    Permission.CONFIGURE: 2,
    Permission.ADMIN: 3,
}


@dataclass
class Permissions:
    """Tracks the permission level granted for each tool.

    Attributes:
        grants: Mapping of tool name to granted :class:`Permission`.
        default: Fallback permission applied when a tool has no explicit grant.
    """

    grants: dict[str, Permission] = field(default_factory=dict)
    default: Permission = Permission.USE

    def grant(self, tool: str, level: Permission) -> Permissions:
        """Grant ``level`` permission for ``tool``. Returns self for chaining."""
        self.grants[tool] = level
        return self

    def revoke(self, tool: str) -> Permissions:
        """Remove any explicit grant for ``tool`` (falls back to default)."""
        self.grants.pop(tool, None)
        return self

    def level(self, tool: str) -> Permission:
        """Return the effective permission level for ``tool``."""
        return self.grants.get(tool, self.default)

    def check(self, tool: str, required: Permission = Permission.USE) -> bool:
        """Return ``True`` if the caller satisfies ``required`` for ``tool``.

        A grant of :attr:`Permission.DENY` always fails. Otherwise the
        granted level must be at least as privileged as ``required``.
        """
        granted = self.level(tool)
        if granted is Permission.DENY:
            return False
        return _PRIVILEGE_ORDER[granted] >= _PRIVILEGE_ORDER[required]
