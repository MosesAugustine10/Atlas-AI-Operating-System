"""Logging configuration for Atlas."""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the root ``atlas`` logger and return it.

    Safe to call repeatedly; the handler is attached only once.
    """
    global _configured
    logger = logging.getLogger("atlas")
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
        _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the Atlas namespace."""
    configure_logging()
    if not name or name == "atlas":
        return logging.getLogger("atlas")
    return logging.getLogger(f"atlas.{name}")
