"""Command-line entry point for the Atlas AI Operating System."""

from __future__ import annotations

import argparse
import collections.abc
import sys

from atlas import __version__


def _print_banner() -> None:
    """Print the Atlas startup banner."""
    print("Atlas AI Operating System")
    print(f"Version {__version__}")
    print("Status: Ready")


def main(argv: collections.abc.Sequence[str] | None = None) -> int:
    """Run the Atlas CLI.

    Returns the process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Atlas AI Operating System",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"atlas {__version__}",
    )
    parser.parse_args(argv)
    _print_banner()
    return 0


if __name__ == "__main__":
    sys.exit(main())
