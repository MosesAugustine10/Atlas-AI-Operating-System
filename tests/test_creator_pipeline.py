"""Tests for the Atlas Creator AI Pipeline (Phase 7).

Covers every module: models, planner, research, script, storyboard,
assets, voice, timeline, render, review, publisher, orchestrator.
All tests are deterministic and headless.
"""

from __future__ import annotations

import pytest

from atlas.creator_pipeline import (
    AssetKind,
    AssetReference,
    CreatorPipelineOrchestrator,
    ExportPackage,
    PipelineArtifact,
    PipelineMetrics,
    PipelinePlanner,
    PipelineProject,
    PipelineReport,
    PipelineResult,
    PipelineStage,
    PipelineState,
    PipelineTask,
    PlatformTarget,
    ProjectStatus,
    RenderJob,
    RenderProvider,
    StageKind,
    StageStatus,
    VoiceTrack,
    __version__,
)

# ===========================================================================
# Package
# ===========================================================================


class TestPackage:
    def test_version(self) -> None:
        assert __version__ == "1.0.0"

    def test_exports(self) -> None:
        from atlas.creator_pipeline import __all__

        assert "CreatorPipelineOrchestrator" in __all__
        assert "PipelinePlanner" in __all__
        assert "PipelineProject" in __all__


# ===========================================================================
# Enums
# ===========================================================================


class TestEnums:
    def test_stage_kind_count(self) -> None:
        assert len(list(StageKind)) == 18

    def test_stage_status_count(self) -> None:
        assert len(list(StageStatus)) == 9

    def test_project_status_count(self) -> None:
        assert len(list(ProjectStatus)) == 7

    def test_asset_kind_count(self) -> None:
        assert len(list(AssetKind)) == 9

    def test_render_provider_count(self) -> None:
        assert len(list(RenderProvider)) == 3

    def test_platform_target_count(self) -> None:
        assert len(list(PlatformTarget)) == 4


# ===========================================================================
# Models
# ===========================================================================


class TestModels:
    def test_asset_reference(self) -> None:
        a = AssetReference(id="a1", name="test.txt")
        assert a.kind == AssetKind.TEXT.value
        assert a.size_bytes == 0

    def test_asset_reference_frozen(self) -> None:
        a = AssetReference(id="a1")
        with pytest.raises(Exception):
            a.name = "x"  # type: ignore[misc]

    def test_pipeline_task_default(self) -> None:
        t = PipelineTask(id="t1", stage_id="s1")
        assert t.status == StageStatus.PENDING.value
        assert t.max_retries == 3

    def test_pipeline_stage_default(self) -> None:
        s = PipelineStage(id="s1")
        assert s.kind == StageKind.RESEARCH.value
        assert s.status == StageStatus.PENDING.value

    def test_pipeline_project_default(self) -> None:
        p = PipelineProject(id="p1")
        assert p.status == ProjectStatus.PLANNED.value
        assert p.stages == ()

    def test_pipeline_project_frozen(self) -> None:
        p = PipelineProject(id="p1")
        with pytest.raises(Exception):
            p.goal = "x"  # type: ignore[misc]

    def test_pipeline_result(self) -> None:
        r = PipelineResult(project_id="p1")
        assert r.stages_completed == 0

    def test_pipeline_metrics_completion_rate(self) -> None:
        m = PipelineMetrics(
            project_id="p1",
            stages_total=10,
            stages_completed=8,
        )
        assert m.completion_rate() == 0.8

    def test_pipeline_metrics_completion_rate_zero(self) -> None:
        m = PipelineMetrics(project_id="p1")
        assert m.completion_rate() == 0.0

    def test_pipeline_report(self) -> None:
        r = PipelineReport(id="r1", project_id="p1")
        assert r.result is None
        assert r.stages == ()

    def test_pipeline_artifact(self) -> None:
        a = PipelineArtifact(
            id="a1",
            asset_ref=AssetReference(id="ref1"),
        )
        assert a.quality_score == -1.0
        assert a.asset_ref.id == "ref1"

    def test_pipeline_state(self) -> None:
        s = PipelineState()
        assert s.artifacts == ()

    def test_voice_track(self) -> None:
        v = VoiceTrack(id="v1")
        assert v.language == "en"

    def test_render_job(self) -> None:
        j = RenderJob(id="j1")
        assert j.provider == RenderProvider.HYPERFRAMES.value
        assert j.status == "queued"

    def test_export_package(self) -> None:
        e = ExportPackage(id="e1")
        assert e.platform == PlatformTarget.YOUTUBE.value

    def test_prompt_template(self) -> None:
        from atlas.creator_pipeline.models import PromptTemplate

        t = PromptTemplate(
            id="t1",
            template="A {style} image of {subject}",
            variables=("style", "subject"),
        )
        rendered = t.render(style="cinematic", subject="SpaceX")
        assert "cinematic" in rendered
        assert "SpaceX" in rendered

    def test_prompt_template_missing_var(self) -> None:
        from atlas.creator_pipeline.models import PromptTemplate

        t = PromptTemplate(id="t1", template="A {style} image")
        rendered = t.render()
        assert rendered == "A {style} image"


