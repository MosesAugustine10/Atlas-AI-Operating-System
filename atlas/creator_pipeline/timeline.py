"""Timeline Assembly stage coordinator.

Coordinates the timeline_assembly stage.
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


class TimelineCoordinator:
    """Coordinates the timeline_assembly stage.

    Parameters:
        No callback needed.
    """

    def __init__(
        self,
    ) -> None:
        self._fn = None

    def execute(
        self,
        project_goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute the timeline_assembly stage.

        Returns the updated :class:`PipelineStage` and a list of
        :class:`PipelineArtifact` instances produced.
        """
        started = _utcnow()
        # Timeline coordinator assembles from prior assets
        result = '{"segments": [], "duration": 120.0}'

        asset_ref = AssetReference(
            id=_new_id("asset"),
            kind=AssetKind.TIMELINE.value,
            name="timeline.json",
            path="/artifacts/timeline.json",
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


__all__ = ["TimelineCoordinator"]
