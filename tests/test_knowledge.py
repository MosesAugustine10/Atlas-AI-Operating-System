"""Tests for the Atlas Knowledge Engine.

Covers models, loader, parser, chunker, embeddings, vector store,
retriever, and engine — exercising the full ingestion and retrieval
pipelines.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from atlas.knowledge.chunker import TextChunker
from atlas.knowledge.embeddings import HashingEmbedder
from atlas.knowledge.engine import KnowledgeEngine
from atlas.knowledge.loader import DocumentLoader
from atlas.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeResult,
)
from atlas.knowledge.parser import DocumentParser
from atlas.knowledge.retriever import Retriever
from atlas.knowledge.store import InMemoryKnowledgeStore
from atlas.knowledge.vectorstore import InMemoryVectorStore

# Fixtures ------------------------------------------------------------------


def _lorem_ipsum() -> str:
    return (
        "Atlas is an AI Operating System. It provides persistent identity, "
        "governed principles, organized memory, curated knowledge, and "
        "controlled tooling. Atlas is not a chatbot. It is the operating "
        "layer through which an AI agent perceives, remembers, reasons, "
        "and acts with continuity across sessions."
    ) * 10


def _short_doc() -> KnowledgeDocument:
    return KnowledgeDocument(
        content="Short document about mining operations.",
        source="test.txt",
        tags=["mining"],
    )


# Models ---------------------------------------------------------------------


def test_document_defaults() -> None:
    doc = KnowledgeDocument(content="hello", source="test.txt")
    assert doc.id
    assert doc.content == "hello"
    assert doc.source == "test.txt"
    assert doc.content_type == "text/plain"
    assert doc.tags == []
    assert doc.created_at


def test_chunk_defaults() -> None:
    chunk = KnowledgeChunk(document_id="doc-1", content="hello", index=0)
    assert chunk.id
    assert chunk.document_id == "doc-1"
    assert chunk.index == 0


def test_query_defaults() -> None:
    q = KnowledgeQuery(text="mining")
    assert q.top_k == 5
    assert q.min_score == 0.0


def test_result_construction() -> None:
    doc = _short_doc()
    chunk = KnowledgeChunk(document_id=doc.id, content="x", index=0)
    r = KnowledgeResult(chunk=chunk, document=doc, score=0.95)
    assert r.score == 0.95


# Loader ----------------------------------------------------------------------


def test_loader_load_text() -> None:
    loader = DocumentLoader()
    doc = loader.load_text(
        content="hello world",
        source="inline",
        content_type="text/plain",
        tags=["test"],
    )
    assert doc.content == "hello world"
    assert doc.tags == ["test"]


def test_loader_load_txt_file(tmp_path: Path) -> None:
    (tmp_path / "demo.txt").write_text("file content", encoding="utf-8")
    loader = DocumentLoader()
    doc = loader.load_file(tmp_path / "demo.txt")
    assert doc.content == "file content"
    assert doc.content_type == "text/plain"


def test_loader_load_md_file(tmp_path: Path) -> None:
    (tmp_path / "demo.md").write_text("# Title\nBody", encoding="utf-8")
    loader = DocumentLoader()
    doc = loader.load_file(tmp_path / "demo.md")
    assert doc.content_type == "text/markdown"


def test_loader_file_not_found(tmp_path: Path) -> None:
    loader = DocumentLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_file(tmp_path / "missing.txt")


def test_loader_pdf_not_implemented(tmp_path: Path) -> None:
    (tmp_path / "demo.pdf").write_bytes(b"%PDF-1.4")
    loader = DocumentLoader()
    with pytest.raises(NotImplementedError):
        loader.load_file(tmp_path / "demo.pdf")


# Parser ----------------------------------------------------------------------


def test_parser_plain_text() -> None:
    doc = KnowledgeDocument(content="  hello  ", source="t", content_type="text/plain")
    parsed = DocumentParser().parse(doc)
    assert parsed == "hello"


def test_parser_markdown_images() -> None:
    doc = KnowledgeDocument(
        content="See ![chart](img.png) here",
        source="t",
        content_type="text/markdown",
    )
    parsed = DocumentParser().parse(doc)
    assert "img.png" not in parsed
    assert "chart" in parsed


def test_parser_markdown_links() -> None:
    doc = KnowledgeDocument(
        content="Read [docs](https://example.com) now",
        source="t",
        content_type="text/markdown",
    )
    parsed = DocumentParser().parse(doc)
    assert "https://example.com" not in parsed
    assert "docs" in parsed


def test_parser_markdown_headings() -> None:
    doc = KnowledgeDocument(
        content="# Title\n## Sub",
        source="t",
        content_type="text/markdown",
    )
    parsed = DocumentParser().parse(doc)
    assert "#" not in parsed
    assert "Title" in parsed


# Chunker ---------------------------------------------------------------------


def test_chunker_basic(tmp_path: Path) -> None:
    chunker = TextChunker(chunk_size=50, overlap=10)
    doc = KnowledgeDocument(content="a" * 120, source="t")
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c.index == i
        assert c.document_id == doc.id


def test_chunker_overlap() -> None:
    chunker = TextChunker(chunk_size=20, overlap=5)
    doc = KnowledgeDocument(content="a" * 50, source="t")
    chunks = chunker.chunk(doc)
    # Overlap means the last 5 chars of chunk N appear at the start of N+1
    if len(chunks) >= 2:
        end_of_first = chunks[0].content[-5:]
        start_of_second = chunks[1].content[:5]
        assert end_of_first == start_of_second


def test_chunker_empty_content() -> None:
    chunker = TextChunker()
    doc = KnowledgeDocument(content="", source="t")
    assert chunker.chunk(doc) == []


def test_chunker_overlap_too_large_raises() -> None:
    with pytest.raises(ValueError, match="overlap"):
        TextChunker(chunk_size=10, overlap=20)


def test_chunker_tag_inheritance() -> None:
    chunker = TextChunker(chunk_size=50, overlap=10)
    doc = KnowledgeDocument(content="x" * 100, source="t", tags=["mining"])
    chunks = chunker.chunk(doc)
    for c in chunks:
        assert "mining" in c.tags


# Embeddings ------------------------------------------------------------------


def test_hashing_embedder_deterministic() -> None:
    embedder = HashingEmbedder(dimensions=32)
    v1 = embedder.embed_document("atlas")
    v2 = embedder.embed_document("atlas")
    assert v1 == v2


def test_hashing_embedder_different_texts_differ() -> None:
    embedder = HashingEmbedder(dimensions=32)
    v1 = embedder.embed_document("atlas")
    v2 = embedder.embed_document("something else")
    assert v1 != v2


def test_hashing_embedder_normalised() -> None:
    embedder = HashingEmbedder(dimensions=64)
    v = embedder.embed_document("normalised text")
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-6


def test_hashing_embedder_query_matches_document() -> None:
    embedder = HashingEmbedder(dimensions=64)
    doc_vec = embedder.embed_document("mining blast report")
    q_vec = embedder.embed_query("mining blast report")
    assert doc_vec == q_vec


def test_hashing_embedder_empty_string() -> None:
    embedder = HashingEmbedder(dimensions=32)
    v = embedder.embed_document("")
    assert v == [0.0] * 32


# Vector Store ----------------------------------------------------------------


def test_vector_store_index_and_search() -> None:
    vs = InMemoryVectorStore()
    embedder = HashingEmbedder(dimensions=32)
    vec = embedder.embed_document("mining operations")
    vs.index("c1", "doc-1", vec)
    assert vs.count() == 1
    hits = vs.search(vec, top_k=1)
    assert len(hits) == 1
    assert hits[0][0] == "c1"


def test_vector_store_delete() -> None:
    vs = InMemoryVectorStore()
    vs.index("c1", "doc-1", [0.0] * 8)
    assert vs.delete("c1") is True
    assert vs.count() == 0
    assert vs.delete("c1") is False


def test_vector_store_delete_document() -> None:
    vs = InMemoryVectorStore()
    vs.index("c1", "doc-1", [1.0, 0.0])
    vs.index("c2", "doc-1", [0.0, 1.0])
    vs.index("c3", "doc-2", [0.5, 0.5])
    removed = vs.delete_document("doc-1")
    assert removed == 2
    assert vs.count() == 1


# InMemoryKnowledgeStore -----------------------------------------------------


def test_store_add_and_search() -> None:
    embedder = HashingEmbedder(dimensions=32)
    store = InMemoryKnowledgeStore()
    doc = KnowledgeDocument(
        content="mining blast report analysis",
        source="t",
    )
    chunks = [KnowledgeChunk(document_id=doc.id, content="mining blast", index=0)]
    embs = {c.id: embedder.embed_document(c.content) for c in chunks}
    store.add_document(doc, chunks, embs)

    assert store.count() == 1
    q_emb = embedder.embed_query("mining")
    results = store.search(KnowledgeQuery(text="mining", top_k=1), embeddings=q_emb)
    assert len(results) == 1
    assert results[0].document.id == doc.id


def test_store_remove_document() -> None:
    store = InMemoryKnowledgeStore()
    doc = _short_doc()
    chunks = [KnowledgeChunk(document_id=doc.id, content="x", index=0)]
    store.add_document(doc, chunks)
    assert store.remove_document(doc.id) is True
    assert store.count() == 0


def test_store_list_documents() -> None:
    store = InMemoryKnowledgeStore()
    store.add_document(
        KnowledgeDocument(content="a", source="1"),
        [KnowledgeChunk(document_id="d1", content="a", index=0)],
    )
    store.add_document(
        KnowledgeDocument(content="b", source="2"),
        [KnowledgeChunk(document_id="d2", content="b", index=0)],
    )
    assert len(store.list_documents()) == 2


# Retriever -------------------------------------------------------------------


def test_retriever_returns_results() -> None:
    embedder = HashingEmbedder(dimensions=32)
    store = InMemoryKnowledgeStore()
    doc = KnowledgeDocument(
        content="atlas ai operating system",
        source="t",
        tags=["ai"],
    )
    chunks = [KnowledgeChunk(document_id=doc.id, content="atlas ai", index=0)]
    embs = {c.id: embedder.embed_document(c.content) for c in chunks}
    store.add_document(doc, chunks, embs)

    retriever = Retriever(store=store, embedder=embedder)
    results = retriever.retrieve(KnowledgeQuery(text="atlas", top_k=5))
    assert len(results) == 1
    assert results[0].chunk.content == "atlas ai"


def test_retriever_filters_by_tags() -> None:
    embedder = HashingEmbedder(dimensions=32)
    store = InMemoryKnowledgeStore()
    doc = KnowledgeDocument(
        content="mining report",
        source="t",
        tags=["mining", "geology"],
    )
    chunks = [
        KnowledgeChunk(document_id=doc.id, content="mining", index=0, tags=["mining"])
    ]
    embs = {c.id: embedder.embed_document(c.content) for c in chunks}
    store.add_document(doc, chunks, embs)

    retriever = Retriever(store=store, embedder=embedder)
    results = retriever.retrieve(KnowledgeQuery(text="mining", tags=["mining"]))
    assert len(results) == 1
    # Filter with a tag that doesn't match:
    results = retriever.retrieve(KnowledgeQuery(text="mining", tags=["biology"]))
    assert len(results) == 0


# Engine ----------------------------------------------------------------------


def test_engine_ingest_and_search() -> None:
    engine = KnowledgeEngine()
    doc = engine.ingest_text(
        content="Atlas provides persistent memory and governed principles.",
        source="identity.md",
        tags=["atlas"],
    )
    assert doc.id

    results = engine.search("persistent memory", top_k=5)
    assert len(results) >= 1


def test_engine_count() -> None:
    engine = KnowledgeEngine()
    assert engine.count() == 0
    engine.ingest_text("Hello world", source="test.txt")
    assert engine.count() == 1


def test_engine_remove() -> None:
    engine = KnowledgeEngine()
    doc = engine.ingest_text("Temporary data", source="tmp.txt")
    assert engine.remove(doc.id) is True
    assert engine.count() == 0


def test_engine_chunks_of() -> None:
    engine = KnowledgeEngine()
    doc = engine.ingest_text("a" * 600, source="big.txt")
    chunks = engine.chunks_of(doc.id)
    assert len(chunks) >= 2


def test_engine_ingest_file(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text(
        "Mining operations in Tanzania.", encoding="utf-8"
    )
    engine = KnowledgeEngine()
    doc = engine.ingest_file(tmp_path / "notes.txt", tags=["mining"])
    assert doc.content_type == "text/plain"
    results = engine.search("mining")
    assert len(results) >= 1


def test_engine_end_to_end_multiple_docs() -> None:
    engine = KnowledgeEngine()
    engine.ingest_text(
        "Blast design in open-pit mining", source="blast.txt", tags=["mining"]
    )
    engine.ingest_text(
        "Python async programming guide", source="python.md", tags=["programming"]
    )
    engine.ingest_text("Neural network architectures", source="ai.txt", tags=["ai"])

    assert engine.count() == 3

    mining_results = engine.search("mining blast", top_k=2)
    assert len(mining_results) >= 1

    python_results = engine.search("async programming", top_k=2)
    assert len(python_results) >= 1
