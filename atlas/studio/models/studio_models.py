"""Studio data models — frozen dataclasses and enums for the MVVM layers.

This module is a *leaf* in the studio dependency graph. It defines every
value object exchanged between the Model, ViewModel and (eventually) View
layers of :mod:`atlas.studio`. Nothing here imports Qt or any other Atlas
subsystem — the models are pure, immutable and dependency-free so they can
be used from tests, controllers and headless scripts alike.

All dataclasses are :func:`dataclasses.dataclass` with ``frozen=True`` so
instances are hashable and safe to share across threads. Mutable defaults
(``list``, ``dict``) always use ``field(default_factory=...)``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PageId(enum.StrEnum):
    """Identifier for every top-level page in the Studio shell.

    The values are stable string keys used by navigation, workspaces and
    settings (e.g. ``pinned_pages``). Renaming a member is a breaking
    change; add new pages at the end.
    """

    CHAT = "chat"
    PROJECTS = "projects"
    AGENTS = "agents"
    PROVIDERS = "providers"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    WORKFLOWS = "workflows"
    EXECUTIONS = "executions"
    ARTIFACTS = "artifacts"
    SKILLS = "skills"
    TOOLS = "tools"
    MCP = "mcp"
    BROWSER = "browser"
    BLENDER = "blender"
    MINING = "mining"
    LOGS = "logs"
    SETTINGS = "settings"


class NavigationCategory(enum.StrEnum):
    """Logical grouping of pages in the navigation sidebar.

    Pages are rendered under their category heading; the order of the
    members here is the order the categories appear in the sidebar.
    """

    MAIN = "main"
    MONITORING = "monitoring"
    TOOLS = "tools"
    SYSTEM = "system"


class LogLevel(enum.StrEnum):
    """Severity levels for log entries shown in the Logs page."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Navigation & workspace models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageInfo:
    """Static description of a navigable Studio page.

    Attributes:
        id: Stable :class:`PageId` key.
        title: Human-readable label shown in the sidebar.
        icon: Lucide-style icon name (e.g. ``"message-square"``).
        description: One-line tooltip / subtitle.
        category: Sidebar grouping.
        position: Sort order within the category (lower comes first).
        enabled: Whether the page is selectable. Disabled pages are
            hidden from the sidebar but still resolvable by id.
    """

    id: PageId
    title: str
    icon: str
    description: str
    category: NavigationCategory
    position: int
    enabled: bool = True


@dataclass(frozen=True)
class TabInfo:
    """A single open tab in the workspace tab strip.

    Attributes:
        id: Unique tab identifier (generated when a tab is opened).
        title: Label shown on the tab.
        page_id: The :class:`PageId` this tab renders.
        icon: Optional icon name for the tab.
        closable: Whether the user may close the tab.
        pinned: Whether the tab is pinned to the left of the strip.
        modified: Whether the tab has unsaved changes (shows a dot).
        tooltip: Optional hover tooltip.
    """

    id: str
    title: str
    page_id: PageId
    icon: str = ""
    closable: bool = True
    pinned: bool = False
    modified: bool = False
    tooltip: str = ""


# ---------------------------------------------------------------------------
# Logging, events & notifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LogEntry:
    """A single line in the Logs page.

    Attributes:
        level: Severity of the entry.
        message: The log message text.
        source: Emitting component (e.g. ``"provider.ollama"``).
        timestamp: When the entry was produced.
        metadata: Free-form structured fields (request ids, etc.).
    """

    level: LogLevel
    message: str
    source: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventEntry:
    """A relayed runtime event shown in the Events panel.

    Attributes:
        type: Class name of the underlying runtime event.
        source: Component that emitted the event.
        timestamp: When the event was published.
        data: Serialized payload of the event.
    """

    type: str
    source: str
    timestamp: datetime = field(default_factory=_utcnow)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationEntry:
    """A toast / notification shown to the operator.

    Attributes:
        id: Unique notification identifier.
        title: Short headline.
        message: Body text.
        level: Severity used for icon / colour.
        timestamp: When the notification was raised.
        read: Whether the user has acknowledged it.
    """

    id: str
    title: str
    message: str
    level: LogLevel = LogLevel.INFO
    timestamp: datetime = field(default_factory=_utcnow)
    read: bool = False


# ---------------------------------------------------------------------------
# Execution timeline
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionStep:
    """One step within an :class:`ExecutionTimeline`.

    Attributes:
        name: Display name of the step.
        status: ``pending`` | ``running`` | ``completed`` | ``failed``
            | ``skipped``.
        started_at: When the step began, or ``None`` if not started.
        completed_at: When the step finished, or ``None`` if still
            running.
        duration: Wall-clock seconds the step took.
        detail: Optional human-readable detail / error message.
    """

    name: str
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float = 0.0
    detail: str = ""


@dataclass(frozen=True)
class ExecutionTimeline:
    """A full execution timeline for a goal.

    Attributes:
        goal_id: Identifier of the goal this timeline tracks.
        description: Human-readable goal description.
        steps: Ordered list of :class:`ExecutionStep`.
        current_step: Index of the currently executing step.
        status: ``idle`` | ``running`` | ``completed`` | ``failed``
            | ``cancelled``.
        started_at: When the goal started.
        completed_at: When the goal finished.
    """

    goal_id: str
    description: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "idle"
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Subsystem status snapshots
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderStatus:
    """Status snapshot of a single LLM provider.

    Attributes:
        name: Unique provider key (e.g. ``"ollama"``).
        display_name: Friendly label for the UI.
        available: Whether the provider is reachable.
        models: List of model identifiers the provider serves.
        latency_ms: Last measured round-trip latency.
        cost_per_1k: Estimated cost per 1k tokens (USD).
        priority: Routing priority (lower is preferred).
    """

    name: str
    display_name: str
    available: bool = False
    models: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    cost_per_1k: float = 0.0
    priority: int = 0


