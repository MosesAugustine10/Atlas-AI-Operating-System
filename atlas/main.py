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
    args = parser.parse_args(argv)

    from atlas.app import AtlasApp, has_qt

    app = AtlasApp()
    if args.headless or not has_qt():
        # Headless mode — just report wiring status
        print("Atlas (headless mode)")
        print(f"  Qt available: {app.is_qt_available()}")
        print(f"  Controllers: {', '.join(app.controller_names())}")
        status = app.status()
        for key, value in status.items():
            if key != "controllers":
                print(f"  {key}: {value}")
        return 0

    # Qt mode — start the event loop
    print("Starting Atlas desktop application…")
    return app.run()


def _cmd_status(argv: list[str]) -> int:
    """Handle ``atlas status`` — print wiring status."""
    from atlas.app import AtlasApp

    app = AtlasApp()
    status = app.status()
    print("Atlas wiring status:")
    for key, value in status.items():
        if key == "controllers":
            print(f"  controllers: {', '.join(value)}")
        else:
            print(f"  {key}: {value}")
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
