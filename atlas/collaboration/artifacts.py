"""Shared artifact registry — collaboration outputs.

The :class:`ArtifactRegistry` manages :class:`SharedArtifact` instances
produced by agents during a collaboration session. Artifacts can be
code, documents, images, or any other output. Agents produce and
consume artifacts.
"""

from __future__ import annotations

import dataclasses

from atlas.collaboration.models import (
    SharedArtifact,
    _new_id,
)


class ArtifactRegistry:
    """Manages shared artifacts for collaboration sessions."""

    def __init__(self) -> None:
        self._artifacts: dict[str, SharedArtifact] = {}

    def produce(
        self,
        session_id: str,
        producer_id: str,
        kind: str = "file",
        name: str = "",
        content: str = "",
        path: str = "",
        tags: tuple[str, ...] = (),
    ) -> SharedArtifact:
        """Produce a new artifact."""
        artifact = SharedArtifact(
            id=_new_id("artifact"),
            session_id=session_id,
            producer_id=producer_id,
            kind=kind,
            name=name,
            content=content,
            path=path,
            tags=tags,
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def get(self, artifact_id: str) -> SharedArtifact | None:
        """Return the artifact with ``artifact_id`` or ``None``."""
        return self._artifacts.get(artifact_id)

    def consume(
        self,
        artifact_id: str,
        consumer_id: str,
    ) -> SharedArtifact | None:
        """Mark ``artifact_id`` as consumed by ``consumer_id``."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return None
        if consumer_id in artifact.consumer_ids:
            return artifact
        new_consumers = (*artifact.consumer_ids, consumer_id)
        updated = dataclasses.replace(artifact, consumer_ids=new_consumers)
        self._artifacts[artifact_id] = updated
        return updated

    def list_artifacts(
        self,
        session_id: str | None = None,
        kind: str | None = None,
        producer_id: str | None = None,
        tag: str | None = None,
    ) -> list[SharedArtifact]:
        """List artifacts with optional filters."""
        artifacts = list(self._artifacts.values())
        if session_id is not None:
            artifacts = [a for a in artifacts if a.session_id == session_id]
        if kind is not None:
            artifacts = [a for a in artifacts if a.kind == kind]
        if producer_id is not None:
            artifacts = [a for a in artifacts if a.producer_id == producer_id]
        if tag is not None:
            artifacts = [a for a in artifacts if tag in a.tags]
        artifacts.sort(key=lambda a: a.created_at, reverse=True)
        return artifacts

    def by_producer(self, producer_id: str) -> list[SharedArtifact]:
        """Return artifacts produced by ``producer_id``."""
        return [a for a in self._artifacts.values() if a.producer_id == producer_id]

    def consumed_by(self, consumer_id: str) -> list[SharedArtifact]:
        """Return artifacts consumed by ``consumer_id``."""
        return [a for a in self._artifacts.values() if consumer_id in a.consumer_ids]

    def search(self, query: str) -> list[SharedArtifact]:
        """Return artifacts whose name or content contains ``query``."""
        q = query.lower()
        return [
            a
            for a in self._artifacts.values()
            if q in a.name.lower() or q in a.content.lower()
        ]

    def count(self) -> int:
        """Return the total number of artifacts."""
        return len(self._artifacts)

    def count_by_kind(self) -> dict[str, int]:
        """Return a dict of artifact counts by kind."""
        counts: dict[str, int] = {}
        for a in self._artifacts.values():
            counts[a.kind] = counts.get(a.kind, 0) + 1
        return counts

    def delete(self, artifact_id: str) -> bool:
        """Delete an artifact. Returns ``True`` if deleted."""
        return self._artifacts.pop(artifact_id, None) is not None


__all__ = ["ArtifactRegistry"]
