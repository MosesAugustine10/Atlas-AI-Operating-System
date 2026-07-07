"""Tests for the Atlas engine, CLI banner, and configuration."""

from __future__ import annotations

import atlas
from atlas.core.atlas import Atlas
from atlas.main import main


def test_version_is_defined() -> None:
    assert atlas.__version__ == "0.1.0"


def test_cli_banner(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "Atlas AI Operating System" in captured.out
    assert "Version 0.1.0" in captured.out
    assert "Status: Ready" in captured.out


def test_engine_status_and_banner() -> None:
    engine = Atlas()
    assert engine.status == "Ready"
    assert "Atlas AI Operating System" in engine.banner()
    assert engine.version == "0.1.0"
