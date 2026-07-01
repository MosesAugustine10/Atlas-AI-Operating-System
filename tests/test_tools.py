"""Tests for the Atlas Tool Layer.

These tests exercise the registry, manager, result, and permissions
components using a small concrete ``EchoTool`` to avoid depending on any
real service or adapter.
"""

from __future__ import annotations

from typing import Any

import pytest

from atlas.tools.base import BaseTool
from atlas.tools.manager import ToolManager
from atlas.tools.permissions import Permission, Permissions
from atlas.tools.registry import ToolRegistry
from atlas.tools.result import ToolResult

# ---------------------------------------------------------------------------
# Test fixture: a minimal concrete tool
# ---------------------------------------------------------------------------


class EchoTool(BaseTool):
    """A trivial tool that echoes its arguments back as the output."""

    def __init__(self) -> None:
        super().__init__(name="echo", description="Echo back the inputs")

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult.ok(output=kwargs)


class BoomTool(BaseTool):
    """A tool that always raises, to exercise manager error handling."""

    def __init__(self) -> None:
        super().__init__(name="boom")

    def execute(self, **kwargs: Any) -> ToolResult:  # noqa: ARG002
        raise RuntimeError("deliberate failure")


# ---------------------------------------------------------------------------
# ToolResult construction
# ---------------------------------------------------------------------------


def test_result_ok_construction() -> None:
    result = ToolResult.ok(output={"x": 1}, latency_ms=12)
    assert result.is_ok()
    assert not result.is_error()
    assert result.output == {"x": 1}
    assert result.metadata == {"latency_ms": 12}
    assert result.error is None


def test_result_fail_construction() -> None:
    result = ToolResult.fail("something broke", code=500)
    assert result.is_error()
    assert not result.is_ok()
    assert result.error == "something broke"
    assert result.metadata == {"code": 500}
    assert result.output is None


def test_result_default_metadata_is_isolated() -> None:
    """Each result must get its own metadata dict (not a shared default)."""
    a = ToolResult(success=True)
    b = ToolResult(success=True)
    a.metadata["k"] = "v"
    assert "k" not in b.metadata


# ---------------------------------------------------------------------------
# Registry: registration, lookup, duplicate handling
# ---------------------------------------------------------------------------


def test_registry_register_and_lookup() -> None:
    registry = ToolRegistry()
    tool = EchoTool()
    assert registry.contains("echo") is False

    registry.register(tool)
    assert registry.contains("echo") is True
    assert registry.get("echo") is tool
    assert len(registry) == 1


def test_registry_duplicate_raises() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(EchoTool())


def test_registry_unregister() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.contains("echo") is True

    registry.unregister("echo")
    assert registry.contains("echo") is False
    assert registry.get("echo") is None
    assert len(registry) == 0


def test_registry_names_sorted_and_iterable() -> None:
    registry = ToolRegistry()
    boom = BoomTool()
    echo = EchoTool()
    # Register out of order to verify sorting.
    registry.register(boom)
    registry.register(echo)
    assert registry.names() == ["boom", "echo"]
    assert [t.name for t in registry] == ["boom", "echo"]


def test_registry_get_unknown_returns_none() -> None:
    registry = ToolRegistry()
    assert registry.get("does-not-exist") is None


# ---------------------------------------------------------------------------
# Permissions: grant, check, deny
# ---------------------------------------------------------------------------


def test_permissions_default_allows_use() -> None:
    perms = Permissions()
    assert perms.check("any_tool") is True
    assert perms.check("any_tool", Permission.USE) is True
    assert perms.check("any_tool", Permission.CONFIGURE) is False


def test_permissions_grant_satisfies_lower_levels() -> None:
    perms = Permissions().grant("github", Permission.ADMIN)
    assert perms.check("github", Permission.USE) is True
    assert perms.check("github", Permission.CONFIGURE) is True
    assert perms.check("github", Permission.ADMIN) is True


def test_permissions_deny_blocks_everything() -> None:
    perms = Permissions().grant("dangerous", Permission.DENY)
    assert perms.check("dangerous", Permission.USE) is False
    assert perms.check("dangerous") is False


def test_permissions_revoke_falls_back_to_default() -> None:
    perms = Permissions(default=Permission.USE)
    perms.grant("github", Permission.ADMIN)
    assert perms.level("github") is Permission.ADMIN
    perms.revoke("github")
    assert perms.level("github") is Permission.USE


# ---------------------------------------------------------------------------
# ToolManager: execution flow, permission gating, error capture
# ---------------------------------------------------------------------------


def test_manager_execute_success() -> None:
    manager = ToolManager()
    manager.register(EchoTool())
    result = manager.execute("echo", message="hi")
    assert result.is_ok()
    assert result.output == {"message": "hi"}


def test_manager_execute_unknown_tool() -> None:
    manager = ToolManager()
    result = manager.execute("missing")
    assert result.is_error()
    assert "Unknown tool" in (result.error or "")


def test_manager_execute_permission_denied() -> None:
    manager = ToolManager()
    manager.register(EchoTool())
    manager.grant("echo", Permission.DENY)
    result = manager.execute("echo", message="hi")
    assert result.is_error()
    assert "Permission denied" in (result.error or "")


def test_manager_execute_captures_exception() -> None:
    manager = ToolManager()
    manager.register(BoomTool())
    result = manager.execute("boom")
    assert result.is_error()
    assert "RuntimeError" in (result.error or "")
    assert "deliberate failure" in (result.error or "")


def test_manager_check_respects_tool_required_permission() -> None:
    """A tool requiring CONFIGURE must not run with only USE permission."""
    manager = ToolManager()
    # Build a tool that requires CONFIGURE.
    secure = EchoTool()
    secure.name = "secure"
    secure.required_permission = Permission.CONFIGURE
    manager.register(secure)

    # Default permission is USE -> denied.
    assert manager.check("secure") is False
    denied = manager.execute("secure")
    assert denied.is_error()

    # Grant CONFIGURE -> allowed.
    manager.grant("secure", Permission.CONFIGURE)
    assert manager.check("secure") is True
    allowed = manager.execute("secure", x=1)
    assert allowed.is_ok()
