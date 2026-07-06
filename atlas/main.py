"""Command-line entry point for the Atlas AI Operating System.

Usage:

    atlas                  # print banner
    atlas --version        # print version
    atlas launch           # start the Qt desktop application
    atlas launch --headless  # boot controllers without Qt (for testing)
    atlas status           # print wiring status
"""

from __future__ import annotations

import argparse
import collections.abc
import sys


def _print_banner() -> None:
    """Print the Atlas startup banner."""
    print("Atlas AI Operating System")
    print(f"Version {__version__}")
    print("Status: Ready")


def _cmd_launch(argv: list[str]) -> int:
    """Handle ``atlas launch`` — start the Qt desktop application."""
    parser = argparse.ArgumentParser(prog="atlas launch")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="boot controllers without starting the Qt event loop",
    )
    parser.add_argument(
        "--no-pipeline",
        action="store_true",
        help="skip wiring the real AI pipeline (use empty controllers)",
    )
    args = parser.parse_args(argv)

    from atlas.app import AtlasApp, has_qt

    # Use the real pipeline by default so brain.think() actually executes.
    # Pass --no-pipeline for a lightweight boot without subsystem wiring.
    if args.no_pipeline:
        app = AtlasApp()
    else:
        app = AtlasApp.with_pipeline()

    if args.headless or not has_qt():
        # Headless mode — report wiring status
        print("Atlas AI Operating System")
        print(f"  Qt available: {app.is_qt_available()}")
        print(f"  Controllers: {', '.join(app.controller_names())}")
        status = app.status()
        for key, value in status.items():
            if key != "controllers":
                print(f"  {key}: {value}")
        if app.pipeline is not None:
            p_status = app.pipeline.status()
            print(f"  Pipeline providers: {p_status['providers']['registered']}")
            print(f"  Pipeline health: {p_status['providers']['health']}")
        return 0

    # Qt mode — start the event loop
    print("Starting Atlas desktop application…")
    return app.run()


def _cmd_status(argv: list[str]) -> int:
    """Handle ``atlas status`` — print wiring status."""
    from atlas.app import AtlasApp

    app = AtlasApp.with_pipeline()
    status = app.status()
    print("Atlas AI Operating System — Status")
    print(f"  Version: {__version__}")
    for key, value in status.items():
        if key == "controllers":
            print(f"  Controllers: {', '.join(value)}")
        else:
            print(f"  {key}: {value}")
    if app.pipeline is not None:
        p_status = app.pipeline.status()
        print(f"  Pipeline providers: {p_status['providers']['registered']}")
        print(f"  Provider health: {p_status['providers']['health']}")
        print(f"  Brain: {p_status['brain']}")
    return 0


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Run the Atlas CLI.

    Returns the process exit code.
    """
    argv = list(argv) if argv is not None else sys.argv[1:]

    # Top-level parser with subcommands
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Atlas AI Operating System",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"atlas {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    # atlas launch
    launch_parser = subparsers.add_parser(
        "launch",
        help="start the Qt desktop application",
    )
    launch_parser.add_argument(
        "--headless",
        action="store_true",
        help="boot controllers without starting the Qt event loop",
    )

    # atlas status
    subparsers.add_parser(
        "status",
        help="print the app's wiring status",
    )

    args = parser.parse_args(argv)

    if args.command == "launch":
        return _cmd_launch(argv[1:])
    if args.command == "status":
        return _cmd_status(argv[1:])

    # Default: print banner
    _print_banner()
    return 0


# Late import so --version works without importing the whole package
from atlas import __version__  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
