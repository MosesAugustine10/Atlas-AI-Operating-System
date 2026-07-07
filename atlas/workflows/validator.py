"""Workflow definition validation.

The :class:`WorkflowValidator` checks that a :class:`WorkflowDefinition` is
structurally sound before the engine attempts to execute it. Validation is
performed eagerly so that misconfigured definitions fail fast at registration
time rather than at run time.

Rules enforced:

* Identifiers are non-empty.
* Step IDs are unique within a definition.
* ``depends_on`` references point to existing step IDs.
* The dependency graph is acyclic (no circular waits).
* The action name for every step is non-empty.
* The definition has at least one step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from atlas.core.logger import get_logger
from atlas.workflows.models import WorkflowDefinition, WorkflowStep


@dataclass(frozen=True)
class ValidationError:
    """A single validation finding.

    Attributes:
        code: Stable machine-readable identifier for the rule that failed.
        message: Human-readable explanation.
        path: Dotted path to the offending element (e.g. ``steps[2].id``).
    """

    code: str
    message: str
    path: str = ""


@dataclass
class WorkflowValidationError(Exception):
    """Raised when a workflow definition fails validation.

    Attributes:
        errors: The list of :class:`ValidationError` findings.
    """

    errors: list[ValidationError] = field(default_factory=list)

    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = list(errors)
        super().__init__(self._format())

    def _format(self) -> str:
        lines = [f"{len(self.errors)} validation error(s):"]
        for err in self.errors:
            loc = f" at {err.path}" if err.path else ""
            lines.append(f"  - [{err.code}] {err.message}{loc}")
        return "\n".join(lines)


class WorkflowValidator:
    """Validate :class:`WorkflowDefinition` objects before execution."""

    def __init__(self) -> None:
        self.logger = get_logger("workflow.validator")

    def validate(self, definition: WorkflowDefinition) -> list[ValidationError]:
        """Return a list of validation errors for ``definition``.

        An empty list means the definition is valid.
        """
        errors: list[ValidationError] = []
        errors.extend(self._validate_definition(definition))
        errors.extend(self._validate_steps(definition))
        errors.extend(self._validate_dependencies(definition))
        return errors

    def validate_or_raise(self, definition: WorkflowDefinition) -> None:
        """Validate ``definition`` and raise on failure.

        Raises:
            WorkflowValidationError: If any validation errors are found.
        """
        errors = self.validate(definition)
        if errors:
            self.logger.warning(
                "Workflow %s failed validation: %d error(s)",
                definition.id,
                len(errors),
            )
            raise WorkflowValidationError(errors)

    # ------------------------------------------------------------------
    # Individual rule groups
    # ------------------------------------------------------------------

    def _validate_definition(
        self, definition: WorkflowDefinition
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if not definition.id or not definition.id.strip():
            errors.append(
                ValidationError(
                    code="empty_definition_id",
                    message="Workflow definition id must be non-empty.",
                    path="id",
                )
            )
        if not definition.name or not definition.name.strip():
            errors.append(
                ValidationError(
                    code="empty_definition_name",
                    message="Workflow definition name must be non-empty.",
                    path="name",
                )
            )
        if not definition.steps:
            errors.append(
                ValidationError(
                    code="no_steps",
                    message="Workflow definition must contain at least one step.",
                    path="steps",
                )
            )
        return errors

    def _validate_step(self, index: int, step: WorkflowStep) -> list[ValidationError]:
        errors: list[ValidationError] = []
        path_base = f"steps[{index}]"
        if not step.id or not step.id.strip():
            errors.append(
                ValidationError(
                    code="empty_step_id",
                    message="Step id must be non-empty.",
                    path=f"{path_base}.id",
                )
            )
        if not step.name or not step.name.strip():
            errors.append(
                ValidationError(
                    code="empty_step_name",
                    message=f"Step {step.id!r} has an empty name.",
                    path=f"{path_base}.name",
                )
            )
        if not step.action or not step.action.strip():
            errors.append(
                ValidationError(
                    code="empty_step_action",
                    message=f"Step {step.id!r} has an empty action.",
                    path=f"{path_base}.action",
                )
            )
        return errors

    def _validate_steps(self, definition: WorkflowDefinition) -> list[ValidationError]:
        errors: list[ValidationError] = []
        seen: dict[str, int] = {}
        for index, step in enumerate(definition.steps):
            errors.extend(self._validate_step(index, step))
            if step.id in seen:
                errors.append(
                    ValidationError(
                        code="duplicate_step_id",
                        message=(
                            f"Step id {step.id!r} is duplicated at indices "
                            f"{seen[step.id]} and {index}."
                        ),
                        path=f"steps[{index}].id",
                    )
                )
            else:
                seen[step.id] = index
        return errors

    def _validate_dependencies(
        self, definition: WorkflowDefinition
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        step_ids = {step.id for step in definition.steps}

        # Reference integrity
        for index, step in enumerate(definition.steps):
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        ValidationError(
                            code="unknown_dependency",
                            message=(
                                f"Step {step.id!r} depends on unknown step " f"{dep!r}."
                            ),
                            path=f"steps[{index}].depends_on",
                        )
                    )
                if dep == step.id:
                    errors.append(
                        ValidationError(
                            code="self_dependency",
                            message=f"Step {step.id!r} depends on itself.",
                            path=f"steps[{index}].depends_on",
                        )
                    )

        # Cycle detection (DFS over the dependency graph).
        cycle = self._find_cycle(definition)
        if cycle is not None:
            errors.append(
                ValidationError(
                    code="circular_dependency",
                    message=(
                        "Dependency cycle detected: "
                        + " -> ".join(cycle)
                        + " -> "
                        + cycle[0]
                    ),
                    path="steps.depends_on",
                )
            )
        return errors

    @staticmethod
    def _build_adjacency(
        definition: WorkflowDefinition,
    ) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {step.id: [] for step in definition.steps}
        for step in definition.steps:
            for dep in step.depends_on:
                # Only add forward edges where the dependency exists; missing
                # deps are reported separately by reference-integrity checks.
                if dep in adj:
                    adj[dep].append(step.id)
        return adj

    def _find_cycle(self, definition: WorkflowDefinition) -> list[str] | None:
        """Return a cycle as a list of step IDs, or ``None`` if acyclic."""
        adj = self._build_adjacency(definition)
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {node: white for node in adj}
        parent: dict[str, str | None] = {node: None for node in adj}

        def dfs(node: str) -> list[str] | None:
            color[node] = gray
            for neighbour in adj.get(node, []):
                if color[neighbour] == white:
                    parent[neighbour] = node
                    found = dfs(neighbour)
                    if found is not None:
                        return found
                elif color[neighbour] == gray:
                    # Reconstruct the cycle path.
                    cycle = [neighbour]
                    current: str | None = node
                    while current is not None and current != neighbour:
                        cycle.append(current)
                        current = parent[current]
                    cycle.append(neighbour)
                    cycle.reverse()
                    return cycle
            color[node] = black
            return None

        for node in adj:
            if color[node] == white:
                cycle = dfs(node)
                if cycle is not None:
                    return cycle
        return None


__all__ = [
    "ValidationError",
    "WorkflowValidationError",
    "WorkflowValidator",
]
