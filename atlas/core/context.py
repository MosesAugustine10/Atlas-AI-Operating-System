"""Request context — the single object passed through the system.

Rather than having each component reach out to global state, every stage of
the kernel pipeline receives exactly what it needs through a :class:`Context`.
This keeps the system testable, side-effect-free, and easy to reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from atlas.core.state import State


@dataclass
class Context:
    """Combines memory, knowledge, configuration, and the user request.

    The Context is the canonical bundle carried through every stage of the
    kernel pipeline (Planner → Router → Agent → Tool Manager). Components
    read from and attach artifacts to it as the request progresses.

    Attributes:
        request: The raw user request or goal string.
        config: Atlas configuration mapping (loaded from ``atlas.yaml``).
        memory: Handle to the persistent memory store (placeholder).
        knowledge: Handle to the knowledge / retrieval store (placeholder).
        state: The live execution state for this request.
        user: Optional identifier for the operator issuing the request.
        artifacts: Named outputs accumulated by each stage for downstream use.
    """

    request: str
    config: dict[str, Any] = field(default_factory=dict)
    memory: Any = None
    knowledge: Any = None
    state: State = field(default_factory=State)
    user: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)

    def attach(self, key: str, value: Any) -> None:
        """Attach a named artifact for downstream stages to consume."""
        self.artifacts[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a previously attached artifact."""
        return self.artifacts.get(key, default)
