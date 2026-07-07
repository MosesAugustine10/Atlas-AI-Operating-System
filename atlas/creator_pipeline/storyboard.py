"""Storyboard stage coordinator.

A callback that generates a storyboard — returns a list of frame dicts.
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


class StoryboardCoordinator:
    """Coordinates the storyboard stage.

    Parameters:
        storyboard_fn: Optional callback for the stage.
    """

    def __init__(
        self,
        storyboard_fn: StoryboardFn | None = None,
    ) -> None:
        self._fn = storyboard_fn

    def execute(
        self,
        project_goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute the storyboard stage.

        Returns the updated :class:`PipelineStage` and a list of
        :class:`PipelineArtifact` instances produced.
        """
        started = _utcnow()
        if self._fn is not None:
            frames = self._fn(goal=project_goal, stage=stage)
        else:
            frames = [{"frame": 1, "description": "Opening shot"}]
        result = str(frames)

        asset_ref = AssetReference(
            id=_new_id("asset"),
            kind=AssetKind.DOCUMENT.value,
            name="storyboard.json",
            path="/artifacts/storyboard.json",
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


__all__ = ["StoryboardCoordinator"]
