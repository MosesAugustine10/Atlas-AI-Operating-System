"""Workflow definition registry.

The :class:`WorkflowRegistry` is the in-memory catalog of registered
:class:`WorkflowDefinition` objects. Definitions are keyed by their unique
``id``. Registration is explicit so that workflows are only available to the
engine when deliberately added.

The registry is intentionally simple — it has no persistence, no schema
migration, and no version negotiation. Those concerns belong to a future
persistence backend; the registry's job is to provide fast lookup and
duplicate detection.
"""

from __future__ import annotations

from collections.abc import Iterator

from atlas.core.logger import get_logger
from atlas.workflows.models import WorkflowDefinition


class WorkflowRegistry:
    """In-memory catalog of registered workflow definitions.

    Definitions are keyed by their unique ``id``. Registering a duplicate id
    raises :class:`ValueError` to prevent silent shadowing.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}
        self.logger = get_logger("workflow.registry")

    def register(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowRegistry:
        """Register ``definition``. Returns self for chaining.

        Raises:
            ValueError: If a definition with the same id is already registered.
        """
        if definition.id in self._definitions:
            raise ValueError(f"Workflow already registered: {definition.id!r}")
        self._definitions[definition.id] = definition
        self.logger.info("Registered workflow: %s (%s)", definition.id, definition.name)
        return self

    def unregister(self, workflow_id: str) -> WorkflowRegistry:
        """Remove a workflow by id. Returns self for chaining."""
        self._definitions.pop(workflow_id, None)
        return self

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        """Look up a workflow by id, returning ``None`` if not found."""
        return self._definitions.get(workflow_id)

    def contains(self, workflow_id: str) -> bool:
        """Return ``True`` if a workflow with ``workflow_id`` is registered."""
        return workflow_id in self._definitions

    def names(self) -> list[str]:
        """Return a sorted list of all registered workflow ids."""
        return sorted(self._definitions)

    def all(self) -> list[WorkflowDefinition]:
        """Return every registered workflow, ordered by id."""
        return [self._definitions[name] for name in self.names()]

    def __iter__(self) -> Iterator[WorkflowDefinition]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._definitions)

    def __repr__(self) -> str:
        return f"<WorkflowRegistry count={len(self)}>"


__all__ = ["WorkflowRegistry"]
