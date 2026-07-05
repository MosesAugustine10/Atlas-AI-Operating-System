"""Artifact controller — wraps the ArtifactManager for the Studio UI.

The :class:`ArtifactController` adapts the
:class:`~atlas.live.artifact_manager.ArtifactManager` (or any duck-typed
equivalent) into a list of
:class:`~atlas.studio.models.ArtifactInfo` snapshots for the Artifacts
page. All access is defensive: a ``None`` manager yields an empty list.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from atlas.studio.models.studio_models import ArtifactInfo


class ArtifactController:
    """ViewModel for the Artifacts page.

    Parameters:
        manager: Optional
            :class:`~atlas.live.artifact_manager.ArtifactManager`-like
            object. Expected duck-typed surface (any subset):
            ``list()``, ``search(query)``, ``get(id)``, ``delete(id)``,
            ``count()``.
    """

    def __init__(self, manager: Any = None) -> None:
        self._manager = manager

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def artifacts(self) -> list[ArtifactInfo]:
        """Return every artifact as an :class:`ArtifactInfo` (newest first)."""
        raw = self._list_all()
        infos = [self._to_info(item) for item in raw]
        infos.sort(key=lambda a: a.created_at, reverse=True)
        return infos

    def search(self, query: str) -> list[ArtifactInfo]:
        """Search artifacts by ``query`` (name / content / source)."""
        if self._manager is None or not query:
            return self.artifacts()
        method = getattr(self._manager, "search", None)
        if not callable(method):
            # Fall back to client-side filtering.
            query_lower = query.lower()
            return [
                a
                for a in self.artifacts()
                if query_lower in a.name.lower()
                or query_lower in a.preview.lower()
                or query_lower in a.source.lower()
            ]
        try:
            raw = method(query)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(raw, list):
            return []
        infos = [self._to_info(item) for item in raw]
        infos.sort(key=lambda a: a.created_at, reverse=True)
        return infos

    def filter_by_type(self, artifact_type: str) -> list[ArtifactInfo]:
        """Return artifacts whose type matches ``artifact_type``."""
        target = artifact_type.lower()
        return [a for a in self.artifacts() if a.type.lower() == target]

    def count(self) -> int:
        """Return the total number of artifacts."""
        if self._manager is None:
            return 0
        method = getattr(self._manager, "count", None)
        if callable(method):
            try:
                return int(method())
            except Exception:  # noqa: BLE001
                pass
        return len(self._list_all())

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def delete(self, artifact_id: str) -> bool:
        """Delete ``artifact_id`` from the wrapped manager."""
        if self._manager is None:
            return False
        method = getattr(self._manager, "delete", None)
        if not callable(method):
            return False
        try:
            result = method(artifact_id)
        except Exception:  # noqa: BLE001
            return False
        return bool(result)

    def __len__(self) -> int:
        return self.count()

    def __repr__(self) -> str:
        return f"<ArtifactController artifacts={self.count()}>"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _list_all(self) -> list[Any]:
        """Return the raw artifact objects from the manager."""
        if self._manager is None:
            return []
        method = getattr(self._manager, "list", None)
        if callable(method):
            try:
                result = method()
            except Exception:  # noqa: BLE001
                return []
            if isinstance(result, list):
                return result
        # Fall back to iterating if the manager is itself iterable.
        try:
            return list(self._manager)
        except TypeError:
            return []

    @staticmethod
    def _to_info(artifact: Any) -> ArtifactInfo:
        """Convert a raw artifact into an :class:`ArtifactInfo`."""
        artifact_id = str(getattr(artifact, "id", "") or "")
        name = str(getattr(artifact, "name", "") or "")
        artifact_type = getattr(artifact, "artifact_type", None)
        type_str = (
            getattr(artifact_type, "value", None)
            if artifact_type is not None and not isinstance(artifact_type, str)
            else artifact_type
        )
        if type_str is None:
            type_str = getattr(artifact, "type", "unknown")
        source = str(getattr(artifact, "source", "") or "")
        created_at = getattr(artifact, "created_at", None)
        if not isinstance(created_at, datetime):
            from datetime import UTC
            from datetime import datetime as _dt

            created_at = _dt.now(UTC)
        size = _as_int(getattr(artifact, "size", 0), 0)
        path = str(getattr(artifact, "path", "") or "")
        preview = _preview(artifact)
        return ArtifactInfo(
            id=artifact_id,
            name=name,
            type=str(type_str or "unknown"),
            source=source,
            created_at=created_at,
            size=size,
            path=path,
            preview=preview,
        )


def _as_int(value: Any, default: int) -> int:
    """Coerce ``value`` to ``int``; return ``default`` on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _preview(artifact: Any) -> str:
    """Build a short text preview for an artifact."""
    content = getattr(artifact, "content", None)
    if isinstance(content, str) and content:
        return content[:120]
    name = getattr(artifact, "name", "")
    path = getattr(artifact, "path", "")
    if path:
        return str(path)
    return str(name)


__all__ = ["ArtifactController"]
