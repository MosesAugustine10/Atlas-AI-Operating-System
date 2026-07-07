"""Quality Review stage coordinator.

A callback that reviews quality — returns a quality score (0.0 to 1.0).
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


class ReviewCoordinator:
    """Coordinates the quality_review stage.

    Parameters:
        review_fn: Optional callback for the stage.
    """

    def __init__(
        self,
        review_fn: ReviewFn | None = None,
    ) -> None:
        self._fn = review_fn

    def execute(
        self,
        project_goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute the quality_review stage.

        Returns the updated :class:`PipelineStage` and a list of
        :class:`PipelineArtifact` instances produced.
        """
        started = _utcnow()
        if self._fn is not None:
            score = self._fn(goal=project_goal, stage=stage)
        else:
            score = 0.85
        result = '{"quality_score": ' + str(score) + "}"

        asset_ref = AssetReference(
            id=_new_id("asset"),
            kind=AssetKind.DOCUMENT.value,
            name="review.json",
            path="/artifacts/review.json",
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


__all__ = ["ReviewCoordinator"]
