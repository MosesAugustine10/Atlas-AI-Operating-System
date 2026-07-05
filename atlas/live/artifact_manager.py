"""Artifact manager — tracks every output as a searchable artifact.

Every output produced by the Atlas execution flow — files, images,
videos, code, documents — becomes an :class:`Artifact` that is stored,
searchable, and retrievable.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.core.logger import get_logger


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str = "art") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class ArtifactType(enum.StrEnum):
    """Supported artifact types."""

    IMAGE = "image"
    VIDEO = "video"
    BLEND = "blend"
    PYTHON = "python"
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"
    ZIP = "zip"
    TEXT = "text"
    HTML = "html"
    UNKNOWN = "unknown"


#: File extension → artifact type mapping.
EXTENSION_MAP: dict[str, ArtifactType] = {
    ".png": ArtifactType.IMAGE,
    ".jpg": ArtifactType.IMAGE,
    ".jpeg": ArtifactType.IMAGE,
    ".svg": ArtifactType.IMAGE,
    ".gif": ArtifactType.IMAGE,
    ".mp4": ArtifactType.VIDEO,
    ".avi": ArtifactType.VIDEO,
    ".mov": ArtifactType.VIDEO,
    ".webm": ArtifactType.VIDEO,
    ".blend": ArtifactType.BLEND,
    ".py": ArtifactType.PYTHON,
    ".md": ArtifactType.MARKDOWN,
    ".json": ArtifactType.JSON,
    ".csv": ArtifactType.CSV,
    ".pdf": ArtifactType.PDF,
    ".pptx": ArtifactType.PPTX,
    ".docx": ArtifactType.DOCX,
    ".zip": ArtifactType.ZIP,
    ".txt": ArtifactType.TEXT,
    ".html": ArtifactType.HTML,
    ".htm": ArtifactType.HTML,
}


@dataclass(frozen=True)
class Artifact:
    """A single output artifact.

    Attributes:
        id: Unique artifact identifier.
        name: Human-readable name.
        artifact_type: :class:`ArtifactType`.
        path: Filesystem path (if the artifact is a file).
        content: Inline content (if the artifact is text).
        source: What produced the artifact (e.g. ``"blender"``,
            ``"coding_agent"``).
        goal_id: The goal that produced this artifact.
        created_at: When the artifact was created.
        metadata: Free-form metadata.
    """

    id: str = field(default_factory=lambda: _new_id("art"))
    name: str = ""
    artifact_type: ArtifactType = ArtifactType.UNKNOWN
    path: str = ""
    content: str = ""
    source: str = ""
    goal_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class ArtifactManager:
    """Manages searchable artifacts.

    Parameters:
        storage_dir: Optional directory to store artifact files.
            If ``None``, artifacts are kept in-memory only.
    """

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else None
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, Artifact] = {}
        self.logger = get_logger("live.artifacts")

    def create(
        self,
        name: str,
        artifact_type: ArtifactType | str | None = None,
        path: str = "",
        content: str = "",
        source: str = "",
        goal_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        """Create and register a new artifact.

        If ``artifact_type`` is not specified, it is inferred from the
        file extension in ``name`` or ``path``.
        """
        if isinstance(artifact_type, str):
            artifact_type = ArtifactType(artifact_type)
        elif artifact_type is None:
            artifact_type = self._infer_type(name or path)
        artifact = Artifact(
            name=name,
            artifact_type=artifact_type,
            path=path,
            content=content,
            source=source,
            goal_id=goal_id,
            metadata=dict(metadata or {}),
        )
        self._artifacts[artifact.id] = artifact
        self.logger.info(
            "Created artifact %s: %s (%s)", artifact.id, name, artifact_type.value
        )
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        """Return the artifact with ``artifact_id`` or ``None``."""
        return self._artifacts.get(artifact_id)

    def list(
        self,
        artifact_type: ArtifactType | None = None,
        source: str | None = None,
        goal_id: str | None = None,
        limit: int = 100,
    ) -> list[Artifact]:
        """Return artifacts, optionally filtered."""
        result = list(self._artifacts.values())
        if artifact_type is not None:
            result = [a for a in result if a.artifact_type is artifact_type]
        if source is not None:
            result = [a for a in result if a.source == source]
        if goal_id is not None:
            result = [a for a in result if a.goal_id == goal_id]
        return sorted(result, key=lambda a: a.created_at, reverse=True)[:limit]

    def search(self, query: str) -> list[Artifact]:
        """Search artifacts by name, content, or source."""
        query_lower = query.lower()
        return [
            a
            for a in self._artifacts.values()
            if query_lower in a.name.lower()
            or query_lower in a.content.lower()
            or query_lower in a.source.lower()
        ]

    def count(self) -> int:
        """Return the total number of artifacts."""
        return len(self._artifacts)

    def count_by_type(self) -> dict[str, int]:
        """Return a ``{type: count}`` summary."""
        counts: dict[str, int] = {}
        for a in self._artifacts.values():
            key = a.artifact_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def delete(self, artifact_id: str) -> bool:
        """Remove an artifact by id."""
        return self._artifacts.pop(artifact_id, None) is not None

    def clear(self) -> None:
        """Remove every artifact."""
        self._artifacts.clear()

    def __len__(self) -> int:
        return len(self._artifacts)

    def __contains__(self, artifact_id: object) -> bool:
        return isinstance(artifact_id, str) and artifact_id in self._artifacts

    def __repr__(self) -> str:
        return f"<ArtifactManager artifacts={len(self)}>"

    @staticmethod
    def _infer_type(filename: str) -> ArtifactType:
        """Infer artifact type from a filename extension."""
        ext = Path(filename).suffix.lower()
        return EXTENSION_MAP.get(ext, ArtifactType.UNKNOWN)


__all__ = ["Artifact", "ArtifactManager", "ArtifactType", "EXTENSION_MAP"]
