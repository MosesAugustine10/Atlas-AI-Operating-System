"""Core engine of the Atlas AI Operating System."""

from __future__ import annotations

from atlas.core.atlas import Atlas
from atlas.core.config import Config
from atlas.core.context import Context
from atlas.core.kernel import Kernel
from atlas.core.logger import get_logger
from atlas.core.planner import Planner, Task
from atlas.core.router import AgentDescriptor, Router
from atlas.core.session import Session
from atlas.core.state import ExecutionState, State

__all__ = [
    "AgentDescriptor",
    "Atlas",
    "Config",
    "Context",
    "ExecutionState",
    "Kernel",
    "Planner",
    "Router",
    "Session",
    "State",
    "Task",
    "get_logger",
]
