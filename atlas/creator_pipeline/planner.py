"""Pipeline planner — converts a creative goal into a stage graph.

The :class:`PipelinePlanner` takes a high-level goal (e.g. "Create a
YouTube documentary about SpaceX") and produces a
:class:`~atlas.creator_pipeline.models.PipelineProject` with a
dependency-ordered set of :class:`PipelineStage` instances.

The planner is pure-Python — it never imports Brain or any Atlas
subsystem. The stage graph is deterministic and can be customised
via an injected ``plan_fn`` callback.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from atlas.creator_pipeline.models import (
    PipelineProject,
    PipelineStage,
    ProjectStatus,
    StageKind,
    StageStatus,
    _new_id,
)

# ---------------------------------------------------------------------------
# Default stage graph
# ---------------------------------------------------------------------------


#: The default 18-stage pipeline in dependency order.
#: Each entry is (stage_kind, display_name, dependency_stage_kinds).
DEFAULT_STAGES: list[tuple[str, str, tuple[str, ...]]] = [
    (StageKind.RESEARCH.value, "Research", ()),
    (StageKind.FACT_CHECK.value, "Fact Verification", (StageKind.RESEARCH.value,)),
    (StageKind.SCRIPT.value, "Script Writing", (StageKind.FACT_CHECK.value,)),
    (StageKind.STORYBOARD.value, "Storyboard Generation", (StageKind.SCRIPT.value,)),
    (StageKind.SHOT_PLAN.value, "Shot Planning", (StageKind.STORYBOARD.value,)),
    (StageKind.PROMPT_GEN.value, "Prompt Generation", (StageKind.SHOT_PLAN.value,)),
    (StageKind.IMAGE_GEN.value, "Image Generation", (StageKind.PROMPT_GEN.value,)),
    (StageKind.VIDEO_GEN.value, "Video Generation", (StageKind.PROMPT_GEN.value,)),
    (StageKind.VOICE_SYNTH.value, "Voice Synthesis", (StageKind.SCRIPT.value,)),
    (StageKind.MUSIC_SELECT.value, "Music Selection", (StageKind.SCRIPT.value,)),
    (
        StageKind.SUBTITLE_GEN.value,
        "Subtitle Generation",
        (StageKind.VOICE_SYNTH.value,),
    ),
    (
        StageKind.TIMELINE_ASSEMBLY.value,
        "Timeline Assembly",
        (
            StageKind.IMAGE_GEN.value,
            StageKind.VIDEO_GEN.value,
            StageKind.VOICE_SYNTH.value,
            StageKind.MUSIC_SELECT.value,
            StageKind.SUBTITLE_GEN.value,
        ),
    ),
    (StageKind.RENDER.value, "Rendering", (StageKind.TIMELINE_ASSEMBLY.value,)),
    (StageKind.QUALITY_REVIEW.value, "Quality Review", (StageKind.RENDER.value,)),
    (
        StageKind.THUMBNAIL_GEN.value,
        "Thumbnail Generation",
        (StageKind.QUALITY_REVIEW.value,),
    ),
    (
        StageKind.METADATA_GEN.value,
        "Metadata Generation",
        (StageKind.QUALITY_REVIEW.value,),
    ),
    (StageKind.SEO_OPTIMIZE.value, "SEO Optimization", (StageKind.METADATA_GEN.value,)),
    (StageKind.PACKAGE.value, "Upload Package", (StageKind.SEO_OPTIMIZE.value,)),
]


class PipelinePlanner:
    """Converts a creative goal into a stage graph.

    Parameters:
        plan_fn: Optional callback invoked with ``(goal, **kwargs)``
            and returning a list of stage dicts. When omitted, the
            default 18-stage graph is used.
    """

    def __init__(
        self,
        plan_fn: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        self._plan_fn = plan_fn

    def plan(
        self,
        goal: str,
        title: str = "",
        target_platforms: tuple[str, ...] = (),
    ) -> PipelineProject:
        """Plan a pipeline project for ``goal``.

        Returns a :class:`PipelineProject` with stages in dependency
        order. The project starts in ``PLANNED`` status.
        """
        if not goal.strip():
            raise ValueError("goal must be non-empty")
        if self._plan_fn is not None:
            raw_stages = self._plan_fn(goal=goal, title=title)
        else:
            raw_stages = [
                {"kind": kind, "name": name, "dependencies": deps}
                for kind, name, deps in DEFAULT_STAGES
            ]
        stages = self._build_stages(raw_stages)
        return PipelineProject(
            id=_new_id("project"),
            goal=goal,
            title=title or goal[:60],
            status=ProjectStatus.PLANNED.value,
            stages=tuple(stages),
            target_platforms=target_platforms or ("youtube",),
        )

    # ------------------------------------------------------------------
    # Stage graph construction
    # ------------------------------------------------------------------

    def _build_stages(
        self,
        raw_stages: list[dict[str, Any]],
    ) -> list[PipelineStage]:
        """Build :class:`PipelineStage` instances from raw dicts.

        Dependencies are resolved from stage-kind strings to stage ids.
        """
        # First pass: create stages with kind-based ids
        kind_to_id: dict[str, str] = {}
        stages: list[PipelineStage] = []
        for i, raw in enumerate(raw_stages):
            kind = raw.get("kind", StageKind.RESEARCH.value)
            name = raw.get("name", kind.replace("_", " ").title())
            stage_id = _new_id("stage")
            kind_to_id[kind] = stage_id
            stage = PipelineStage(
                id=stage_id,
                kind=kind,
                name=name,
                status=StageStatus.PENDING.value,
                order=i,
                dependencies=(),  # filled in second pass
            )
            stages.append(stage)

        # Second pass: resolve dependencies from kind to stage id
        resolved: list[PipelineStage] = []
        for i, raw in enumerate(raw_stages):
            dep_kinds: tuple[str, ...] = tuple(raw.get("dependencies", ()))
            dep_ids = tuple(kind_to_id[dk] for dk in dep_kinds if dk in kind_to_id)
            # Replace the stage with resolved dependencies
            import dataclasses

            resolved.append(dataclasses.replace(stages[i], dependencies=dep_ids))
        return resolved

    # ------------------------------------------------------------------
    # Stage queries
    # ------------------------------------------------------------------

    @staticmethod
    def stage_order(project: PipelineProject) -> list[PipelineStage]:
        """Return stages in topological (dependency) order."""
        stages = list(project.stages)
        # Topological sort by dependencies
        ordered: list[PipelineStage] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(stage: PipelineStage) -> None:
            if stage.id in visited:
                return
            if stage.id in visiting:
                return  # cycle — skip
            visiting.add(stage.id)
            for dep_id in stage.dependencies:
                dep = next((s for s in stages if s.id == dep_id), None)
                if dep is not None:
                    visit(dep)
            visiting.discard(stage.id)
            visited.add(stage.id)
            ordered.append(stage)

        for stage in stages:
            visit(stage)
        return ordered

    @staticmethod
    def ready_stages(project: PipelineProject) -> list[PipelineStage]:
        """Return stages whose dependencies are all completed."""
        completed_ids = {
            s.id for s in project.stages if s.status == StageStatus.COMPLETED.value
        }
        return [
            s
            for s in project.stages
            if s.status == StageStatus.PENDING.value
            and all(dep in completed_ids for dep in s.dependencies)
        ]

    @staticmethod
    def blocked_stages(project: PipelineProject) -> list[PipelineStage]:
        """Return stages that are blocked by incomplete dependencies."""
        completed_ids = {
            s.id for s in project.stages if s.status == StageStatus.COMPLETED.value
        }
        return [
            s
            for s in project.stages
            if s.status == StageStatus.PENDING.value
            and not all(dep in completed_ids for dep in s.dependencies)
        ]

    @staticmethod
    def parallel_groups(project: PipelineProject) -> list[list[PipelineStage]]:
        """Group stages into parallel-execution layers.

        Each layer contains stages that can run in parallel (their
        dependencies are all in earlier layers).
        """
        layers: list[list[PipelineStage]] = []
        placed: set[str] = set()
        remaining = list(project.stages)
        while remaining:
            layer = [
                s for s in remaining if all(dep in placed for dep in s.dependencies)
            ]
            if not layer:
                # Cycle or deadlock — place remaining in one layer
                layer = remaining
            layers.append(layer)
            for s in layer:
                placed.add(s.id)
            remaining = [s for s in remaining if s.id not in placed]
        return layers

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    @staticmethod
    def default_stage_kinds() -> list[str]:
        """Return the default 18 stage kinds in order."""
        return [kind for kind, _name, _deps in DEFAULT_STAGES]

    @staticmethod
    def default_stage_count() -> int:
        """Return the number of default stages."""
        return len(DEFAULT_STAGES)


__all__ = ["DEFAULT_STAGES", "PipelinePlanner"]
