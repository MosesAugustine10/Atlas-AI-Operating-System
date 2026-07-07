"""Tests for the Atlas Memory Engine.

Covers models, storage injection, working memory CRUD, episodic logging,
reflection storage, and engine orchestration.
"""

from __future__ import annotations

from atlas.memory.engine import MemoryEngine
from atlas.memory.episodic import EpisodicMemory
from atlas.memory.models import (
    MemoryCategory,
    MemoryEntry,
    MemoryPriority,
    MemoryQuery,
)
from atlas.memory.procedural import ProceduralMemory
from atlas.memory.reflection import ReflectionMemory
from atlas.memory.semantic import SemanticMemory
from atlas.memory.storage import MemoryStorage
from atlas.memory.working import WorkingMemory

# ---------------------------------------------------------------------------
# MemoryEntry & MemoryQuery models
# ---------------------------------------------------------------------------


def test_entry_construction_defaults() -> None:
    entry = MemoryEntry(content="hello")
    assert entry.category is MemoryCategory.WORKING
    assert entry.content == "hello"
    assert entry.tags == []
    assert entry.priority is MemoryPriority.NORMAL
    assert entry.id
    assert entry.timestamp


def test_entry_tag_matching() -> None:
    entry = MemoryEntry(tags=["mining", "blast"])
    assert entry.matches_tag("mining")
    assert not entry.matches_tag("github")


def test_query_defaults() -> None:
    q = MemoryQuery()
    assert q.text == ""
    assert q.tags == []
    assert q.category is None
    assert q.limit == 20


# ---------------------------------------------------------------------------
# Storage interface — a minimal in-memory stub for injection tests
# ---------------------------------------------------------------------------


class _InMemoryStorage(MemoryStorage):
    """Minimal concrete storage for testing injection."""

    def __init__(self) -> None:
        super().__init__(name="test")
        self._data: dict[str, MemoryEntry] = {}

    def store(self, entry: MemoryEntry) -> MemoryEntry:
        self._data[entry.id] = entry
        return entry

    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        return self._data.get(entry_id)

    def query(self, query: MemoryQuery) -> list[MemoryEntry]:  # noqa: ARG002
        return list(self._data.values())

    def delete(self, entry_id: str) -> bool:
        return self._data.pop(entry_id, None) is not None

    def update(self, entry_id: str, **fields: object) -> MemoryEntry | None:
        entry = self._data.get(entry_id)
        if entry is None:
            return None
        for k, v in fields.items():
            setattr(entry, k, v)
        return entry

    def count(self, category: str | None = None) -> int:
        if category is None:
            return len(self._data)
        return sum(1 for e in self._data.values() if e.category.value == category)


def test_storage_injection() -> None:
    storage = _InMemoryStorage()
    assert storage.count() == 0
    entry = MemoryEntry(content="test")
    storage.store(entry)
    assert storage.count() == 1
    assert storage.retrieve(entry.id) is entry
    assert storage.delete(entry.id) is True
    assert storage.count() == 0


# ---------------------------------------------------------------------------
# Working memory CRUD
# ---------------------------------------------------------------------------


def test_working_memory_store_and_retrieve() -> None:
    wm = WorkingMemory()
    entry = wm.store(content="task context", tags=["session"])
    assert entry.id
    retrieved = wm.retrieve(entry.id)
    assert retrieved is not None
    assert retrieved.content == "task context"


def test_working_memory_delete() -> None:
    wm = WorkingMemory()
    entry = wm.store(content="temporary")
    assert wm.delete(entry.id) is True
    assert wm.retrieve(entry.id) is None
    assert wm.delete(entry.id) is False


def test_working_memory_query_by_tag() -> None:
    wm = WorkingMemory()
    wm.store(content="a", tags=["red"])
    wm.store(content="b", tags=["blue"])
    results = wm.query(MemoryQuery(tags=["red"]))
    assert len(results) == 1
    assert results[0].content == "a"


def test_working_memory_query_by_text() -> None:
    wm = WorkingMemory()
    wm.store(content="the quick fox")
    wm.store(content="slow turtle")
    results = wm.query(MemoryQuery(text="quick"))
    assert len(results) == 1


def test_working_memory_clear() -> None:
    wm = WorkingMemory()
    wm.store(content="x")
    wm.store(content="y")
    wm.clear()
    assert wm.query(MemoryQuery()) == []


def test_working_memory_capacity_eviction() -> None:
    wm = WorkingMemory(capacity=2)
    first = wm.store(content="first")
    wm.store(content="second")
    wm.store(content="third")  # should evict "first"
    assert wm.retrieve(first.id) is None
    assert wm.query(MemoryQuery())  # two remain


