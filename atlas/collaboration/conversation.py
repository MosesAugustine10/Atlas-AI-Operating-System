"""Conversation — multi-agent conversation threads with turn-taking.

The :class:`ConversationManager` owns :class:`Conversation` and
:class:`Turn` instances. Agents take turns producing messages of
various kinds (proposal, question, answer, agreement, etc.).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from atlas.collaboration.models import (
    Conversation,
    Turn,
    TurnKind,
    TurnStatus,
    _new_id,
    _utcnow,
)


class ConversationError(RuntimeError):
    """Raised when a conversation operation fails."""


class ConversationManager:
    """Manages conversations and turns."""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def create(
        self,
        session_id: str,
        topic: str = "",
        participant_ids: tuple[str, ...] = (),
    ) -> Conversation:
        """Create a new conversation."""
        conv = Conversation(
            id=_new_id("conv"),
            session_id=session_id,
            topic=topic,
            participant_ids=participant_ids,
        )
        self._conversations[conv.id] = conv
        return conv

    def get(self, conversation_id: str) -> Conversation | None:
        """Return the conversation with ``conversation_id`` or ``None``."""
        return self._conversations.get(conversation_id)

    def list_conversations(
        self,
        session_id: str | None = None,
    ) -> list[Conversation]:
        """List conversations, optionally filtered by session."""
        convs = list(self._conversations.values())
        if session_id is not None:
            convs = [c for c in convs if c.session_id == session_id]
        convs.sort(key=lambda c: c.created_at, reverse=True)
        return convs

    def close(self, conversation_id: str) -> Conversation:
        """Close a conversation."""
        conv = self._require(conversation_id)
        return self._update(conversation_id, closed_at=_utcnow())

    # ------------------------------------------------------------------
    # Turns
    # ------------------------------------------------------------------

    def add_turn(
        self,
        conversation_id: str,
        agent_id: str,
        content: str = "",
        kind: str = TurnKind.INFO.value,
        reply_to: str = "",
    ) -> Turn:
        """Add a turn to a conversation and return it."""
        conv = self._require(conversation_id)
        turn = Turn(
            id=_new_id("turn"),
            session_id=conv.session_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            kind=kind,
            content=content,
            status=TurnStatus.COMPLETED.value,
            reply_to=reply_to,
            completed_at=_utcnow(),
        )
        turns = tuple(list(conv.turns) + [turn])
        self._update(conversation_id, turns=turns)
        return turn

    def list_turns(
        self,
        conversation_id: str,
        kind: str | None = None,
        agent_id: str | None = None,
    ) -> list[Turn]:
        """Return turns in a conversation, optionally filtered."""
        conv = self._require(conversation_id)
        turns = list(conv.turns)
        if kind is not None:
            turns = [t for t in turns if t.kind == kind]
        if agent_id is not None:
            turns = [t for t in turns if t.agent_id == agent_id]
        return turns

    def turn_count(self, conversation_id: str) -> int:
        """Return the number of turns in a conversation."""
        conv = self._conversations.get(conversation_id)
        return len(conv.turns) if conv else 0

    def last_turn(self, conversation_id: str) -> Turn | None:
        """Return the most recent turn in a conversation, or ``None``."""
        turns = self.list_turns(conversation_id)
        return turns[-1] if turns else None

    def replies(self, turn_id: str) -> list[Turn]:
        """Return all turns that reply to ``turn_id``."""
        results: list[Turn] = []
        for conv in self._conversations.values():
            for turn in conv.turns:
                if turn.reply_to == turn_id:
                    results.append(turn)
        return results

    def thread(self, turn_id: str) -> list[Turn]:
        """Return the thread rooted at ``turn_id`` (BFS)."""
        root: Turn | None = None
        for conv in self._conversations.values():
            for turn in conv.turns:
                if turn.id == turn_id:
                    root = turn
                    break
            if root:
                break
        if root is None:
            return []
        thread = [root]
        pending = [turn_id]
        while pending:
            current = pending.pop(0)
            for reply in self.replies(current):
                thread.append(reply)
                pending.append(reply.id)
        return thread

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def turns_by_agent(
        self,
        conversation_id: str,
    ) -> dict[str, int]:
        """Return a ``{agent_id: turn_count}`` dict."""
        turns = self.list_turns(conversation_id)
        counts: dict[str, int] = {}
        for t in turns:
            counts[t.agent_id] = counts.get(t.agent_id, 0) + 1
        return counts

    def count_by_kind(
        self,
        conversation_id: str,
    ) -> dict[str, int]:
        """Return a dict of turn counts by kind."""
        turns = self.list_turns(conversation_id)
        counts: dict[str, int] = {}
        for t in turns:
            counts[t.kind] = counts.get(t.kind, 0) + 1
        return counts

    def conversation_count(self) -> int:
        """Return the total number of conversations."""
        return len(self._conversations)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, conversation_id: str) -> Conversation:
        conv = self._conversations.get(conversation_id)
        if conv is None:
            raise ConversationError(f"conversation {conversation_id} not found")
        return conv

    def _update(self, conversation_id: str, **changes: Any) -> Conversation:
        conv = self._conversations[conversation_id]
        updated = dataclasses.replace(conv, **changes)
        self._conversations[conversation_id] = updated
        return updated


__all__ = ["ConversationError", "ConversationManager"]
