"""Chat controller — manages chat messages and provider/agent dispatch.

The :class:`ChatController` is the ViewModel-layer bridge between the
Chat page and the underlying Atlas execution/providing subsystems. It
holds the conversation state (messages, streaming flag, selected
provider/agent) and dispatches ``send`` calls through *injected*
subsystems via duck typing.

All injected subsystems are optional (``None`` default). When every
subsystem is ``None`` the controller still works — :meth:`send` simply
returns a placeholder response so the UI can render an empty state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def _is_runnable(obj: Any) -> bool:
    """Return ``True`` if ``obj`` exposes a ``run`` or ``execute`` method."""
    return hasattr(obj, "run") or hasattr(obj, "execute")


class ChatController:
    """ViewModel for the Chat page.

    Parameters:
        brain: Optional high-level Atlas brain / execution object. If it
            exposes a ``run`` (or ``execute``) callable it is used as the
            fallback when no provider manager is wired.
        providers: Optional :class:`~atlas.providers.manager.ProviderManager`
            -like object exposing a ``chat`` method.
        agent_registry: Optional agent registry / dict whose values expose
            ``run`` or ``execute``.
    """

    def __init__(
        self,
        brain: Any = None,
        providers: Any = None,
        agent_registry: Any = None,
    ) -> None:
        self._brain = brain
        self._providers = providers
        self._agents = agent_registry
        #: Ordered conversation history. Each entry is a dict with
        #: ``role`` (``user`` | ``assistant`` | ``system``), ``content``
        #: and ``timestamp`` keys.
        self.messages: list[dict[str, Any]] = []
        self.streaming: bool = False
        self.provider: str | None = None
        self.agent: str | None = None

    # ------------------------------------------------------------------
    # Conversation lifecycle
    # ------------------------------------------------------------------

    def send(self, text: str) -> str:
        """Send ``text`` to the active provider/agent and store the reply.

        The user message is appended immediately and ``streaming`` is set
        to ``True`` for the duration of the call. The assistant reply is
        appended on completion. Returns the assistant reply text.

        If no subsystem is wired in, a placeholder reply is produced so
        the UI can still render a turn.
        """
        if not text:
            return ""
        self.messages.append({"role": "user", "content": text, "timestamp": _utcnow()})
        self.streaming = True
        reply = self._dispatch(text)
        self.streaming = False
        self.messages.append(
            {"role": "assistant", "content": reply, "timestamp": _utcnow()}
        )
        return reply

    def stop(self) -> None:
        """Signal that the current stream should stop."""
        self.streaming = False

    def retry(self) -> str:
        """Re-send the most recent user message.

        Removes the last assistant reply (if any) and re-dispatches the
        last user message. Returns the new reply, or ``""`` if there is
        nothing to retry.
        """
        # Drop a trailing assistant turn so we can re-derive a reply.
        while self.messages and self.messages[-1]["role"] == "assistant":
            self.messages.pop()
        if not self.messages or self.messages[-1]["role"] != "user":
            return ""
        last_user = self.messages[-1]["content"]
        # Pop the user message so :meth:`send` re-appends it cleanly.
        self.messages.pop()
        return self.send(last_user)

    def clear(self) -> None:
        """Remove every message from the conversation."""
        self.messages.clear()
        self.streaming = False

    # ------------------------------------------------------------------
    # Export & selection
    # ------------------------------------------------------------------

    def export(self) -> list[dict[str, Any]]:
        """Return a plain-list copy of the conversation.

        Timestamps are serialised as ISO-8601 strings so the result is
        JSON-friendly.
        """
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": (
                    msg["timestamp"].isoformat()
                    if isinstance(msg["timestamp"], datetime)
                    else str(msg["timestamp"])
                ),
            }
            for msg in self.messages
        ]

    def set_provider(self, name: str | None) -> None:
        """Select the provider to route ``send`` calls through."""
        self.provider = name

    def set_agent(self, name: str | None) -> None:
        """Select the agent to dispatch ``send`` calls through."""
        self.agent = name

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, text: str) -> str:
        """Try each wired subsystem in priority order and return a reply."""
        # 1. Provider manager (preferred path).
        if self._providers is not None and hasattr(self._providers, "chat"):
            try:
                messages = self._build_provider_messages()
                result = self._providers.chat(messages, provider=self.provider or None)
                return self._extract_text(result)
            except Exception as exc:  # noqa: BLE001 — keep UI responsive
                return f"[provider error: {exc}]"

        # 2. Explicit agent selection.
        if self.agent is not None and self._agents is not None:
            agent = self._lookup_agent(self.agent)
            if agent is not None and _is_runnable(agent):
                try:
                    return str(self._call_runnable(agent, text))
                except Exception as exc:  # noqa: BLE001
                    return f"[agent error: {exc}]"

        # 3. Brain fallback.
        if self._brain is not None and _is_runnable(self._brain):
            try:
                return str(self._call_runnable(self._brain, text))
            except Exception as exc:  # noqa: BLE001
                return f"[brain error: {exc}]"

        # 4. Nothing wired in.
        return "[no provider or agent available — wire a subsystem into ChatController]"

    def _build_provider_messages(self) -> list[Any]:
        """Build the message list expected by ``ProviderManager.chat``.

        Uses :class:`atlas.providers.models.Message` when importable;
        otherwise falls back to simple ``{"role": ..., "content": ...}``
        dicts (duck-typed providers should accept either).
        """
        try:
            from atlas.providers.models import Message  # lazy import
        except Exception:  # noqa: BLE001
            return [
                {"role": m["role"], "content": m["content"]}
                for m in self.messages
                if m["role"] in ("system", "user", "assistant")
            ]
        return [
            Message(role=m["role"], content=m["content"])
            for m in self.messages
            if m["role"] in ("system", "user", "assistant")
        ]

    def _lookup_agent(self, name: str) -> Any:
        """Resolve ``name`` against the injected agent registry."""
        agents = self._agents
        if agents is None:
            return None
        # Mapping-like registry.
        try:
            if hasattr(agents, "__getitem__"):
                return agents[name]
        except (KeyError, IndexError, TypeError):
            pass
        # Iterable registry of agent objects with a ``name`` attribute.
        all_agents = agents.all() if hasattr(agents, "all") else []
        for agent in all_agents:
            if getattr(agent, "name", None) == name:
                return agent
        # Object with a get(name) helper.
        getter = getattr(agents, "get", None)
        if callable(getter):
            try:
                return getter(name)
            except Exception:  # noqa: BLE001
                return None
        return None

    @staticmethod
    def _call_runnable(runnable: Any, text: str) -> Any:
        """Invoke ``runnable.run`` / ``runnable.execute`` with ``text``."""
        for method_name in ("run", "execute"):
            method = getattr(runnable, method_name, None)
            if callable(method):
                return method(text)
        return ""

    @staticmethod
    def _extract_text(result: Any) -> str:
        """Pull a human-readable string out of a provider/brain result."""
        if result is None:
            return ""
        for attr in ("text", "content", "response", "output"):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value:
                return value
        return str(result)

    def __repr__(self) -> str:
        return (
            f"<ChatController messages={len(self.messages)} "
            f"streaming={self.streaming} provider={self.provider!r}>"
        )


__all__ = ["ChatController"]