@dataclass(frozen=True)
class AgentStatus:
    """Status snapshot of a single agent.

    Attributes:
        name: Unique agent key.
        role: Human-readable role (e.g. ``"Researcher"``).
        status: ``idle`` | ``running`` | ``paused`` | ``error``.
        current_task: Description of the task the agent is working on.
        started_at: When the current task started.
        duration: Seconds the current task has been running.
    """

    name: str
    role: str = ""
    status: str = "idle"
    current_task: str = ""
    started_at: datetime | None = None
    duration: float = 0.0


@dataclass(frozen=True)
class ConnectorStatus:
    """Status snapshot of a single MCP connector.

    Attributes:
        name: Unique connector key (e.g. ``"blender"``).
        connected: Whether the connector is currently connected.
        capabilities: Capability names exposed by the connector.
        latency_ms: Last measured round-trip latency.
        health_level: ``"healthy"`` | ``"degraded"`` | ``"unhealthy"``
            | ``"unknown"``.
    """

    name: str
    connected: bool = False
    capabilities: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    health_level: str = "unknown"


@dataclass(frozen=True)
class ArtifactInfo:
    """Lightweight view of an artifact for the Artifacts page.

    Attributes:
        id: Unique artifact identifier.
        name: Human-readable name.
        type: Artifact type key (e.g. ``"image"``).
        source: Component that produced the artifact.
        created_at: When the artifact was created.
        size: Size in bytes (0 if unknown / inline).
        path: Filesystem path (empty for inline content).
        preview: Short text preview / thumbnail hint.
    """

    id: str
    name: str
    type: str
    source: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    size: int = 0
    path: str = ""
    preview: str = ""


@dataclass(frozen=True)
class MemoryEntry:
    """Lightweight view of a memory record for the Memory page.

    Note:
        This is the *studio* view model; it is distinct from
        :class:`atlas.memory.models.MemoryEntry` which is the storage
        record. The studio view only carries a content preview to keep
        the UI payload small.

    Attributes:
        id: Unique memory entry identifier.
        category: Memory category key (e.g. ``"working"``).
        content_preview: Truncated content for display.
        tags: Free-form tags.
        source: Origin of the memory.
        timestamp: When the memory was stored.
    """

    id: str
    category: str
    content_preview: str
    tags: list[str] = field(default_factory=list)
    source: str = ""
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class KnowledgeDoc:
    """Lightweight view of an indexed knowledge document.

    Attributes:
        id: Unique document identifier.
        source: Origin (file path, URL, etc.).
        content_type: MIME-style type hint.
        chunk_count: Number of chunks the document was split into.
        created_at: When the document was indexed.
        tags: Free-form tags.
    """

    id: str
    source: str
    content_type: str = "text/plain"
    chunk_count: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowRun:
    """A single run of a workflow for the Workflows page.

    Attributes:
        id: Unique run identifier.
        name: Workflow name.
        state: ``idle`` | ``running`` | ``completed`` | ``failed``
            | ``cancelled``.
        started_at: When the run started.
        completed_at: When the run finished.
        step_count: Total number of steps in the workflow.
        current_step: Index of the step currently executing.
    """

    id: str
    name: str
    state: str = "idle"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_count: int = 0
    current_step: int = 0


# ---------------------------------------------------------------------------
# System metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SystemMetric:
    """A single point-in-time system resource snapshot.

    All numeric fields default to ``0.0`` so a metric with no data is
    still constructible. ``gpu_*`` fields are ``0.0`` / empty when no GPU
    is present.

    Attributes:
        cpu_percent: Aggregate CPU utilisation (0–100).
        ram_percent: RAM utilisation (0–100).
        ram_used_mb: RAM in use, in MiB.
        ram_total_mb: Total RAM, in MiB.
        disk_percent: Disk utilisation (0–100).
        network_in: Inbound throughput in KB/s.
        network_out: Outbound throughput in KB/s.
        gpu_percent: GPU utilisation (0–100).
        gpu_name: GPU device name (empty if none).
    """

    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    disk_percent: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0
    gpu_percent: float = 0.0
    gpu_name: str = ""


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginInfo:
    """Metadata for a pluggable Studio page.

    Attributes:
        id: Unique plugin identifier.
        name: Human-readable plugin name.
        version: Semver-style version string.
        description: One-line description.
        page_class: Dotted import path of the page class to instantiate.
        enabled: Whether the plugin is currently enabled.
        dependencies: Other plugin ids this plugin requires.
    """

    id: str
    name: str
    version: str = "0.0.0"
    description: str = ""
    page_class: str = ""
    enabled: bool = True
    dependencies: list[str] = field(default_factory=list)


__all__ = [
    "AgentStatus",
    "ArtifactInfo",
    "ConnectorStatus",
    "EventEntry",
    "ExecutionStep",
    "ExecutionTimeline",
    "KnowledgeDoc",
    "LogEntry",
    "LogLevel",
    "MemoryEntry",
    "NavigationCategory",
    "NotificationEntry",
    "PageId",
    "PageInfo",
    "PluginInfo",
    "ProviderStatus",
    "SystemMetric",
    "TabInfo",
    "WorkflowRun",
]
