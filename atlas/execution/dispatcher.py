"""Execution dispatcher — resolves tasks to agents, providers, tools, workflows.

The :class:`ExecutionDispatcher` is the second stage of the execution
pipeline. It receives an :class:`atlas.execution.models.ExecutionPlan`
and, for each :class:`atlas.execution.models.ExecutionTask`, decides
*which* agent / provider / tool / workflow should handle it.

The dispatcher is **capability-based**: it never hardcodes agent names
or provider names. Instead, it queries injected registries (any object
with ``all()``, ``names()``, or ``get(name)``) and picks the first
candidate whose declared capabilities satisfy the task's ``kind`` and
``action``.

When no registry is injected (or no candidate matches), the dispatcher
falls back to a deterministic default and records the choice in the
task's metadata. This keeps the engine fully functional offline with
zero external dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from atlas.core.logger import get_logger
from atlas.execution.models import ExecutionPlan, ExecutionTask, TaskKind
from atlas.execution.strategy import ExecutionStrategy

# ---------------------------------------------------------------------------
# Resolution result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskResolution:
    """The dispatcher's decision for a single task.

    Attributes:
        task_id: The task this resolution applies to.
        agent: Name of the agent selected (or ``None``).
        provider: Name of the provider selected (or ``None``).
        tool: Name of the tool selected (or ``None``).
        workflow: ID of the workflow selected (or ``None``).
        skill: Name of the skill selected (or ``None``).
        action: The action string the executor should dispatch.
        params: Merged parameters (task params + resolution overrides).
        reason: Human-readable explanation of the choice.
    """

    task_id: str
    agent: str | None = None
    provider: str | None = None
    tool: str | None = None
    workflow: str | None = None
    skill: str | None = None
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class DispatchResult:
    """The dispatcher's decision for an entire plan.

    Attributes:
        plan_id: The plan that was dispatched.
        resolutions: Mapping of task ID -> :class:`TaskResolution`.
        strategy: The :class:`ExecutionStrategy` to use.
    """

    plan_id: str
    resolutions: dict[str, TaskResolution] = field(default_factory=dict)
    strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC


# ---------------------------------------------------------------------------
# Capability mapping
# ---------------------------------------------------------------------------


#: Default capability mapping from :class:`TaskKind` to the capability
#: tags the dispatcher looks for in agents, providers, tools, and
#: workflows. An empty list means "any candidate is acceptable".
_DEFAULT_CAPABILITY_TAGS: dict[TaskKind, tuple[str, ...]] = {
    TaskKind.RESEARCH: ("research", "search", "knowledge"),
    TaskKind.GENERATE: ("generate", "code", "text", "creative"),
    TaskKind.TEST: ("test", "validate", "run"),
    TaskKind.DEPLOY: ("deploy", "publish", "release"),
    TaskKind.GIT: ("git", "vcs", "commit"),
    TaskKind.REVIEW: ("review", "reflect", "evaluate"),
    TaskKind.CUSTOM: (),
}


# ---------------------------------------------------------------------------
# Base and concrete dispatcher
# ---------------------------------------------------------------------------


class BaseDispatcher(ABC):
    """Abstract contract for execution dispatchers."""

    @abstractmethod
    def dispatch(
        self,
        plan: ExecutionPlan,
        strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC,
    ) -> DispatchResult:
        """Resolve every task in ``plan`` to a :class:`TaskResolution`."""


class ExecutionDispatcher(BaseDispatcher):
    """Capability-based dispatcher.

    Parameters:
        agents: Optional agent registry. Any object with ``all()``,
            ``names()``, or ``get(name)`` is accepted.
        providers: Optional provider registry.
        tools: Optional tool registry.
        workflows: Optional workflow registry.
        skills: Optional skill registry.
        capability_tags: Optional override for the default
            :data:`_DEFAULT_CAPABILITY_TAGS` mapping.
    """

    def __init__(
        self,
        agents: Any = None,
        providers: Any = None,
        tools: Any = None,
        workflows: Any = None,
        skills: Any = None,
        capability_tags: dict[TaskKind, tuple[str, ...]] | None = None,
    ) -> None:
        self.agents = agents
        self.providers = providers
        self.tools = tools
        self.workflows = workflows
        self.skills = skills
        self.capability_tags = (
            capability_tags if capability_tags is not None else _DEFAULT_CAPABILITY_TAGS
        )
        self.logger = get_logger("execution.dispatcher")

    def dispatch(
        self,
        plan: ExecutionPlan,
        strategy: ExecutionStrategy = ExecutionStrategy.AUTOMATIC,
    ) -> DispatchResult:
        """Resolve every task in ``plan`` to a :class:`TaskResolution`."""
        resolutions: dict[str, TaskResolution] = {}
        for task in plan.tasks:
            resolutions[task.id] = self._resolve_task(task)
        result = DispatchResult(
            plan_id=plan.id,
            resolutions=resolutions,
            strategy=strategy,
        )
        self.logger.info(
            "Dispatched %d task(s) for plan %s (strategy=%s)",
            len(resolutions),
            plan.id,
            strategy.value,
        )
        return result

    def resolve(self, task: ExecutionTask) -> TaskResolution:
        """Resolve a single task (public convenience wrapper)."""
        return self._resolve_task(task)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_task(self, task: ExecutionTask) -> TaskResolution:
        """Pick an agent / provider / tool / workflow for ``task``."""
        tags = self.capability_tags.get(task.kind, ())
        agent = self._select_agent(task, tags)
        provider = self._select_provider(task, tags)
        tool = self._select_tool(task, tags)
        workflow = self._select_workflow(task, tags)
        skill = self._select_skill(task, tags)
        action = task.action or task.kind.value
        params = dict(task.params)
        reason = self._explain(task, agent, provider, tool, workflow, skill)
        return TaskResolution(
            task_id=task.id,
            agent=agent,
            provider=provider,
            tool=tool,
            workflow=workflow,
            skill=skill,
            action=action,
            params=params,
            reason=reason,
        )

    def _select_agent(self, task: ExecutionTask, tags: tuple[str, ...]) -> str | None:
        """Pick an agent whose capabilities include any of ``tags``."""
        candidate = self._select_from_registry(self.agents, tags)
        if candidate is not None:
            return candidate
        # Deterministic fallback based on task kind.
        return self._default_agent(task)

    def _select_provider(
        self, task: ExecutionTask, tags: tuple[str, ...]
    ) -> str | None:
        """Pick a provider whose capabilities include any of ``tags``."""
        candidate = self._select_from_registry(self.providers, tags)
        if candidate is not None:
            return candidate
        return self._default_provider(task)

    def _select_tool(self, task: ExecutionTask, tags: tuple[str, ...]) -> str | None:
        """Pick a tool whose name or description matches any of ``tags``."""
        candidate = self._select_from_registry(self.tools, tags)
        if candidate is not None:
            return candidate
        return self._default_tool(task)

    def _select_workflow(
        self, task: ExecutionTask, tags: tuple[str, ...]
    ) -> str | None:
        """Pick a workflow whose name matches any of ``tags``."""
        candidate = self._select_from_registry(self.workflows, tags)
        return candidate  # workflows have no deterministic fallback

    def _select_skill(self, task: ExecutionTask, tags: tuple[str, ...]) -> str | None:
        """Pick a skill whose name matches any of ``tags``."""
        candidate = self._select_from_registry(self.skills, tags)
        return candidate

    def _select_from_registry(self, registry: Any, tags: tuple[str, ...]) -> str | None:
        """Return the name of the first registry item matching ``tags``.

        A registry is any object with ``all()``, ``names()``, or
        ``get(name)``. Items are matched by looking for any of ``tags``
        in their ``name``, ``description``, ``capabilities``, or
        ``role`` attributes (case-insensitive).
        """
        if registry is None or not tags:
            return None
        items = self._registry_items(registry)
        for item in items:
            haystack = self._item_haystack(item)
            if any(tag.lower() in haystack for tag in tags):
                return self._item_name(item)
        return None

    @staticmethod
    def _registry_items(registry: Any) -> list[Any]:
        """Return every item in ``registry`` as a list."""
        all_fn = getattr(registry, "all", None)
        if callable(all_fn):
            try:
                return list(all_fn())
            except Exception:  # noqa: BLE001
                pass
        names_fn = getattr(registry, "names", None)
        if callable(names_fn):
            try:
                names = list(names_fn())
                get_fn = getattr(registry, "get", None)
                if callable(get_fn):
                    return [get_fn(name) for name in names if get_fn(name) is not None]
            except Exception:  # noqa: BLE001
                pass
        return []

    @staticmethod
    def _item_name(item: Any) -> str:
        """Return the name of a registry item."""
        return str(
            getattr(item, "name", None) or getattr(item, "id", None) or repr(item)
        )

    @staticmethod
    def _item_haystack(item: Any) -> str:
        """Return a lowercase haystack string for tag matching."""
        parts: list[str] = []
        for attr in ("name", "description", "role"):
            value = getattr(item, attr, None)
            if isinstance(value, str):
                parts.append(value.lower())
        caps = getattr(item, "capabilities", None)
        if isinstance(caps, (list, tuple)):
            parts.extend(str(c).lower() for c in caps)
        elif isinstance(caps, str):
            parts.append(caps.lower())
        return " ".join(parts)

    @staticmethod
    def _default_agent(task: ExecutionTask) -> str | None:
        """Deterministic default agent based on task kind."""
        defaults = {
            TaskKind.RESEARCH: "researcher",
            TaskKind.GENERATE: "coder",
            TaskKind.TEST: "tester",
            TaskKind.DEPLOY: "deployer",
            TaskKind.GIT: "git_agent",
            TaskKind.REVIEW: "reviewer",
            TaskKind.CUSTOM: "default_agent",
        }
        return defaults.get(task.kind)

    @staticmethod
    def _default_provider(task: ExecutionTask) -> str | None:
        """Deterministic default provider based on task kind."""
        defaults = {
            TaskKind.RESEARCH: "zai",
            TaskKind.GENERATE: "zai",
            TaskKind.TEST: "local",
            TaskKind.DEPLOY: "local",
            TaskKind.GIT: "local",
            TaskKind.REVIEW: "zai",
            TaskKind.CUSTOM: "zai",
        }
        return defaults.get(task.kind)

    @staticmethod
    def _default_tool(task: ExecutionTask) -> str | None:
        """Deterministic default tool based on task kind."""
        defaults = {
            TaskKind.GIT: "git",
            TaskKind.TEST: "test_runner",
            TaskKind.DEPLOY: "deployer",
        }
        return defaults.get(task.kind)

    @staticmethod
    def _explain(
        task: ExecutionTask,
        agent: str | None,
        provider: str | None,
        tool: str | None,
        workflow: str | None,
        skill: str | None,
    ) -> str:
        """Produce a human-readable explanation of the resolution."""
        parts: list[str] = []
        if agent:
            parts.append(f"agent={agent}")
        if provider:
            parts.append(f"provider={provider}")
        if tool:
            parts.append(f"tool={tool}")
        if workflow:
            parts.append(f"workflow={workflow}")
        if skill:
            parts.append(f"skill={skill}")
        if not parts:
            parts.append("no_registry_match_defaulted")
        return f"task={task.id} kind={task.kind.value} " + " ".join(parts)


__all__ = [
    "BaseDispatcher",
    "DispatchResult",
    "ExecutionDispatcher",
    "TaskResolution",
]
