"""Provider data models for the Atlas Provider Layer.

Pure immutable dataclasses representing requests to, and responses from,
any LLM provider. These are leaf nodes — they hold data and construction
helpers only, with no dependencies on the rest of the providers package.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _uuid() -> str:
    """Return a new unique identifier."""
    return uuid.uuid4().hex


class MessageRole(enum.StrEnum):
    """Role of a message in a chat conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class Message:
    """A single chat message.

    Attributes:
        role: The speaker role (system, user, assistant, tool).
        content: The message text.
        name: Optional name for the speaker (used for tool calls).
    """

    role: MessageRole
    content: str
    name: str | None = None


@dataclass(frozen=True)
class ProviderCapability:
    """Declares what a provider can do.

    Attributes:
        streaming: Whether the provider supports token streaming.
        tools: Whether the provider supports tool/function calling.
        images: Whether the provider supports image inputs.
        system_prompt: Whether the provider honours a system message.
    """

    streaming: bool = False
    tools: bool = False
    images: bool = False
    system_prompt: bool = True


@dataclass(frozen=True)
class ProviderInfo:
    """Static metadata describing a provider.

    Attributes:
        name: Unique provider identifier (e.g. ``"openai"``).
        display_name: Human-readable name.
        base_url: Default API base URL (if applicable).
        priority: Routing priority — lower is preferred.
        cost_per_1k: Relative cost per 1k tokens (arbitrary scale).
        capabilities: Declared :class:`ProviderCapability`.
    """

    name: str
    display_name: str
    base_url: str | None = None
    priority: int = 100
    cost_per_1k: float = 0.0
    capabilities: ProviderCapability = field(default_factory=ProviderCapability)


@dataclass(frozen=True)
class ProviderRequest:
    """A request to an LLM provider.

    Attributes:
        prompt: The prompt text (for completion-style calls).
        messages: The chat message list (for chat-style calls).
        model: The specific model to use (provider-specific string).
        temperature: Sampling temperature (0.0–2.0).
        max_tokens: Maximum tokens to generate.
        tools: Optional tool schemas the model may call.
        images: Optional image inputs (base64 or URLs).
        streaming: Whether to stream the response.
        metadata: Free-form bag for tracing, request ids, etc.
    """

    prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 1024
    tools: list[dict[str, Any]] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    streaming: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class ProviderResponse:
    """A response from an LLM provider.

    Attributes:
        text: The generated text.
        model: The model that produced this response.
        provider: The provider name that produced this response.
        finish_reason: Why generation stopped (``stop``, ``length``, etc.).
        usage: Token usage breakdown (``prompt``, ``completion``, ``total``).
        metadata: Free-form bag for latency, raw payload, etc.
    """

    text: str
    model: str
    provider: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_utcnow)
