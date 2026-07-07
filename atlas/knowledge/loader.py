"""Document loader for the Atlas Knowledge Engine.

The :class:`DocumentLoader` reads raw files from disk (or accepts raw text)
and produces :class:`KnowledgeDocument` objects. It supports plain text and
Markdown natively; PDF and DOCX are declared as placeholders to be wired in
when binary parsers are added.
"""

from __future__ import annotations

from pathlib import Path

from atlas.core.logger import get_logger
from atlas.knowledge.models import KnowledgeDocument

_CONTENT_TYPE_MAP: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentLoader:
    """Loads documents from files or raw text.

    Parameters:
        default_encoding: Text encoding used when reading text files.
    """

    def __init__(self, default_encoding: str = "utf-8") -> None:
        self.default_encoding = default_encoding
        self.logger = get_logger("knowledge.loader")

    def load_file(
        self,
        path: str | Path,
        tags: list[str] | None = None,
        **metadata: object,
    ) -> KnowledgeDocument:
        """Load a document from a file path.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            NotImplementedError: For unsupported binary formats (PDF, DOCX).
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")

        suffix = p.suffix.lower()
        content_type = _CONTENT_TYPE_MAP.get(suffix, "text/plain")

        if suffix in (".pdf", ".docx"):
            raise NotImplementedError(f"Loading {suffix} files is not yet implemented")

        content = p.read_text(encoding=self.default_encoding)
        self.logger.info("Loaded file: %s (%s)", p, content_type)
        return self.load_text(
            content=content,
            source=str(p),
            content_type=content_type,
            tags=tags,
            **metadata,
        )

    def load_text(
        self,
        content: str,
        source: str,
        content_type: str = "text/plain",
        tags: list[str] | None = None,
        **metadata: object,
    ) -> KnowledgeDocument:
        """Build a :class:`KnowledgeDocument` from raw text."""
        return KnowledgeDocument(
            content=content,
            source=source,
            content_type=content_type,
            tags=list(tags or []),
            metadata=dict(metadata),
        )
