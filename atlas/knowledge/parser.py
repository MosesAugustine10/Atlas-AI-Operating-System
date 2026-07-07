"""Document parser for the Atlas Knowledge Engine.

The :class:`DocumentParser` extracts clean, normalised text from a
:class:`KnowledgeDocument`. Plain-text and Markdown are supported now; PDF,
HTML, and web-page parsing are reserved for future implementations. The
parser is deliberately separate from the loader so that re-parsing a cached
document never requires re-reading the source file.
"""

from __future__ import annotations

import re

from atlas.core.logger import get_logger
from atlas.knowledge.models import KnowledgeDocument


class DocumentParser:
    """Extracts and normalises text from documents.

    The parser strips Markdown formatting noise (image tags, link URLs) so
    downstream chunking operates on prose rather than markup.
    """

    def __init__(self) -> None:
        self.logger = get_logger("knowledge.parser")

    def parse(self, document: KnowledgeDocument) -> str:
        """Return clean text extracted from ``document``.

        Dispatches on ``content_type``. Unknown types are treated as plain
        text.
        """
        ct = document.content_type
        if ct == "text/markdown":
            return self._parse_markdown(document.content)
        if ct == "text/plain":
            return self._parse_plain(document.content)
        # Future: PDF, HTML, GitHub README, web pages.
        self.logger.debug("Falling back to plain parser for %s", ct)
        return self._parse_plain(document.content)

    def _parse_plain(self, text: str) -> str:
        """Normalise whitespace in plain text."""
        return text.strip()

    def _parse_markdown(self, text: str) -> str:
        """Strip common Markdown markup, leaving readable prose.

        Removes image syntax, link URLs (keeping anchor text), and code
        fences. This is intentionally lightweight; a full AST parser can
        replace it later.
        """
        cleaned = text
        # ![alt](url) -> alt
        cleaned = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", cleaned)
        # [text](url) -> text
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        # ``` fenced code ``` -> keep contents (still useful prose in docs)
        cleaned = re.sub(r"```", "", cleaned)
        # Leading/trailing hash on headings: "# Title" -> "Title"
        cleaned = re.sub(r"(?m)^#{1,6}\s+", "", cleaned)
        return cleaned.strip()
