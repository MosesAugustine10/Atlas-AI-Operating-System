"""Atlas Creator AI Pipeline — autonomous content creation pipeline.

Transforms ONE user goal into a complete professional media project.

Example::

    "Create a YouTube documentary about SpaceX."
      ↓
    Research → Fact Check → Script → Storyboard → Shot Plan →
    Prompt Gen → Image Gen → Video Gen → Voice Synth → Music Select →
    Subtitle Gen → Timeline Assembly → Render → Quality Review →
    Thumbnail Gen → Metadata Gen → SEO Optimize → Package

The pipeline sits ABOVE the Collaboration Engine:

    User goal
      ↓
    Creator Pipeline  ← this package
      ↓
    Collaboration / Workforce / Brain / Execution / Runtime
      ↓
    Providers / MCP / Memory / Knowledge / Artifacts

**Dependency injection everywhere.** The pipeline NEVER imports
Brain, Workforce, Collaboration, or any Atlas subsystem directly.
It receives callbacks (``research_fn``, ``script_fn``,
``image_gen_fn``, etc.) via dependency injection and calls them.

Modules:

* :mod:`atlas.creator_pipeline.models` — frozen dataclasses and enums.
* :mod:`atlas.creator_pipeline.planner` — :class:`PipelinePlanner`.
* :mod:`atlas.creator_pipeline.research` — :class:`ResearchCoordinator`.
* :mod:`atlas.creator_pipeline.script` — :class:`ScriptCoordinator`.
* :mod:`atlas.creator_pipeline.storyboard` — :class:`StoryboardCoordinator`.
* :mod:`atlas.creator_pipeline.assets` — :class:`AssetsCoordinator`.
* :mod:`atlas.creator_pipeline.voice` — :class:`VoiceCoordinator`.
* :mod:`atlas.creator_pipeline.timeline` — :class:`TimelineCoordinator`.
* :mod:`atlas.creator_pipeline.render` — :class:`RenderCoordinator`.
* :mod:`atlas.creator_pipeline.review` — :class:`ReviewCoordinator`.
* :mod:`atlas.creator_pipeline.publisher` — :class:`PublisherCoordinator`.
* :mod:`atlas.creator_pipeline.orchestrator` — :class:`CreatorPipelineOrchestrator`.

Usage::

    from atlas.creator_pipeline import CreatorPipelineOrchestrator

    orch = CreatorPipelineOrchestrator()
    project = orch.create_project("Create a YouTube documentary about SpaceX")
    result = orch.run(project.id)
    print(f"Completed {result.stages_completed}/{len(project.stages)} stages")
    report = orch.generate_report(project.id)
"""

from __future__ import annotations

__version__ = "1.0.0"


# Re-export models (pure Python, always available)
from atlas.creator_pipeline.assets import AssetsCoordinator  # noqa: E402
from atlas.creator_pipeline.models import (  # noqa: E402
    AssetKind,
    AssetReference,
    ExportPackage,
    ImageGenFn,
    MetadataGenFn,
    MusicSelectFn,
    MusicTrack,
    PipelineArtifact,
    PipelineMetrics,
    PipelineProject,
    PipelineReport,
    PipelineResult,
    PipelineStage,
    PipelineState,
    PipelineTask,
    PlatformTarget,
    ProjectStatus,
    PromptTemplate,
    RenderFn,
    RenderJob,
    RenderProvider,
    ResearchFn,
    ReviewFn,
    ScriptFn,
    StageKind,
    StageStatus,
    StoryboardFn,
    SubtitleGenFn,
    SubtitleTrack,
    ThumbnailGenFn,
    TimelineSegment,
    VideoGenFn,
    VoiceSynthFn,
    VoiceTrack,
)
from atlas.creator_pipeline.orchestrator import (
    CreatorPipelineOrchestrator,
)  # noqa: E402

# Re-export coordinator + planner (pure Python, always available)
from atlas.creator_pipeline.planner import DEFAULT_STAGES, PipelinePlanner  # noqa: E402
from atlas.creator_pipeline.publisher import PublisherCoordinator  # noqa: E402
from atlas.creator_pipeline.render import RenderCoordinator  # noqa: E402
from atlas.creator_pipeline.research import ResearchCoordinator  # noqa: E402
from atlas.creator_pipeline.review import ReviewCoordinator  # noqa: E402
from atlas.creator_pipeline.script import ScriptCoordinator  # noqa: E402
from atlas.creator_pipeline.storyboard import StoryboardCoordinator  # noqa: E402
from atlas.creator_pipeline.timeline import TimelineCoordinator  # noqa: E402
from atlas.creator_pipeline.voice import VoiceCoordinator  # noqa: E402

__all__ = [
    "__version__",
    # Models
    "AssetKind",
    "AssetReference",
    "ExportPackage",
    "ImageGenFn",
    "MetadataGenFn",
    "MusicSelectFn",
    "MusicTrack",
    "PipelineArtifact",
    "PipelineMetrics",
    "PipelineProject",
    "PipelineReport",
    "PipelineResult",
    "PipelineStage",
    "PipelineState",
    "PipelineTask",
    "PlatformTarget",
    "PromptTemplate",
    "RenderFn",
    "RenderJob",
    "RenderProvider",
    "ResearchFn",
    "ReviewFn",
    "ScriptFn",
    "StageKind",
    "StageStatus",
    "ProjectStatus",
    "StoryboardFn",
    "SubtitleGenFn",
    "SubtitleTrack",
    "ThumbnailGenFn",
    "TimelineSegment",
    "VideoGenFn",
    "VoiceSynthFn",
    "VoiceTrack",
    # Planner + Coordinators
    "DEFAULT_STAGES",
    "PipelinePlanner",
    "ResearchCoordinator",
    "ScriptCoordinator",
    "StoryboardCoordinator",
    "AssetsCoordinator",
    "VoiceCoordinator",
    "TimelineCoordinator",
    "RenderCoordinator",
    "ReviewCoordinator",
    "PublisherCoordinator",
    "CreatorPipelineOrchestrator",
]
