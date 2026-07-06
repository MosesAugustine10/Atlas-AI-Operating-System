"""Image Gen stage coordinator.

A callback that generates images — returns an asset path.
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


class AssetsCoordinator:
    """Coordinates the image_gen stage.

    Parameters:
        image_gen_fn: Optional callback for the stage.
    """

    def __init__(
        self,
        image_gen_fn: ImageGenFn | None = None,
    ) -> None:
        self._fn = image_gen_fn

    def execute(
        self,
        project_goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute the image_gen stage.

        Returns the updated :class:`PipelineStage` and a list of
        :class:`PipelineArtifact` instances produced.
        """
        started = _utcnow()
        if self._fn is not None:
            result = self._fn(goal=project_goal, stage=stage)
        else:
            result = f"/artifacts/images/{_new_id('img')}"

        asset_ref = AssetReference(
            id=_new_id("asset"),
            kind=AssetKind.IMAGE.value,
            name="images/",
            path="/artifacts/images/",
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


__all__ = ["AssetsCoordinator"]
