"""Reusable workflow templates.

A :class:`WorkflowTemplate` is a parameterised factory for
:class:`WorkflowDefinition` objects. It bundles a builder callable with
metadata (name, description, expected parameters) so that the same workflow
shape can be instantiated many times with different inputs.

The :class:`TemplateRegistry` is the catalog of registered templates. It
behaves like the workflow :class:`WorkflowRegistry`: lookup by id, duplicate
detection, and ordered enumeration.

A handful of built-in templates are provided as convenience constructors:

* :func:`linear_template` — builds a linear chain of N steps.
* :func:`retry_template` — wraps an action in N retry attempts.
* :func:`sequential_template` — builds a workflow from an explicit list of
  ``(step_id, action, params)`` tuples.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from atlas.core.logger import get_logger
from atlas.workflows.models import WorkflowDefinition, WorkflowStep

Builder = Callable[[dict[str, Any]], WorkflowDefinition]


class WorkflowTemplate:
    """A parameterised factory for :class:`WorkflowDefinition` objects.

    Parameters:
        template_id: Unique identifier for this template.
        name: Human-readable name.
        builder: A callable that accepts a parameters dict and returns a
            :class:`WorkflowDefinition`. The builder is responsible for
            constructing steps, inputs, outputs, etc.
        description: Free-form documentation.
        parameters: Optional mapping of parameter name -> description, used
            for documentation and tooling.
    """

    def __init__(
        self,
        template_id: str,
        name: str,
        builder: Builder,
        description: str = "",
        parameters: dict[str, str] | None = None,
    ) -> None:
        if not template_id or not template_id.strip():
            raise ValueError("Template id must be non-empty.")
        if not name or not name.strip():
            raise ValueError("Template name must be non-empty.")
        if builder is None:
            raise ValueError("Template builder must be callable.")
        self.template_id = template_id
        self.name = name
        self.builder = builder
        self.description = description
        self.parameters: dict[str, str] = dict(parameters or {})

    def instantiate(self, **params: Any) -> WorkflowDefinition:
        """Build a :class:`WorkflowDefinition` from this template."""
        return self.builder(dict(params))

    def __repr__(self) -> str:
        return f"<WorkflowTemplate id={self.template_id!r} name={self.name!r}>"


class TemplateRegistry:
    """In-memory catalog of registered workflow templates."""

    def __init__(self) -> None:
        self._templates: dict[str, WorkflowTemplate] = {}
        self.logger = get_logger("workflow.templates")

    def register(self, template: WorkflowTemplate) -> TemplateRegistry:
        """Register ``template``. Returns self for chaining.

        Raises:
            ValueError: If a template with the same id is already registered.
        """
        if template.template_id in self._templates:
            raise ValueError(f"Template already registered: {template.template_id!r}")
        self._templates[template.template_id] = template
        self.logger.info(
            "Registered template: %s (%s)", template.template_id, template.name
        )
        return self

    def unregister(self, template_id: str) -> bool:
        """Remove a template by id. Return ``True`` if it existed."""
        return self._templates.pop(template_id, None) is not None

    def get(self, template_id: str) -> WorkflowTemplate | None:
        """Look up a template by id, returning ``None`` if not found."""
        return self._templates.get(template_id)

    def contains(self, template_id: str) -> bool:
        """Return ``True`` if a template with ``template_id`` is registered."""
        return template_id in self._templates

    def names(self) -> list[str]:
        """Return a sorted list of all registered template ids."""
        return sorted(self._templates)

    def all(self) -> list[WorkflowTemplate]:
        """Return every registered template, ordered by id."""
        return [self._templates[name] for name in self.names()]

    def instantiate(self, template_id: str, **params: Any) -> WorkflowDefinition:
        """Instantiate a registered template by id.

        Raises:
            KeyError: If ``template_id`` is not registered.
        """
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"Template not registered: {template_id!r}")
        return template.instantiate(**params)

    def __iter__(self) -> Iterator[WorkflowTemplate]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._templates)

    def __repr__(self) -> str:
        return f"<TemplateRegistry count={len(self)}>"


# ---------------------------------------------------------------------------
# Built-in template builders
# ---------------------------------------------------------------------------


def linear_template(
    template_id: str,
    name: str,
    actions: list[tuple[str, str]],
    description: str = "",
) -> WorkflowTemplate:
    """Build a template that produces a linear chain of steps.

    Args:
        template_id: Unique template identifier.
        name: Human-readable template name.
        actions: Ordered list of ``(step_id, action)`` tuples. Each step
            depends on the previous one.
        description: Free-form documentation.
    """
    if not actions:
        raise ValueError("linear_template requires at least one action.")

    def builder(params: dict[str, Any]) -> WorkflowDefinition:
        steps: list[WorkflowStep] = []
        previous: str | None = None
        for step_id, action in actions:
            depends = [previous] if previous is not None else []
            steps.append(
                WorkflowStep(
                    id=step_id,
                    name=step_id.replace("_", " ").title(),
                    action=action,
                    params=dict(params),
                    depends_on=depends,
                )
            )
            previous = step_id
        return WorkflowDefinition(
            id=f"{template_id}_instance",
            name=name,
            description=description,
            steps=steps,
            inputs=dict(params),
        )

    return WorkflowTemplate(
        template_id=template_id,
        name=name,
        builder=builder,
        description=description,
    )


def sequential_template(
    template_id: str,
    name: str,
    steps: list[tuple[str, str, dict[str, Any]]],
    description: str = "",
) -> WorkflowTemplate:
    """Build a template from an explicit list of step specs.

    Args:
        template_id: Unique template identifier.
        name: Human-readable template name.
        steps: Ordered list of ``(step_id, action, params)`` tuples. Steps
            do not declare dependencies on each other.
        description: Free-form documentation.
    """
    if not steps:
        raise ValueError("sequential_template requires at least one step.")

    def builder(params: dict[str, Any]) -> WorkflowDefinition:
        wf_steps = [
            WorkflowStep(
                id=step_id,
                name=step_id.replace("_", " ").title(),
                action=action,
                params={**step_params, **params},
            )
            for step_id, action, step_params in steps
        ]
        return WorkflowDefinition(
            id=f"{template_id}_instance",
            name=name,
            description=description,
            steps=wf_steps,
            inputs=dict(params),
        )

    return WorkflowTemplate(
        template_id=template_id,
        name=name,
        builder=builder,
        description=description,
    )


def retry_template(
    template_id: str,
    name: str,
    action: str,
    max_attempts: int = 3,
    description: str = "",
) -> WorkflowTemplate:
    """Build a template that wraps an action in N retry steps.

    Each retry step has the same action but a distinct id; the engine's
    retry machinery (``engine.retry``) is the canonical way to retry a
    failed *run*, but this template is useful when you want retries to be
    expressed as part of the definition itself.

    Args:
        template_id: Unique template identifier.
        name: Human-readable template name.
        action: The action name to attempt.
        max_attempts: Number of retry steps to generate.
        description: Free-form documentation.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1.")

    def builder(params: dict[str, Any]) -> WorkflowDefinition:
        steps = [
            WorkflowStep(
                id=f"attempt_{index + 1}",
                name=f"Attempt {index + 1}",
                action=action,
                params=dict(params),
                optional=(index < max_attempts - 1),
            )
            for index in range(max_attempts)
        ]
        return WorkflowDefinition(
            id=f"{template_id}_instance",
            name=name,
            description=description or f"Retry {action} up to {max_attempts} times.",
            steps=steps,
            inputs=dict(params),
        )

    return WorkflowTemplate(
        template_id=template_id,
        name=name,
        builder=builder,
        description=description,
    )


__all__ = [
    "Builder",
    "TemplateRegistry",
    "WorkflowTemplate",
    "linear_template",
    "retry_template",
    "sequential_template",
]
