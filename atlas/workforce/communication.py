"""Communication channel — worker-to-worker messaging.

The :class:`CommunicationChannel` is a pure-Python message broker
that routes :class:`~atlas.workforce.models.Message` instances between
workers. It supports direct messages, team broadcasts, reply threads,
and read tracking.

The channel never imports workers directly — it operates purely on
worker ids (strings), keeping the package decoupled.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from atlas.core.logger import get_logger
from atlas.workforce.models import (
    Message,
    MessageKind,
    _new_id,
)


class CommunicationChannel:
    """Routes messages between workers.

    Parameters:
        delivery_fn: Optional callback invoked when a message is
            delivered, with ``(message)``. Used for real-time UI
            notifications.
    """

    def __init__(
        self,
        delivery_fn: Callable[[Message], None] | None = None,
    ) -> None:
        self._messages: dict[str, Message] = {}
        self._delivery_fn = delivery_fn
        self.logger = get_logger("workforce.communication")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send(
        self,
        sender_id: str,
        recipient_id: str = "",
        team_id: str = "",
        kind: str = MessageKind.INFO.value,
        subject: str = "",
        body: str = "",
        task_id: str = "",
        reply_to: str = "",
    ) -> Message:
        """Send a message and return it.

        When ``recipient_id`` is empty, the message is a broadcast to
        all workers on ``team_id`` (or all workers if ``team_id`` is
        also empty).
        """
        msg = Message(
            id=_new_id("msg"),
            sender_id=sender_id,
            recipient_id=recipient_id,
            team_id=team_id,
            kind=kind,
            subject=subject,
            body=body,
            task_id=task_id,
            reply_to=reply_to,
        )
        self._messages[msg.id] = msg
        if self._delivery_fn is not None:
            try:
                self._delivery_fn(msg)
            except Exception as exc:  # noqa: BLE001 — delivery must not break send
                self.logger.warning("Delivery callback failed: %s", exc)
        return msg

    def broadcast(
        self,
        sender_id: str,
        team_id: str,
        subject: str,
        body: str,
        task_id: str = "",
    ) -> Message:
        """Broadcast a message to all workers on ``team_id``."""
        return self.send(
            sender_id=sender_id,
            recipient_id="",
            team_id=team_id,
            kind=MessageKind.BROADCAST.value,
            subject=subject,
            body=body,
            task_id=task_id,
        )

    def request(
        self,
        sender_id: str,
        recipient_id: str,
        subject: str,
        body: str,
        task_id: str = "",
    ) -> Message:
        """Send a request message."""
        return self.send(
            sender_id=sender_id,
            recipient_id=recipient_id,
            kind=MessageKind.REQUEST.value,
            subject=subject,
            body=body,
            task_id=task_id,
        )

    def respond(
        self,
        sender_id: str,
        recipient_id: str,
        reply_to: str,
        subject: str,
        body: str,
    ) -> Message:
        """Send a response message in reply to ``reply_to``."""
        return self.send(
            sender_id=sender_id,
            recipient_id=recipient_id,
            kind=MessageKind.RESPONSE.value,
            subject=subject,
            body=body,
            reply_to=reply_to,
        )

    def handoff(
        self,
        sender_id: str,
        recipient_id: str,
        task_id: str,
        notes: str = "",
    ) -> Message:
        """Send a task-handoff message."""
        return self.send(
            sender_id=sender_id,
            recipient_id=recipient_id,
            kind=MessageKind.HANDOFF.value,
            subject=f"Handoff: {task_id}",
            body=notes,
            task_id=task_id,
        )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get(self, message_id: str) -> Message | None:
        """Return the message with ``message_id`` or ``None``."""
        return self._messages.get(message_id)

    def inbox(
        self,
        worker_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Message]:
        """Return messages addressed to ``worker_id`` (newest first)."""
        msgs = [
            m
            for m in self._messages.values()
            if m.recipient_id == worker_id and (not unread_only or not m.read)
        ]
        msgs.sort(key=lambda m: m.timestamp, reverse=True)
        return msgs[:limit]

    def broadcasts_for(
        self,
        worker_id: str,
        team_ids: tuple[str, ...] = (),
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Message]:
        """Return broadcast messages relevant to ``worker_id``."""
        msgs = [
            m
            for m in self._messages.values()
            if m.kind == MessageKind.BROADCAST.value
            and (not team_ids or m.team_id in team_ids)
            and (not unread_only or not m.read)
        ]
        msgs.sort(key=lambda m: m.timestamp, reverse=True)
        return msgs[:limit]

    def sent_by(self, worker_id: str, limit: int = 50) -> list[Message]:
        """Return messages sent by ``worker_id`` (newest first)."""
        msgs = [m for m in self._messages.values() if m.sender_id == worker_id]
        msgs.sort(key=lambda m: m.timestamp, reverse=True)
        return msgs[:limit]

    def thread(self, root_message_id: str) -> list[Message]:
        """Return the message thread rooted at ``root_message_id``."""
        root = self._messages.get(root_message_id)
        if root is None:
            return []
        thread_msgs = [root]
        # Find all replies (BFS)
        pending = [root_message_id]
        while pending:
            current = pending.pop(0)
            replies = [m for m in self._messages.values() if m.reply_to == current]
            replies.sort(key=lambda m: m.timestamp)
            for r in replies:
                thread_msgs.append(r)
                pending.append(r.id)
        return thread_msgs

    def mark_read(self, message_id: str) -> Message | None:
        """Mark a message as read. Returns the updated message."""
        msg = self._messages.get(message_id)
        if msg is None:
            return None
        updated = dataclasses.replace(msg, read=True)
        self._messages[message_id] = updated
        return updated

    def mark_all_read(self, worker_id: str) -> int:
        """Mark all of ``worker_id``'s messages as read. Returns the count."""
        count = 0
        for mid, msg in list(self._messages.items()):
            if msg.recipient_id == worker_id and not msg.read:
                self._messages[mid] = dataclasses.replace(msg, read=True)
                count += 1
        return count

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def unread_count(self, worker_id: str) -> int:
        """Return the number of unread messages for ``worker_id``."""
        return sum(
            1
            for m in self._messages.values()
            if m.recipient_id == worker_id and not m.read
        )

    def message_count(self) -> int:
        """Return the total number of messages."""
        return len(self._messages)

    def count_by_kind(self) -> dict[str, int]:
        """Return a dict of message counts by kind."""
        counts: dict[str, int] = {}
        for m in self._messages.values():
            counts[m.kind] = counts.get(m.kind, 0) + 1
        return counts

    def all_messages(self, limit: int = 100) -> list[Message]:
        """Return all messages (newest first)."""
        msgs = sorted(self._messages.values(), key=lambda m: m.timestamp, reverse=True)
        return msgs[:limit]

    def clear(self) -> int:
        """Clear all messages. Returns the count cleared."""
        count = len(self._messages)
        self._messages.clear()
        return count

    def delete(self, message_id: str) -> bool:
        """Delete a message. Returns ``True`` if deleted."""
        return self._messages.pop(message_id, None) is not None


__all__ = ["CommunicationChannel"]
