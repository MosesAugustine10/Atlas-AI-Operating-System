"""Atlas Creator AI Pipeline data models — frozen dataclasses and enums.

This module is a *leaf* in the creator_pipeline package dependency
graph. It defines every value object exchanged between the planner,
research, script, storyboard, assets, voice, timeline, render, review,
publisher, and orchestrator layers. Nothing here imports Brain,
Workforce, Collaboration, or any other Atlas subsystem — the models
are pure, immutable and dependency-free.

The Creator AI Pipeline sits ABOVE the Collaboration Engine:

    User goal ("Create a YouTube documentary about SpaceX")
      ↓
    Creator Pipeline  ← this package
      ↓
    Collaboration / Workforce / Brain / Execution / Runtime
      ↓
    Providers / MCP / Memory / Knowledge / Artifacts

The pipeline NEVER imports concrete implementations. It receives
callbacks (e.g. ``research_fn``, ``script_fn``, ``generate_fn``) via
dependency injection and calls them. This keeps the package fully
decoupled from every concrete Atlas subsystem.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _new_id(prefix: str = "cp") -> str:
    """Return a new unique identifier prefixed with ``prefix``."""
    return f"{prefix}_{uuid.uuid4().hex}"


# ===========================================================================
# Enumerations
# ===========================================================================


class StageKind(enum.StrEnum):
    """The 18 stages of the creator pipeline.

    Attributes:
        RESEARCH: Gather information and context.
        FACT_CHECK: Verify facts from the research stage.
        SCRIPT: Write the script.
        STORYBOARD: Generate storyboard frames.
        SHOT_PLAN: Plan shots for each storyboard frame.
        PROMPT_GEN: Generate image/video prompts.
        IMAGE_GEN: Generate images from prompts.
        VIDEO_GEN: Generate video clips.
        VOICE_SYNTH: Synthesize voice narration.
        MUSIC_SELECT: Select background music.
        SUBTITLE_GEN: Generate subtitles.
        TIMELINE_ASSEMBLY: Assemble the timeline from assets.
        RENDER: Render the final video.
        QUALITY_REVIEW: Review the rendered video quality.
        THUMBNAIL_GEN: Generate the video thumbnail.
        METADATA_GEN: Generate title, description, tags.
        SEO_OPTIMIZE: Optimize metadata for SEO.
        PACKAGE: Package everything for upload.
    """

    RESEARCH = "research"
    FACT_CHECK = "fact_check"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    SHOT_PLAN = "shot_plan"
    PROMPT_GEN = "prompt_gen"
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    VOICE_SYNTH = "voice_synth"
    MUSIC_SELECT = "music_select"
    SUBTITLE_GEN = "subtitle_gen"
    TIMELINE_ASSEMBLY = "timeline_assembly"
    RENDER = "render"
    QUALITY_REVIEW = "quality_review"
    THUMBNAIL_GEN = "thumbnail_gen"
    METADATA_GEN = "metadata_gen"
    SEO_OPTIMIZE = "seo_optimize"
    PACKAGE = "package"


class StageStatus(enum.StrEnum):
    """Lifecycle status of a pipeline stage.

    Attributes:
        PENDING: The stage has not started.
        READY: Dependencies are met; the stage is ready to run.
        RUNNING: The stage is currently executing.
        PAUSED: The stage has been paused (checkpoint).
        COMPLETED: The stage completed successfully.
        FAILED: The stage failed.
        SKIPPED: The stage was skipped.
        CANCELLED: The stage was cancelled.
        RETRYING: The stage is being retried after a failure.
    """

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ProjectStatus(enum.StrEnum):
    """Lifecycle status of a pipeline project.

    Attributes:
        PLANNED: The project has been planned but not started.
        RUNNING: The project is actively running.
        PAUSED: The project has been paused (checkpoint).
        COMPLETED: The project completed successfully.
        FAILED: The project failed.
        CANCELLED: The project was cancelled.
        EXPORTED: The project has been exported.
    """

    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPORTED = "exported"


class AssetKind(enum.StrEnum):
    """Kinds of assets produced by the pipeline.

    Attributes:
        TEXT: A text asset (research notes, script, etc.).
        IMAGE: An image asset.
        VIDEO: A video clip asset.
        AUDIO: An audio asset (voice, music, SFX).
        DOCUMENT: A document asset (storyboard, metadata).
        TIMELINE: A timeline asset.
        RENDER: A rendered video asset.
        THUMBNAIL: A thumbnail image asset.
        PACKAGE: A packaged export asset.
    """

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    TIMELINE = "timeline"
    RENDER = "render"
    THUMBNAIL = "thumbnail"
    PACKAGE = "package"


class RenderProvider(enum.StrEnum):
    """Render providers the pipeline can dispatch to.

    Attributes:
        HYPERFRAMES: HyperFrames composition engine.
        REMOTION: Remotion (React-based) composition engine.
        OPENMONTAGE: OpenMontage composition engine.
    """

    HYPERFRAMES = "hyperframes"
    REMOTION = "remotion"
    OPENMONTAGE = "openmontage"


class PlatformTarget(enum.StrEnum):
    """Platforms the pipeline can prepare upload packages for.

    Attributes:
        YOUTUBE: YouTube.
        TIKTOK: TikTok.
        INSTAGRAM: Instagram.
        FACEBOOK: Facebook.
    """

    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


# ===========================================================================
# Core models
# ===========================================================================


@dataclass(frozen=True)
class AssetReference:
    """A reference to an asset produced by a stage.

    Parameters:
        id: Unique asset reference id.
        kind: :class:`AssetKind`.
        name: Display name.
        path: Filesystem path or URL.
        produced_by_stage: The :class:`StageKind` that produced this asset.
        size_bytes: Size in bytes (0 = unknown).
        metadata: Immutable metadata mapping.
    """

    id: str
    kind: str = AssetKind.TEXT.value
    name: str = ""
    path: str = ""
    produced_by_stage: str = ""
    size_bytes: int = 0
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PromptTemplate:
    """A prompt template for image/video generation.

    Parameters:
        id: Unique template id.
        name: Template display name.
        template: The prompt text (with ``{placeholders}``).
        variables: Tuple of variable names the template accepts.
        category: Template category (e.g. "cinematic", "documentary").
    """

    id: str
    name: str = ""
    template: str = ""
    variables: tuple[str, ...] = ()
    category: str = "general"

    def render(self, **kwargs: str) -> str:
        """Render the template with the given variables."""
        try:
            return self.template.format(**kwargs)
        except (KeyError, IndexError):
            return self.template


@dataclass(frozen=True)
class TimelineSegment:
    """A single segment in the assembled timeline.

    Parameters:
        id: Unique segment id.
        order: 0-based ordering within the timeline.
        asset_ref_id: The :class:`AssetReference` id for this segment.
        kind: Segment kind (e.g. "video", "audio", "subtitle").
        start: Start time in seconds.
        duration: Duration in seconds.
        transition_in: Transition kind at the start.
        transition_out: Transition kind at the end.
    """

    id: str
    order: int = 0
    asset_ref_id: str = ""
    kind: str = "video"
    start: float = 0.0
    duration: float = 0.0
    transition_in: str = "cut"
    transition_out: str = "cut"


@dataclass(frozen=True)
class VoiceTrack:
    """A voice narration track.

    Parameters:
        id: Unique track id.
        voice_profile_id: The voice profile used.
        text: The narration text.
        audio_asset_ref_id: The produced audio :class:`AssetReference` id.
        duration: Duration in seconds.
        language: ISO language code.
    """

    id: str
    voice_profile_id: str = ""
    text: str = ""
    audio_asset_ref_id: str = ""
    duration: float = 0.0
    language: str = "en"


@dataclass(frozen=True)
class MusicTrack:
    """A background music track.

    Parameters:
        id: Unique track id.
        name: Track display name.
        artist: Artist / composer.
        mood: Music mood.
        audio_asset_ref_id: The audio :class:`AssetReference` id.
        duration: Duration in seconds.
        bpm: Beats per minute.
        license: License identifier.
    """

    id: str
    name: str = ""
    artist: str = ""
    mood: str = ""
    audio_asset_ref_id: str = ""
    duration: float = 0.0
    bpm: int = 0
    license: str = ""


@dataclass(frozen=True)
class SubtitleTrack:
    """A subtitle track.

    Parameters:
        id: Unique track id.
        language: ISO language code.
        entries: Tuple of (start, end, text) subtitle entries.
        format: Subtitle format (srt, vtt, ass).
        asset_ref_id: The produced subtitle :class:`AssetReference` id.
    """

    id: str
    language: str = "en"
    entries: tuple[tuple[float, float, str], ...] = ()
    format: str = "srt"
    asset_ref_id: str = ""


@dataclass(frozen=True)
class RenderJob:
    """A render job dispatched to a render provider.

    Parameters:
        id: Unique job id.
        provider: :class:`RenderProvider`.
        timeline_asset_ref_id: The timeline asset to render.
        output_asset_ref_id: The produced render asset (or "").
        status: Job status.
        progress: Progress fraction (0.0 to 1.0).
        started_at: When the job started (or None).
        completed_at: When the job completed (or None).
        error: Error message if failed.
        resolution: Target resolution (e.g. "1080p", "4k").
        fps: Target frames per second.
        estimated_cost_usd: Estimated cost in USD.
    """

    id: str
    provider: str = RenderProvider.HYPERFRAMES.value
    timeline_asset_ref_id: str = ""
    output_asset_ref_id: str = ""
    status: str = "queued"
    progress: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str = ""
    resolution: str = "1080p"
    fps: float = 30.0
    estimated_cost_usd: float = 0.0


@dataclass(frozen=True)
class ExportPackage:
    """A packaged export ready for upload.

    Parameters:
        id: Unique package id.
        platform: :class:`PlatformTarget`.
        title: Video title.
        description: Video description.
        tags: Tuple of tags/hashtags.
        video_asset_ref_id: The final video asset.
        thumbnail_asset_ref_id: The thumbnail asset.
        subtitle_asset_ref_ids: Tuple of subtitle asset ids.
        metadata: Immutable metadata mapping (category, privacy, etc.).
        created_at: When the package was created.
    """

    id: str
    platform: str = PlatformTarget.YOUTUBE.value
    title: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    video_asset_ref_id: str = ""
    thumbnail_asset_ref_id: str = ""
    subtitle_asset_ref_ids: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class PipelineTask:
    """A single task within a pipeline stage.

    Parameters:
        id: Unique task id.
        stage_id: The stage this task belongs to.
        name: Task display name.
        description: What the task does.
        status: :class:`StageStatus`.
        order: Ordering within the stage.
        dependencies: Tuple of task ids this task depends on.
        assigned_agent_id: The agent assigned to this task (or "").
        result: The task's result (or "").
        error: Error message if failed.
        created_at: When the task was created.
        started_at: When the task started (or None).
        completed_at: When the task completed (or None).
        retry_count: Number of times this task has been retried.
        max_retries: Maximum retries before giving up.
    """

    id: str
    stage_id: str
    name: str = ""
    description: str = ""
    status: str = StageStatus.PENDING.value
    order: int = 0
    dependencies: tuple[str, ...] = ()
    assigned_agent_id: str = ""
    result: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass(frozen=True)
class PipelineStage:
    """A stage in the creator pipeline.

    Parameters:
        id: Unique stage id.
        kind: :class:`StageKind`.
        name: Display name.
        status: :class:`StageStatus`.
        order: Ordering within the pipeline.
        dependencies: Tuple of stage ids this stage depends on.
        tasks: Tuple of :class:`PipelineTask` instances.
        asset_refs: Tuple of :class:`AssetReference` ids produced by this stage.
        created_at: When the stage was created.
        started_at: When the stage started (or None).
        completed_at: When the stage completed (or None).
        quality_score: Quality score from review (0.0 to 1.0, or -1 = unreviewed).
        cost_usd: Estimated cost of this stage in USD.
        duration_seconds: Actual duration of this stage.
        metadata: Immutable metadata mapping.
    """

    id: str
    kind: str = StageKind.RESEARCH.value
    name: str = ""
    status: str = StageStatus.PENDING.value
    order: int = 0
    dependencies: tuple[str, ...] = ()
    tasks: tuple[PipelineTask, ...] = ()
    asset_refs: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    quality_score: float = -1.0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PipelineProject:
    """A creator pipeline project.

    Parameters:
        id: Unique project id.
        goal: The high-level goal (e.g. "Create a YouTube documentary about SpaceX").
        title: Generated project title.
        status: :class:`ProjectStatus`.
        stages: Tuple of :class:`PipelineStage` instances.
        created_at: When the project was created.
        started_at: When the project started (or None).
        completed_at: When the project completed (or None).
        paused_at: When the project was last paused (or None).
        target_platforms: Tuple of :class:`PlatformTarget` values.
        metadata: Immutable metadata mapping.
    """

    id: str
    goal: str = ""
    title: str = ""
    status: str = ProjectStatus.PLANNED.value
    stages: tuple[PipelineStage, ...] = ()
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    target_platforms: tuple[str, ...] = (PlatformTarget.YOUTUBE.value,)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    """The result of running a pipeline project.

    Parameters:
        project_id: The project this result belongs to.
        status: Final project status.
        stages_completed: Number of completed stages.
        stages_failed: Number of failed stages.
        total_assets: Total assets produced.
        total_cost_usd: Total estimated cost.
        total_duration_seconds: Total actual duration.
        quality_score: Overall quality score (0.0 to 1.0).
        export_packages: Tuple of :class:`ExportPackage` ids produced.
        error: Error message if the project failed.
        completed_at: When the project completed (or None).
    """

    project_id: str
    status: str = ProjectStatus.PLANNED.value
    stages_completed: int = 0
    stages_failed: int = 0
    total_assets: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    quality_score: float = 0.0
    export_packages: tuple[str, ...] = ()
    error: str = ""
    completed_at: datetime | None = None


@dataclass(frozen=True)
class PipelineMetrics:
    """Metrics for a pipeline project.

    Parameters:
        project_id: The project these metrics describe.
        stages_total: Total number of stages.
        stages_completed: Number of completed stages.
        stages_failed: Number of failed stages.
        tasks_total: Total tasks across all stages.
        tasks_completed: Total completed tasks.
        assets_total: Total assets produced.
        assets_by_kind: Tuple of (kind, count) pairs.
        total_cost_usd: Total estimated cost.
        total_duration_seconds: Total actual duration.
        average_quality: Average quality score across stages.
        render_jobs: Number of render jobs.
        export_packages: Number of export packages.
        last_updated: When these metrics were last computed.
    """

    project_id: str
    stages_total: int = 0
    stages_completed: int = 0
    stages_failed: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0
    assets_total: int = 0
    assets_by_kind: tuple[tuple[str, int], ...] = ()
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    average_quality: float = 0.0
    render_jobs: int = 0
    export_packages: int = 0
    last_updated: datetime = field(default_factory=_utcnow)

    def completion_rate(self) -> float:
        """Return the fraction of completed stages (0.0 to 1.0)."""
        if self.stages_total == 0:
            return 0.0
        return self.stages_completed / self.stages_total


@dataclass(frozen=True)
class PipelineReport:
    """A comprehensive report of a pipeline project.

    Parameters:
        id: Unique report id.
        project_id: The project this report describes.
        generated_at: When the report was generated.
        result: The :class:`PipelineResult`.
        metrics: The :class:`PipelineMetrics`.
        stages: Tuple of stage summaries (kind, status, quality, cost, duration).
        assets: Tuple of asset summaries (kind, name, stage).
        export_packages: Tuple of :class:`ExportPackage` instances.
    """

    id: str
    project_id: str
    generated_at: datetime = field(default_factory=_utcnow)
    result: PipelineResult | None = None
    metrics: PipelineMetrics | None = None
    stages: tuple[tuple[str, str, float, float, float], ...] = ()
    assets: tuple[tuple[str, str, str], ...] = ()
    export_packages: tuple[ExportPackage, ...] = ()


@dataclass(frozen=True)
class PipelineArtifact:
    """An artifact produced by the pipeline.

    This is a richer wrapper around :class:`AssetReference` that
    includes provenance (which stage/task produced it) and quality
    scoring.

    Parameters:
        id: Unique artifact id.
        asset_ref: The underlying :class:`AssetReference`.
        stage_id: The stage that produced this artifact.
        task_id: The task that produced this artifact (or "").
        quality_score: Quality score (0.0 to 1.0, or -1 = unreviewed).
        created_at: When the artifact was created.
    """

    id: str
    asset_ref: AssetReference = field(default_factory=AssetReference)
    stage_id: str = ""
    task_id: str = ""
    quality_score: float = -1.0
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class PipelineState:
    """Immutable snapshot of the pipeline's state.

    Used for checkpointing — the orchestrator can save a
    :class:`PipelineState` and restore from it to resume a paused
    or failed project.

    Parameters:
        project: The :class:`PipelineProject`.
        artifacts: Tuple of :class:`PipelineArtifact` instances.
        timeline_segments: Tuple of :class:`TimelineSegment` instances.
        voice_tracks: Tuple of :class:`VoiceTrack` instances.
        music_tracks: Tuple of :class:`MusicTrack` instances.
        subtitle_tracks: Tuple of :class:`SubtitleTrack` instances.
        render_jobs: Tuple of :class:`RenderJob` instances.
        export_packages: Tuple of :class:`ExportPackage` instances.
        captured_at: When this state was captured.
    """

    project: PipelineProject = field(default_factory=lambda: PipelineProject(id=""))
    artifacts: tuple[PipelineArtifact, ...] = ()
    timeline_segments: tuple[TimelineSegment, ...] = ()
    voice_tracks: tuple[VoiceTrack, ...] = ()
    music_tracks: tuple[MusicTrack, ...] = ()
    subtitle_tracks: tuple[SubtitleTrack, ...] = ()
    render_jobs: tuple[RenderJob, ...] = ()
    export_packages: tuple[ExportPackage, ...] = ()
    captured_at: datetime = field(default_factory=_utcnow)


# ===========================================================================
# Callback type aliases (for dependency injection)
# ===========================================================================


#: A callback that researches a topic — returns a text result.
ResearchFn = Callable[..., str]

#: A callback that writes a script — returns the script text.
ScriptFn = Callable[..., str]

#: A callback that generates a storyboard — returns a list of frame dicts.
StoryboardFn = Callable[..., list[dict[str, Any]]]

#: A callback that generates an image — returns an asset path.
ImageGenFn = Callable[..., str]

#: A callback that generates a video clip — returns an asset path.
VideoGenFn = Callable[..., str]

#: A callback that synthesizes voice — returns an audio asset path.
VoiceSynthFn = Callable[..., str]

#: A callback that selects music — returns a music asset path.
MusicSelectFn = Callable[..., str]

#: A callback that generates subtitles — returns a subtitle asset path.
SubtitleGenFn = Callable[..., str]

#: A callback that renders a timeline — returns a render asset path.
RenderFn = Callable[..., str]

#: A callback that reviews quality — returns a quality score (0.0 to 1.0).
ReviewFn = Callable[..., float]

#: A callback that generates a thumbnail — returns an image asset path.
ThumbnailGenFn = Callable[..., str]

#: A callback that generates metadata — returns a dict.
MetadataGenFn = Callable[..., dict[str, Any]]


__all__ = [
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
    "_new_id",
    "_utcnow",
]
