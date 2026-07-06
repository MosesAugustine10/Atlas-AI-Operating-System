"""Research stage coordinator.

The :class:`ResearchCoordinator` runs the research stage by calling
an injected ``research_fn`` callback. The callback typically delegates
to the Brain, Workforce Research Agent, or Knowledge Engine — but the
coordinator never imports those subsystems directly.
"""

from __future__ import annotations

from collections.abc import Callable

from atlas.creator_pipeline.models import (
    AssetKind,
    AssetReference,
    PipelineArtifact,
    PipelineStage,
    StageStatus,
    _new_id,
    _utcnow,
)


class ResearchCoordinator:
    """Coordinates the research stage.

    Parameters:
        research_fn: Optional callback invoked with ``(goal, **kwargs)``
            and returning a research-notes string. When omitted, a
            deterministic placeholder is produced.
    """

    def __init__(
        self,
        research_fn: Callable[..., str] | None = None,
    ) -> None:
        self._research_fn = research_fn

    def execute(
        self,
        project_goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute the research stage.

        Returns the updated :class:`PipelineStage` and a list of
        :class:`PipelineArtifact` instances produced.
        """
        started = _utcnow()
        # Execute the research callback
        if self._research_fn is not None:
            notes = self._research_fn(goal=project_goal, stage=stage)
        else:
            notes = f"Research notes for: {project_goal}"

        # Create the research asset
        asset_ref = AssetReference(
            id=_new_id("asset"),
            kind=AssetKind.DOCUMENT.value,
            name="research_notes.md",
            path="/artifacts/research_notes.md",
            produced_by_stage=stage.kind,
            size_bytes=len(notes.encode("utf-8")),
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


__all__ = ["ResearchCoordinator"]