# ===========================================================================
# PipelinePlanner
# ===========================================================================


class TestPlanner:
    def test_plan_default(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Create a documentary")
        assert project.goal == "Create a documentary"
        assert len(project.stages) == 18

    def test_plan_empty_goal_raises(self) -> None:
        p = PipelinePlanner()
        with pytest.raises(ValueError):
            p.plan("")

    def test_plan_whitespace_goal_raises(self) -> None:
        p = PipelinePlanner()
        with pytest.raises(ValueError):
            p.plan("   ")

    def test_plan_sets_status_planned(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal")
        assert project.status == ProjectStatus.PLANNED.value

    def test_plan_with_title(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal", title="My Title")
        assert project.title == "My Title"

    def test_plan_default_title_from_goal(self) -> None:
        p = PipelinePlanner()
        project = p.plan("A very long goal that should be truncated")
        assert project.title == "A very long goal that should be truncated"[:60]

    def test_plan_with_platforms(self) -> None:
        p = PipelinePlanner()
        project = p.plan(
            "Goal",
            target_platforms=("youtube", "tiktok"),
        )
        assert project.target_platforms == ("youtube", "tiktok")

    def test_stage_order(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal")
        ordered = PipelinePlanner.stage_order(project)
        assert len(ordered) == 18
        # Research should be first
        assert ordered[0].kind == StageKind.RESEARCH.value
        # Package should be last
        assert ordered[-1].kind == StageKind.PACKAGE.value

    def test_ready_stages_initial(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal")
        ready = PipelinePlanner.ready_stages(project)
        assert len(ready) == 1  # only research has no deps
        assert ready[0].kind == StageKind.RESEARCH.value

    def test_blocked_stages_initial(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal")
        blocked = PipelinePlanner.blocked_stages(project)
        assert len(blocked) == 17  # everything except research

    def test_parallel_groups(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal")
        groups = PipelinePlanner.parallel_groups(project)
        assert len(groups) > 1
        # First group should contain research
        assert groups[0][0].kind == StageKind.RESEARCH.value

    def test_default_stage_count(self) -> None:
        assert PipelinePlanner.default_stage_count() == 18

    def test_default_stage_kinds(self) -> None:
        kinds = PipelinePlanner.default_stage_kinds()
        assert StageKind.RESEARCH.value in kinds
        assert StageKind.PACKAGE.value in kinds
        assert len(kinds) == 18

    def test_custom_plan_fn(self) -> None:
        def custom_plan(**kwargs: object) -> list[dict[str, object]]:
            return [
                {"kind": "research", "name": "Research", "dependencies": ()},
                {"kind": "script", "name": "Script", "dependencies": ("research",)},
            ]

        p = PipelinePlanner(plan_fn=custom_plan)
        project = p.plan("Goal")
        assert len(project.stages) == 2

    def test_dependency_resolution(self) -> None:
        p = PipelinePlanner()
        project = p.plan("Goal")
        # Script stage depends on fact_check
        script = next(s for s in project.stages if s.kind == StageKind.SCRIPT.value)
        fact_check = next(
            s for s in project.stages if s.kind == StageKind.FACT_CHECK.value
        )
        assert fact_check.id in script.dependencies


# ===========================================================================
# ResearchCoordinator
# ===========================================================================


class TestResearchCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.research import ResearchCoordinator

        c = ResearchCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.RESEARCH.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert len(artifacts) == 1

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.research import ResearchCoordinator

        calls: list[str] = []

        def research_fn(**kwargs: object) -> str:
            calls.append(str(kwargs.get("goal", "")))
            return "Research notes"

        c = ResearchCoordinator(research_fn=research_fn)
        stage = PipelineStage(id="s1", kind=StageKind.RESEARCH.value)
        updated, artifacts = c.execute("My goal", stage)
        assert len(calls) == 1
        assert updated.status == StageStatus.COMPLETED.value
        assert artifacts[0].asset_ref.size_bytes > 0

    def test_produces_document_asset(self) -> None:
        from atlas.creator_pipeline.research import ResearchCoordinator

        c = ResearchCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.RESEARCH.value)
        _updated, artifacts = c.execute("Goal", stage)
        assert artifacts[0].asset_ref.kind == AssetKind.DOCUMENT.value

    def test_sets_duration(self) -> None:
        from atlas.creator_pipeline.research import ResearchCoordinator

        c = ResearchCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.RESEARCH.value)
        updated, _ = c.execute("Goal", stage)
        assert updated.duration_seconds >= 0.0


# ===========================================================================
# ScriptCoordinator
# ===========================================================================


class TestScriptCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.script import ScriptCoordinator

        c = ScriptCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.SCRIPT.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert len(artifacts) == 1

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.script import ScriptCoordinator

        c = ScriptCoordinator(script_fn=lambda **kw: "My script")
        stage = PipelineStage(id="s1", kind=StageKind.SCRIPT.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value


# ===========================================================================
# StoryboardCoordinator
# ===========================================================================


class TestStoryboardCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.storyboard import StoryboardCoordinator

        c = StoryboardCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.STORYBOARD.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert len(artifacts) == 1

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.storyboard import StoryboardCoordinator

        c = StoryboardCoordinator(
            storyboard_fn=lambda **kw: [{"frame": 1, "description": "Shot"}]
        )
        stage = PipelineStage(id="s1", kind=StageKind.STORYBOARD.value)
        updated, _ = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value


# ===========================================================================
# AssetsCoordinator
# ===========================================================================


class TestAssetsCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.assets import AssetsCoordinator

        c = AssetsCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.IMAGE_GEN.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert artifacts[0].asset_ref.kind == AssetKind.IMAGE.value

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.assets import AssetsCoordinator

        c = AssetsCoordinator(image_gen_fn=lambda **kw: "/artifacts/img1.png")
        stage = PipelineStage(id="s1", kind=StageKind.IMAGE_GEN.value)
        updated, _ = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value


# ===========================================================================
# VoiceCoordinator
# ===========================================================================


class TestVoiceCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.voice import VoiceCoordinator

        c = VoiceCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.VOICE_SYNTH.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert artifacts[0].asset_ref.kind == AssetKind.AUDIO.value

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.voice import VoiceCoordinator

        c = VoiceCoordinator(voice_synth_fn=lambda **kw: "/artifacts/voice.wav")
        stage = PipelineStage(id="s1", kind=StageKind.VOICE_SYNTH.value)
        updated, _ = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value


# ===========================================================================
# TimelineCoordinator
# ===========================================================================


class TestTimelineCoordinator:
    def test_execute(self) -> None:
        from atlas.creator_pipeline.timeline import TimelineCoordinator

        c = TimelineCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.TIMELINE_ASSEMBLY.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert artifacts[0].asset_ref.kind == AssetKind.TIMELINE.value


# ===========================================================================
# RenderCoordinator
# ===========================================================================


class TestRenderCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.render import RenderCoordinator

        c = RenderCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.RENDER.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert artifacts[0].asset_ref.kind == AssetKind.RENDER.value

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.render import RenderCoordinator

        c = RenderCoordinator(render_fn=lambda **kw: "/artifacts/render.mp4")
        stage = PipelineStage(id="s1", kind=StageKind.RENDER.value)
        updated, _ = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value


# ===========================================================================
# ReviewCoordinator
# ===========================================================================


class TestReviewCoordinator:
    def test_execute_no_fn(self) -> None:
        from atlas.creator_pipeline.review import ReviewCoordinator

        c = ReviewCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.QUALITY_REVIEW.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value

    def test_execute_with_fn(self) -> None:
        from atlas.creator_pipeline.review import ReviewCoordinator

        c = ReviewCoordinator(review_fn=lambda **kw: 0.95)
        stage = PipelineStage(id="s1", kind=StageKind.QUALITY_REVIEW.value)
        updated, _ = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value


# ===========================================================================
# PublisherCoordinator
# ===========================================================================


class TestPublisherCoordinator:
    def test_execute(self) -> None:
        from atlas.creator_pipeline.publisher import PublisherCoordinator

        c = PublisherCoordinator()
        stage = PipelineStage(id="s1", kind=StageKind.PACKAGE.value)
        updated, artifacts = c.execute("Goal", stage)
        assert updated.status == StageStatus.COMPLETED.value
        assert artifacts[0].asset_ref.kind == AssetKind.PACKAGE.value


# ===========================================================================
# CreatorPipelineOrchestrator
# ===========================================================================


class TestOrchestrator:
    def test_construct(self) -> None:
        o = CreatorPipelineOrchestrator()
        assert o is not None

    def test_create_project(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Create a documentary")
        assert project.goal == "Create a documentary"
        assert project.status == ProjectStatus.RUNNING.value
        assert len(project.stages) == 18

    def test_get_project(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        assert o.get_project(project.id) is project

    def test_get_project_none(self) -> None:
        o = CreatorPipelineOrchestrator()
        assert o.get_project("missing") is None

    def test_list_projects(self) -> None:
        o = CreatorPipelineOrchestrator()
        o.create_project("A")
        o.create_project("B")
        assert len(o.list_projects()) == 2

    def test_list_projects_by_status(self) -> None:
        o = CreatorPipelineOrchestrator()
        o.create_project("A")
        assert len(o.list_projects(status=ProjectStatus.RUNNING.value)) == 1

    def test_run_completes_all_stages(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Create a documentary")
        result = o.run(project.id)
        assert result.stages_completed == 18
        assert result.stages_failed == 0

    def test_run_produces_artifacts(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        artifacts = o.get_artifacts(project.id)
        assert len(artifacts) == 18

    def test_run_streams_events(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        events = list(o._run_streaming(project.id))
        event_types = [e["event"] for e in events]
        assert "project_start" in event_types
        assert "project_complete" in event_types

    def test_cancel_project(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.cancel_project(project.id)
        assert o.get_project(project.id).status == ProjectStatus.CANCELLED.value

    def test_resume_project(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.cancel_project(project.id)
        o.resume_project(project.id)
        # Cancelled is not resumable, so status stays cancelled
        # Let's test with paused instead
        import dataclasses

        paused = dataclasses.replace(
            o.get_project(project.id),
            status=ProjectStatus.PAUSED.value,
        )
        o._projects[project.id] = paused
        o.resume_project(project.id)
        assert o.get_project(project.id).status == ProjectStatus.RUNNING.value

    def test_retry_stage(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        # Mark a stage as failed
        import dataclasses

        stage = project.stages[0]
        failed = dataclasses.replace(stage, status=StageStatus.FAILED.value)
        o._projects[project.id] = dataclasses.replace(
            project, stages=(failed,) + project.stages[1:]
        )
        o.retry_stage(project.id, stage.id)
        updated = o.get_project(project.id)
        assert updated.stages[0].status == StageStatus.PENDING.value

    def test_export_project(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        o.export_project(project.id)
        assert o.get_project(project.id).status == ProjectStatus.EXPORTED.value

    def test_compute_result(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        result = o.compute_result(project.id)
        assert result.stages_completed == 18
        assert result.total_assets == 18

    def test_compute_metrics(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        metrics = o.compute_metrics(project.id)
        assert metrics.stages_total == 18
        assert metrics.stages_completed == 18
        assert metrics.assets_total == 18

    def test_generate_report(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        report = o.generate_report(project.id)
        assert report.project_id == project.id
        assert len(report.stages) == 18
        assert len(report.assets) == 18

    def test_checkpoint_restore(self) -> None:
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        state = o.checkpoint(project.id)
        assert state.project.id == project.id
        assert len(state.artifacts) == 18
        # Restore
        restored = o.restore(project.id)
        assert restored.id == project.id

    def test_status(self) -> None:
        o = CreatorPipelineOrchestrator()
        o.create_project("A")
        status = o.status()
        assert status["projects"] == 1

    def test_with_callbacks(self) -> None:
        calls: list[str] = []

        def research_fn(**kw: object) -> str:
            calls.append("research")
            return "notes"

        def script_fn(**kw: object) -> str:
            calls.append("script")
            return "script"

        o = CreatorPipelineOrchestrator(
            research_fn=research_fn,
            script_fn=script_fn,
        )
        project = o.create_project("Goal")
        o.run(project.id)
        assert "research" in calls
        assert "script" in calls

    def test_unknown_project_raises(self) -> None:
        o = CreatorPipelineOrchestrator()
        with pytest.raises(KeyError):
            o.compute_result("missing")


# ===========================================================================
# No subsystem imports
# ===========================================================================


class TestNoSubsystemImports:
    def test_creator_pipeline_does_not_import_subsystems(self) -> None:
        """The creator_pipeline package must not import any Atlas subsystem."""
        import os
        import re

        import atlas.creator_pipeline

        root = os.path.dirname(atlas.creator_pipeline.__file__)  # type: ignore[arg-type]
        forbidden = re.compile(
            r"^\s*from atlas\.(intelligence|execution|runtime|providers|mcp|memory|knowledge|workflows|tools|integration|agents|dashboard|live|studio|ide|creator|command|experience|desktop|app|pipeline|workforce|collaboration)\b"
        )
        offenders: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                with open(path) as f:
                    for lineno, line in enumerate(f, start=1):
                        if forbidden.match(line):
                            offenders.append(f"{path}:{lineno}: {line.rstrip()}")
        assert (
            not offenders
        ), "atlas.creator_pipeline imports other Atlas subsystems:\n" + "\n".join(
            offenders
        )

    def test_reload(self) -> None:
        import importlib

        import atlas.creator_pipeline

        importlib.reload(atlas.creator_pipeline)
        assert atlas.creator_pipeline.__version__ == "1.0.0"


# ===========================================================================
# End-to-end integration
# ===========================================================================


class TestIntegration:
    def test_full_youtube_documentary(self) -> None:
        """End-to-end: 'Create a YouTube documentary about SpaceX'."""
        o = CreatorPipelineOrchestrator()
        project = o.create_project(
            "Create a YouTube documentary about SpaceX",
            target_platforms=("youtube",),
        )
        result = o.run(project.id)
        assert result.status == ProjectStatus.COMPLETED.value
        assert result.stages_completed == 18
        assert result.total_assets == 18
        report = o.generate_report(project.id)
        assert len(report.stages) == 18

    def test_streaming_events_order(self) -> None:
        """Streaming events should be in the correct order."""
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        events = list(o._run_streaming(project.id))
        assert events[0]["event"] == "project_start"
        assert events[-1]["event"] in ("project_complete", "project_failed")

    def test_checkpoint_after_run(self) -> None:
        """Checkpointing after a run should capture all artifacts."""
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        o.run(project.id)
        state = o.checkpoint(project.id)
        assert len(state.artifacts) == 18
        assert state.project.status == ProjectStatus.COMPLETED.value

    def test_multiple_projects(self) -> None:
        """Multiple projects can run independently."""
        o = CreatorPipelineOrchestrator()
        p1 = o.create_project("Goal 1")
        p2 = o.create_project("Goal 2")
        r1 = o.run(p1.id)
        r2 = o.run(p2.id)
        assert r1.stages_completed == 18
        assert r2.stages_completed == 18

    def test_failure_recovery(self) -> None:
        """A failing stage marks the project as failed."""

        def failing_research(**kw: object) -> str:
            raise RuntimeError("research failed")

        o = CreatorPipelineOrchestrator(research_fn=failing_research)
        project = o.create_project("Goal")
        result = o.run(project.id)
        assert result.status == ProjectStatus.FAILED.value

    def test_retry_after_failure(self) -> None:
        """Retrying a failed stage resets it to pending."""
        o = CreatorPipelineOrchestrator()
        project = o.create_project("Goal")
        # Run to completion
        o.run(project.id)
        # Pick a stage and mark it failed
        import dataclasses

        stage = project.stages[5]
        failed = dataclasses.replace(stage, status=StageStatus.FAILED.value)
        o._projects[project.id] = dataclasses.replace(
            project,
            stages=tuple(failed if s.id == stage.id else s for s in project.stages),
        )
        o.retry_stage(project.id, stage.id)
        updated = o.get_project(project.id)
        retried = next(s for s in updated.stages if s.id == stage.id)
        assert retried.status == StageStatus.PENDING.value
