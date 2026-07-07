"""Render stage coordinator.

A callback that renders a timeline — returns a render asset path.
"""

from __future__ import annotations

from atlas.creator_pipeline.models import (
    AssetKind,
    AssetReference,
    PipelineArtifact,
    PipelineStage,
    StageStatus,
    _new_id,
    _utcnow,
)


class RenderCoordinator:
    """Coordinates the render stage.

    Parameters:
        render_fn: Optional callback for the stage.
    """

    def __init__(
        self,
        render_fn: RenderFn | None = None,
    ) -> None:
        self._fn = render_fn

    def execute(
        self,
        project_goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute the render stage.

        Returns the updated :class:`PipelineStage` and a list of
        :class:`PipelineArtifact` instances produced.
        """
        started = _utcnow()
        if self._fn is not None:
            result = self._fn(goal=project_goal, stage=stage)
        else:
            result = f"/artifacts/render/{_new_id('render')}"

        asset_ref = AssetReference(
            id=_new_id("asset"),
            kind=AssetKind.RENDER.value,
            name="render.mp4",
            path="/artifacts/render.mp4",
            produced_by_stage=stage.kind,
            size_bytes=len(str(result).encode("utf-8")),
        )
        artifact = PipelineArtifact(
            id=_new_id("artifact"),
            asset_ref=asset_ref,
            stage_id=stage.id,
            quality_score=0.8,
        )
        completed = _utcnow()
        import dataclasses

        updated_stage = dataclasses.replace(
            stage,
            status=StageStatus.COMPLETED.value,
            started_at=started,
            completed_at=completed,
            asset_refs=(asset_ref.id,),
            duration_seconds=(completed - started).total_seconds(),
        )
        return updated_stage, [artifact]


__all__ = ["RenderCoordinator"]
