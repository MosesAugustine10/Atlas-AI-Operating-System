"""The Atlas engine — the core runtime of the operating system."""

from __future__ import annotations

from atlas import __version__
from atlas.core.config import Config
from atlas.core.logger import get_logger


class Atlas:
    """The Atlas AI Operating System engine.

    Holds configuration and logging, and serves as the central runtime
    through which agents, memory, knowledge, workflows, and tools are
    coordinated.
    """

    def __init__(self, config_path: str | None = None) -> None:
        self.logger = get_logger("atlas")
        self.config = Config(config_path)
        self.version = __version__
        self.logger.info("Atlas engine initialised (v%s)", self.version)

    @property
    def status(self) -> str:
        """Return the current engine status."""
        return "Ready"

    def banner(self) -> str:
        """Return the startup banner text."""
        return (
            f"Atlas AI Operating System\n"
            f"Version {self.version}\n"
            f"Status: {self.status}"
        )