def test_working_memory_with_storage_injection() -> None:
    storage = _InMemoryStorage()
    wm = WorkingMemory(storage=storage)
    entry = wm.store(content="persisted")
    assert storage.retrieve(entry.id) is entry


# ---------------------------------------------------------------------------
# Episodic memory logging
# ---------------------------------------------------------------------------


def test_episodic_store_and_retrieve() -> None:
    em = EpisodicMemory()
    entry = em.store(content="user asked about mining", tags=["conversation"])
    assert entry.category is MemoryCategory.EPISODIC
    assert em.retrieve(entry.id) is not None


def test_episodic_recent_returns_newest_first() -> None:
    em = EpisodicMemory()
    em.store(content="first")
    em.store(content="second")
    em.store(content="third")
    recent = em.recent(count=2)
    assert len(recent) == 2
    assert recent[0].content == "third"
    assert recent[1].content == "second"


def test_episodic_delete() -> None:
    em = EpisodicMemory()
    entry = em.store(content="log this")
    assert em.delete(entry.id) is True
    assert em.retrieve(entry.id) is None


# ---------------------------------------------------------------------------
# Semantic, Procedural stores (basic CRUD)
# ---------------------------------------------------------------------------


def test_semantic_store_and_query() -> None:
    sm = SemanticMemory()
    sm.store(content="Python is a programming language", tags=["programming"])
    results = sm.query(MemoryQuery(tags=["programming"]))
    assert len(results) == 1


def test_procedural_store_and_query() -> None:
    pm = ProceduralMemory()
    pm.store(content="git commit -m 'msg'", tags=["git", "workflow"])
    results = pm.query(MemoryQuery(text="git commit"))
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Reflection memory
# ---------------------------------------------------------------------------


def test_reflection_store_and_retrieve() -> None:
    rm = ReflectionMemory()
    entry = rm.store(
        content="Should double-check facts before answering",
        tags=["lesson"],
    )
    assert rm.retrieve(entry.id) is not None
    assert entry.category is MemoryCategory.REFLECTION


def test_reflection_lessons() -> None:
    rm = ReflectionMemory()
    rm.store(content="always verify", tags=["lesson", "accuracy"])
    rm.store(content="be concise", tags=["lesson", "style"])
    lessons = rm.lessons(tags=["lesson"])
    assert len(lessons) == 2


def test_reflection_newest_first() -> None:
    rm = ReflectionMemory()
    rm.store(content="old lesson")
    rm.store(content="new lesson")
    lessons = rm.lessons()
    assert lessons[0].content == "new lesson"


# ---------------------------------------------------------------------------
# MemoryEngine orchestration
# ---------------------------------------------------------------------------


def test_engine_has_all_five_stores() -> None:
    engine = MemoryEngine()
    assert isinstance(engine.working, WorkingMemory)
    assert isinstance(engine.episodic, EpisodicMemory)
    assert isinstance(engine.semantic, SemanticMemory)
    assert isinstance(engine.procedural, ProceduralMemory)
    assert isinstance(engine.reflection, ReflectionMemory)


def test_engine_remember_delegates_to_correct_store() -> None:
    engine = MemoryEngine()
    entry = engine.remember("daily standup notes", category=MemoryCategory.EPISODIC)
    assert engine.episodic.retrieve(entry.id) is not None
    assert engine.working.retrieve(entry.id) is None


def test_engine_recall_specific_category() -> None:
    engine = MemoryEngine()
    engine.remember("fact", category=MemoryCategory.SEMANTIC, tags=["ai"])
    results = engine.recall(MemoryQuery(category=MemoryCategory.SEMANTIC, tags=["ai"]))
    assert len(results) == 1


def test_engine_recall_across_all_stores() -> None:
    engine = MemoryEngine()
    engine.remember("working note", category=MemoryCategory.WORKING)
    engine.remember("episode", category=MemoryCategory.EPISODIC)
    engine.remember("fact", category=MemoryCategory.SEMANTIC)
    results = engine.recall(MemoryQuery(limit=10))
    assert len(results) == 3


def test_engine_forget() -> None:
    engine = MemoryEngine()
    entry = engine.remember("to be forgotten", category=MemoryCategory.WORKING)
    assert engine.forget(entry.id) is True
    assert engine.working.retrieve(entry.id) is None


def test_engine_forget_unknown_returns_false() -> None:
    engine = MemoryEngine()
    assert engine.forget("nonexistent") is False


def test_engine_with_storage_injection() -> None:
    storage = _InMemoryStorage()
    engine = MemoryEngine(storage=storage)
    entry = engine.remember("persistent note", category=MemoryCategory.WORKING)
    assert storage.retrieve(entry.id) is entry


def test_engine_store_for() -> None:
    engine = MemoryEngine()
    store = engine.store_for(MemoryCategory.REFLECTION)
    assert isinstance(store, ReflectionMemory)
