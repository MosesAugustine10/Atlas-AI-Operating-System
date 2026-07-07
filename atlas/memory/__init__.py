"""The Atlas Memory Engine.

A layered memory framework providing five specialised stores — working,
episodic, semantic, procedural, and reflection — orchestrated by a single
:class:`MemoryEngine`. Every store shares a common :class:`BaseMemory`
contract and can optionally be backed by a swappable :class:`MemoryStorage`
persistence layer.

The dependency graph is acyclic:

* ``models`` — pure dataclasses (leaf).
* ``storage`` — abstract persistence contract.
* ``base`` — abstract memory-store contract.
* ``working / episodic / semantic / procedural / reflection`` — concrete stores.
* ``engine`` — orchestrator that owns all stores.
"""

from __future__ import annotations

from atlas.memory.base import BaseMemory
from atlas.memory.engine import MemoryEngine
from atlas.memory.episodic import EpisodicMemory
from atlas.memory.models import MemoryCategory, MemoryEntry, MemoryPriority, MemoryQuery
from atlas.memory.procedural import ProceduralMemory
from atlas.memory.reflection import ReflectionMemory
from atlas.memory.semantic import SemanticMemory
from atlas.memory.storage import MemoryStorage
from atlas.memory.working import WorkingMemory

__all__ = [
    "BaseMemory",
    "EpisodicMemory",
    "MemoryCategory",
    "MemoryEngine",
    "MemoryEntry",
    "MemoryPriority",
    "MemoryQuery",
    "MemoryStorage",
    "ProceduralMemory",
    "ReflectionMemory",
    "SemanticMemory",
    "WorkingMemory",
]
