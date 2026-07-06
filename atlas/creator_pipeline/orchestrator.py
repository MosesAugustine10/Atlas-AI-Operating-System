"""Creator Pipeline Orchestrator — the top-level facade.

The :class:`CreatorPipelineOrchestrator` is the single entry point
for the creator AI pipeline. It wires together every stage coordinator
(research, script, storyboard, assets, voice, timeline, render,
review, publisher) and the :class:`PipelinePlanner`.

The orchestrator supports:
* ``create_project(goal)`` — plan and start a new project.
* ``resume_project(project_id)`` — resume a paused/failed project.
* ``cancel_project(project_id)`` — cancel a running project.
* ``retry_stage(project_id, stage_id)`` — retry a failed stage.
* ``export_project(project_id)`` — export the final project.

The orchestrator NEVER imports Brain, Workforce, Collaboration, or
any Atlas subsystem directly. It receives callbacks via dependency
injection and calls them.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterator
from typing import Any

from atlas.creator_pipeline.assets import AssetsCoordinator
from atlas.creator_pipeline.models import (
    ExportPackage,
    PipelineArtifact,
    PipelineMetrics,
    PipelineProject,
    PipelineReport,
    PipelineResult,
    PipelineStage,
    PipelineState,
    ProjectStatus,
    StageKind,
    StageStatus,
    _new_id,
    _utcnow,
)
from atlas.creator_pipeline.planner import PipelinePlanner
from atlas.creator_pipeline.publisher import PublisherCoordinator
from atlas.creator_pipeline.render import RenderCoordinator
from atlas.creator_pipeline.research import ResearchCoordinator
from atlas.creator_pipeline.review import ReviewCoordinator
from atlas.creator_pipeline.script import ScriptCoordinator
from atlas.creator_pipeline.storyboard import StoryboardCoordinator
from atlas.creator_pipeline.timeline import TimelineCoordinator
from atlas.creator_pipeline.voice import VoiceCoordinator


class CreatorPipelineOrchestrator:
    """Top-level orchestrator for the creator AI pipeline.

    All parameters are optional — sensible defaults are used for any
    that are omitted. Injected callbacks wire the pipeline to real
    Atlas subsystems (Brain, Workforce, Providers, MCP, etc.).

    Parameters:
        research_fn: Callback for the research stage.
        script_fn: Callback for the script stage.
        storyboard_fn: Callback for the storyboard stage.
        image_gen_fn: Callback for image generation.
        video_gen_fn: Callback for video generation.
        voice_synth_fn: Callback for voice synthesis.
        music_select_fn: Callback for music selection.
        subtitle_gen_fn: Callback for subtitle generation.
        render_fn: Callback for rendering.
        review_fn: Callback for quality review.
        thumbnail_gen_fn: Callback for thumbnail generation.
        metadata_gen_fn: Callback for metadata generation.
        plan_fn: Optional custom planning callback.
    """

    def __init__(
        self,
        research_fn: Callable[..., str] | None = None,
        script_fn: Callable[..., str] | None = None,
        storyboard_fn: Callable[..., list[dict[str, Any]]] | None = None,
        image_gen_fn: Callable[..., str] | None = None,
        video_gen_fn: Callable[..., str] | None = None,
        voice_synth_fn: Callable[..., str] | None = None,
        music_select_fn: Callable[..., str] | None = None,
        subtitle_gen_fn: Callable[..., str] | None = None,
        render_fn: Callable[..., str] | None = None,
        review_fn: Callable[..., float] | None = None,
        thumbnail_gen_fn: Callable[..., str] | None = None,
        metadata_gen_fn: Callable[..., dict[str, Any]] | None = None,
        plan_fn: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        self.planner = PipelinePlanner(plan_fn=plan_fn)
        self.research_coord = ResearchCoordinator(research_fn=research_fn)
        self.script_coord = ScriptCoordinator(script_fn=script_fn)
        self.storyboard_coord = StoryboardCoordinator(storyboard_fn=storyboard_fn)
        self.assets_coord = AssetsCoordinator(image_gen_fn=image_gen_fn)
        self.voice_coord = VoiceCoordinator(voice_synth_fn=voice_synth_fn)
        self.timeline_coord = TimelineCoordinator()
        self.render_coord = RenderCoordinator(render_fn=render_fn)
        self.review_coord = ReviewCoordinator(review_fn=review_fn)
        self.publisher_coord = PublisherCoordinator()
        # Store all callbacks for later stages
        self._video_gen_fn = video_gen_fn
        self._music_select_fn = music_select_fn
        self._subtitle_gen_fn = subtitle_gen_fn
        self._thumbnail_gen_fn = thumbnail_gen_fn
        self._metadata_gen_fn = metadata_gen_fn
        # State
        self._projects: dict[str, PipelineProject] = {}
        self._artifacts: dict[str, list[PipelineArtifact]] = {}
        self._export_packages: dict[str, list[ExportPackage]] = {}
        self._checkpoints: dict[str, PipelineState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_project(
        self,
        goal: str,
        title: str = "",
        target_platforms: tuple[str, ...] = (),
    ) -> PipelineProject:
        """Create and start a new pipeline project.

        Parameters:
            goal: The high-level goal (e.g. "Create a YouTube documentary about SpaceX").
            title: Optional project title.
            target_platforms: Tuple of :class:`PlatformTarget` values.

        Returns the planned :class:`PipelineProject` in RUNNING status.
        """
        project = self.planner.plan(
            goal=goal,
            title=title,
            target_platforms=target_platforms,
        )
        project = dataclasses.replace(
            project,
            status=ProjectStatus.RUNNING.value,
            started_at=_utcnow(),
        )
        self._projects[project.id] = project
        self._artifacts[project.id] = []
        self._export_packages[project.id] = []
        return project

    def resume_project(self, project_id: str) -> PipelineProject:
        """Resume a paused or failed project."""
        project = self._require_project(project_id)
        if project.status not in (
            ProjectStatus.PAUSED.value,
            ProjectStatus.FAILED.value,
        ):
            return project
        return self._update_project(
            project_id,
            status=ProjectStatus.RUNNING.value,
            paused_at=None,
        )

    def cancel_project(self, project_id: str) -> PipelineProject:
        """Cancel a running project."""
        project = self._require_project(project_id)
        return self._update_project(
            project_id,
            status=ProjectStatus.CANCELLED.value,
            completed_at=_utcnow(),
        )

    def retry_stage(
        self,
        project_id: str,
        stage_id: str,
    ) -> PipelineProject:
        """Retry a failed stage."""
        project = self._require_project(project_id)
        stages = []
        for stage in project.stages:
            if stage.id == stage_id:
                stages.append(
                    dataclasses.replace(
                        stage,
                        status=StageStatus.PENDING.value,
                        started_at=None,
                        completed_at=None,
                    )
                )
            else:
                stages.append(stage)
        return self._update_project(project_id, stages=tuple(stages))

    def export_project(self, project_id: str) -> PipelineProject:
        """Mark a project as exported."""
        project = self._require_project(project_id)
        return self._update_project(
            project_id,
            status=ProjectStatus.EXPORTED.value,
            completed_at=_utcnow(),
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(
        self,
        project_id: str,
        stream: bool = False,
    ) -> PipelineResult:
        """Run all ready stages in a project.

        When ``stream`` is ``True``, yields events as a generator
        instead of returning a :class:`PipelineResult`.
        """
        if stream:
            return self._run_streaming(project_id)  # type: ignore[return-value]
        # Execute synchronously
        for _event in self._run_streaming(project_id):
            pass  # consume all events
        return self.compute_result(project_id)

    def _run_streaming(self, project_id: str) -> Iterator[dict[str, Any]]:
        """Run the project, yielding events."""
        project = self._require_project(project_id)
        yield {
            "event": "project_start",
            "data": {"project_id": project_id, "goal": project.goal},
        }

        # Execute stages in dependency order
        ordered = PipelinePlanner.stage_order(project)
        for stage in ordered:
            if stage.status == StageStatus.COMPLETED.value:
                yield {
                    "event": "stage_skip",
                    "data": {"stage_id": stage.id, "kind": stage.kind},
                }
                continue
            # Check dependencies
            completed_ids = {
                s.id for s in project.stages if s.status == StageStatus.COMPLETED.value
            }
            if not all(dep in completed_ids for dep in stage.dependencies):
                yield {
                    "event": "stage_blocked",
                    "data": {"stage_id": stage.id, "kind": stage.kind},
                }
                continue
            yield {
                "event": "stage_start",
                "data": {"stage_id": stage.id, "kind": stage.kind},
            }
            try:
                updated_stage, artifacts = self._execute_stage(
                    project_id, project.goal, stage
                )
                # Update project
                project = self._replace_stage(project_id, updated_stage)
                self._artifacts[project_id].extend(artifacts)
                yield {
                    "event": "stage_complete",
                    "data": {
                        "stage_id": stage.id,
                        "kind": stage.kind,
                        "artifacts": len(artifacts),
                    },
                }
            except Exception as exc:  # noqa: BLE001 — surface any error
                failed_stage = dataclasses.replace(
                    stage,
                    status=StageStatus.FAILED.value,
                    completed_at=_utcnow(),
                )
                project = self._replace_stage(project_id, failed_stage)
                yield {
                    "event": "stage_failed",
                    "data": {
                        "stage_id": stage.id,
                        "kind": stage.kind,
                        "error": str(exc),
                    },
                }
                # Mark project as failed
                self._update_project(project_id, status=ProjectStatus.FAILED.value)
                yield {
                    "event": "project_failed",
                    "data": {"project_id": project_id, "error": str(exc)},
                }
                return

        # All stages complete
        self._update_project(
            project_id,
            status=ProjectStatus.COMPLETED.value,
            completed_at=_utcnow(),
        )
        yield {"event": "project_complete", "data": {"project_id": project_id}}

    def _execute_stage(
        self,
        project_id: str,
        goal: str,
        stage: PipelineStage,
    ) -> tuple[PipelineStage, list[PipelineArtifact]]:
        """Execute a single stage using the appropriate coordinator."""
        coord = self._coordinator_for(stage.kind)
        if coord is None:
            # Unknown stage — mark as skipped
            return (
                dataclasses.replace(stage, status=StageStatus.SKIPPED.value),
                [],
            )
        return coord.execute(goal, stage)

    def _coordinator_for(self, stage_kind: str) -> Any:
        """Return the coordinator for ``stage_kind``."""
        mapping = {
            StageKind.RESEARCH.value: self.research_coord,
            StageKind.FACT_CHECK.value: self.research_coord,  # reuse research
            StageKind.SCRIPT.value: self.script_coord,
            StageKind.STORYBOARD.value: self.storyboard_coord,
            StageKind.SHOT_PLAN.value: self.storyboard_coord,  # reuse storyboard
            StageKind.PROMPT_GEN.value: self.storyboard_coord,  # reuse storyboard
            StageKind.IMAGE_GEN.value: self.assets_coord,
            StageKind.VIDEO_GEN.value: self.assets_coord,  # reuse assets
            StageKind.VOICE_SYNTH.value: self.voice_coord,
            StageKind.MUSIC_SELECT.value: self.voice_coord,  # reuse voice
            StageKind.SUBTITLE_GEN.value: self.voice_coord,  # reuse voice
            StageKind.TIMELINE_ASSEMBLY.value: self.timeline_coord,
            StageKind.RENDER.value: self.render_coord,
            StageKind.QUALITY_REVIEW.value: self.review_coord,
            StageKind.THUMBNAIL_GEN.value: self.assets_coord,  # reuse assets
            StageKind.METADATA_GEN.value: self.review_coord,  # reuse review
            StageKind.SEO_OPTIMIZE.value: self.review_coord,  # reuse review
            StageKind.PACKAGE.value: self.publisher_coord,
        }
        return mapping.get(stage_kind)

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def checkpoint(self, project_id: str) -> PipelineState:
        """Capture a :class:`PipelineState` checkpoint for the project."""
        project = self._require_project(project_id)
        state = PipelineState(
            project=project,
            artifacts=tuple(self._artifacts.get(project_id, [])),
        )
        self._checkpoints[project_id] = state
        return state

    def restore(self, project_id: str) -> PipelineProject:
        """Restore a project from its last checkpoint."""
        state = self._checkpoints.get(project_id)
        if state is None:
            raise KeyError(f"no checkpoint for project {project_id}")
        self._projects[project_id] = state.project
        self._artifacts[project_id] = list(state.artifacts)
        return state.project

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> PipelineProject | None:
        """Return the project with ``project_id`` or ``None``."""
        return self._projects.get(project_id)

    def list_projects(
        self,
        status: str | None = None,
    ) -> list[PipelineProject]:
        """List projects, optionally filtered by status."""
        projects = list(self._projects.values())
        if status is not None:
            projects = [p for p in projects if p.status == status]
        return projects

    def get_artifacts(self, project_id: str) -> list[PipelineArtifact]:
        """Return all artifacts produced for ``project_id``."""
        return list(self._artifacts.get(project_id, []))

    def get_export_packages(self, project_id: str) -> list[ExportPackage]:
        """Return all export packages for ``project_id``."""
        return list(self._export_packages.get(project_id, []))

    def compute_result(self, project_id: str) -> PipelineResult:
        """Compute the :class:`PipelineResult` for ``project_id``."""
        project = self._require_project(project_id)
        completed = sum(
            1 for s in project.stages if s.status == StageStatus.COMPLETED.value
        )
        failed = sum(1 for s in project.stages if s.status == StageStatus.FAILED.value)
        artifacts = self._artifacts.get(project_id, [])
        packages = self._export_packages.get(project_id, [])
        total_cost = sum(s.cost_usd for s in project.stages)
        total_duration = sum(s.duration_seconds for s in project.stages)
        quality_scores = [
            s.quality_score for s in project.stages if s.quality_score >= 0.0
        ]
        return PipelineResult(
            project_id=project_id,
            status=project.status,
            stages_completed=completed,
            stages_failed=failed,
            total_assets=len(artifacts),
            total_cost_usd=total_cost,
            total_duration_seconds=total_duration,
            quality_score=(
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            ),
            export_packages=tuple(p.id for p in packages),
            completed_at=project.completed_at,
        )

    def compute_metrics(self, project_id: str) -> PipelineMetrics:
        """Compute :class:`PipelineMetrics` for ``project_id``."""
        project = self._require_project(project_id)
        artifacts = self._artifacts.get(project_id, [])
        packages = self._export_packages.get(project_id, [])
        completed = sum(
            1 for s in project.stages if s.status == StageStatus.COMPLETED.value
        )
        failed = sum(1 for s in project.stages if s.status == StageStatus.FAILED.value)
        # Count assets by kind
        by_kind: dict[str, int] = {}
        for art in artifacts:
            kind = art.asset_ref.kind
            by_kind[kind] = by_kind.get(kind, 0) + 1
        quality_scores = [
            s.quality_score for s in project.stages if s.quality_score >= 0.0
        ]
        return PipelineMetrics(
            project_id=project_id,
            stages_total=len(project.stages),
            stages_completed=completed,
            stages_failed=failed,
            assets_total=len(artifacts),
            assets_by_kind=tuple(sorted(by_kind.items())),
            total_cost_usd=sum(s.cost_usd for s in project.stages),
            total_duration_seconds=sum(s.duration_seconds for s in project.stages),
            average_quality=(
                sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            ),
            render_jobs=sum(
                1 for s in project.stages if s.kind == StageKind.RENDER.value
            ),
            export_packages=len(packages),
        )

    def generate_report(self, project_id: str) -> PipelineReport:
        """Generate a :class:`PipelineReport` for ``project_id``."""
        project = self._require_project(project_id)
        result = self.compute_result(project_id)
        metrics = self.compute_metrics(project_id)
        artifacts = self._artifacts.get(project_id, [])
        packages = self._export_packages.get(project_id, [])
        stage_summaries = tuple(
            (s.kind, s.status, s.quality_score, s.cost_usd, s.duration_seconds)
            for s in project.stages
        )
        asset_summaries = tuple(
            (a.asset_ref.kind, a.asset_ref.name, a.stage_id) for a in artifacts
        )
        return PipelineReport(
            id=_new_id("report"),
            project_id=project_id,
            result=result,
            metrics=metrics,
            stages=stage_summaries,
            assets=asset_summaries,
            export_packages=tuple(packages),
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Return a summary of the orchestrator's state."""
        return {
            "projects": len(self._projects),
            "running": len(self.list_projects(status=ProjectStatus.RUNNING.value)),
            "completed": len(self.list_projects(status=ProjectStatus.COMPLETED.value)),
            "failed": len(self.list_projects(status=ProjectStatus.FAILED.value)),
            "checkpoints": len(self._checkpoints),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_project(self, project_id: str) -> PipelineProject:
        project = self._projects.get(project_id)
        if project is None:
            raise KeyError(f"project {project_id} not found")
        return project

    def _update_project(
        self,
        project_id: str,
        **changes: Any,
    ) -> PipelineProject:
        project = self._projects[project_id]
        updated = dataclasses.replace(project, **changes)
        self._projects[project_id] = updated
        return updated

    def _replace_stage(
        self,
        project_id: str,
        new_stage: PipelineStage,
    ) -> PipelineProject:
        project = self._projects[project_id]
        stages = tuple(new_stage if s.id == new_stage.id else s for s in project.stages)
        return self._update_project(project_id, stages=stages)


__all__ = ["CreatorPipelineOrchestrator"]
