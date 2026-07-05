"""Live provider adapter — real LLM execution via MCP connectors.

Wraps the MCP :class:`OllamaConnector` and :class:`OpenRouterConnector`
as :class:`BaseProvider` implementations so the existing
:class:`ProviderManager` can route to real LLMs without changing its
contract.

The adapter is **dependency-injected**: it accepts an optional
:class:`MCPManager` and resolves connectors from it. If the MCP manager
is not supplied, the adapter constructs standalone connectors.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from atlas.core.logger import get_logger
from atlas.providers.base import BaseProvider
from atlas.providers.models import (
    ProviderCapability,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class OllamaProvider(BaseProvider):
    """Real :class:`BaseProvider` backed by the Ollama MCP connector.

    Parameters:
        mcp_manager: Optional :class:`MCPManager` with a registered
            ``ollama`` connector. If ``None``, a standalone
            :class:`OllamaConnector` is constructed.
        base_url: Ollama server URL (used when ``mcp_manager`` is None).
        default_model: Default model name.
    """

    def __init__(
        self,
        mcp_manager: Any = None,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
    ) -> None:
        info = ProviderInfo(
            name="ollama",
            display_name="Ollama (Local LLM)",
            base_url=base_url,
            priority=5,
            cost_per_1k=0.0,
            capabilities=ProviderCapability(
                streaming=True,
                tools=False,
                images=False,
                system_prompt=True,
            ),
        )
        super().__init__(info=info)
        self._mcp = mcp_manager
        self._default_model = default_model
        self._standalone: Any = None
        if mcp_manager is None:
            from atlas.mcp.connectors.ollama import OllamaConnector

            self._standalone = OllamaConnector(base_url=base_url)
            self._standalone.connect()
        self._logger = get_logger("live.provider.ollama")

    def _execute(self, capability: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an Ollama MCP capability."""
        if self._mcp is not None:
            session = self._mcp.open_session("ollama", permissions=["read"])
            try:
                resp = self._mcp.execute_capability(
                    capability,
                    params,
                    connector="ollama",
                    session_id=session.id,
                )
                if not resp.success:
                    raise RuntimeError(resp.error or "ollama capability failed")
                return resp.output
            finally:
                self._mcp.close_session(session.id)
        else:
            from atlas.mcp.models import MCPRequest

            req = MCPRequest(connector="ollama", capability=capability, params=params)
            resp = self._standalone.execute(req)
            if not resp.success:
                raise RuntimeError(resp.error or "ollama capability failed")
            return resp.output

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate text via the Ollama API."""
        model = request.model if request.model != "default" else self._default_model
        output = self._execute(
            "ollama.generate",
            {
                "model": model,
                "prompt": request.prompt,
            },
        )
        return ProviderResponse(
            text=output.get("response", ""),
            model=model,
            provider="ollama",
            finish_reason="stop",
            usage=output.get("usage", {}),
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        """Stream text via Ollama (placeholder — returns one chunk)."""
        yield self.generate(request)

    def health(self) -> bool:
        """Check Ollama server health."""
        try:
            output = self._execute("ollama.health", {})
            return output.get("available", False)
        except Exception:  # noqa: BLE001
            return False

    def available_models(self) -> list[str]:
        """List available Ollama models."""
        try:
            output = self._execute("ollama.models", {})
            return output.get("models", [])
        except Exception:  # noqa: BLE001
            return []


class OpenRouterProvider(BaseProvider):
    """Real :class:`BaseProvider` backed by the OpenRouter MCP connector."""

    def __init__(
        self,
        mcp_manager: Any = None,
        api_key: str | None = None,
        default_model: str = "openai/gpt-4o-mini",
    ) -> None:
        info = ProviderInfo(
            name="openrouter",
            display_name="OpenRouter (Multi-model Gateway)",
            base_url="https://openrouter.ai/api/v1",
            priority=10,
            cost_per_1k=0.002,
            capabilities=ProviderCapability(
                streaming=True,
                tools=True,
                images=True,
                system_prompt=True,
            ),
        )
        super().__init__(info=info)
        self._mcp = mcp_manager
        self._default_model = default_model
        self._standalone: Any = None
        if mcp_manager is None:
            import os

            from atlas.mcp.connectors.openrouter import OpenRouterConnector

            key = api_key or os.environ.get("OPENROUTER_API_KEY")
            self._standalone = OpenRouterConnector(api_key=key)
            self._standalone.connect()
        self._logger = get_logger("live.provider.openrouter")

    def _execute(self, capability: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an OpenRouter MCP capability."""
        if self._mcp is not None:
            session = self._mcp.open_session("openrouter", permissions=["read"])
            try:
                resp = self._mcp.execute_capability(
                    capability,
                    params,
                    connector="openrouter",
                    session_id=session.id,
                )
                if not resp.success:
                    raise RuntimeError(resp.error or "openrouter capability failed")
                return resp.output
            finally:
                self._mcp.close_session(session.id)
        else:
            from atlas.mcp.models import MCPRequest

            req = MCPRequest(
                connector="openrouter", capability=capability, params=params
            )
            resp = self._standalone.execute(req)
            if not resp.success:
                raise RuntimeError(resp.error or "openrouter capability failed")
            return resp.output

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate text via the OpenRouter API."""
        model = request.model if request.model != "default" else self._default_model
        output = self._execute(
            "openrouter.generate",
            {
                "model": model,
                "prompt": request.prompt,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
        )
        return ProviderResponse(
            text=output.get("response", ""),
            model=model,
            provider="openrouter",
            finish_reason="stop",
            usage=output.get("usage", {}),
        )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        """Stream text via OpenRouter (placeholder — returns one chunk)."""
        yield self.generate(request)

    def health(self) -> bool:
        """Check OpenRouter API health."""
        try:
            output = self._execute("openrouter.health", {})
            return output.get("available", False)
        except Exception:  # noqa: BLE001
            return False

    def available_models(self) -> list[str]:
        """List available OpenRouter models."""
        try:
            output = self._execute("openrouter.models", {})
            return output.get("models", [])
        except Exception:  # noqa: BLE001
            return []


class ZAIProvider(BaseProvider):
    """Real :class:`BaseProvider` backed by the Z.ai API.

    The Z.ai provider is a lightweight wrapper that calls the Z.ai
    HTTP API directly. If the ``ZAI_API_KEY`` environment variable is
    not set, the provider degrades gracefully and returns a placeholder
    response.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.z.ai/v1",
        default_model: str = "glm-4",
    ) -> None:
        import os

        info = ProviderInfo(
            name="zai",
            display_name="Z.ai (Built-in LLM)",
            base_url=base_url,
            priority=1,
            cost_per_1k=0.001,
            capabilities=ProviderCapability(
                streaming=True,
                tools=True,
                images=False,
                system_prompt=True,
            ),
        )
        super().__init__(info=info)
        self._api_key = api_key or os.environ.get("ZAI_API_KEY")
        self._base_url = base_url
        self._default_model = default_model
        self._logger = get_logger("live.provider.zai")

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Generate text via the Z.ai API."""
        if not self._api_key:
            return ProviderResponse(
                text="[Z.ai placeholder: set ZAI_API_KEY to enable real generation]",
                model=request.model,
                provider="zai",
                finish_reason="stop",
                usage={"prompt_tokens": 0, "completion_tokens": 0},
            )
        try:
            import requests

            model = request.model if request.model != "default" else self._default_model
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": request.prompt}],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage = data.get("usage", {})
            return ProviderResponse(
                text=message.get("content", ""),
                model=model,
                provider="zai",
                finish_reason=choice.get("finish_reason", "stop"),
                usage=usage,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Z.ai generate failed: %s", exc)
            return ProviderResponse(
                text=f"[Z.ai error: {exc}]",
                model=request.model,
                provider="zai",
                finish_reason="error",
                usage={},
            )

    def stream(self, request: ProviderRequest) -> Iterator[ProviderResponse]:
        """Stream text via Z.ai (placeholder — returns one chunk)."""
        yield self.generate(request)

    def health(self) -> bool:
        """Check Z.ai API health."""
        return self._api_key is not None

    def available_models(self) -> list[str]:
        """List available Z.ai models."""
        return ["glm-4", "glm-4-flash", "glm-4v"]


def create_live_providers(
    mcp_manager: Any = None,
) -> list[BaseProvider]:
    """Create a list of live provider instances.

    Returns a list of :class:`OllamaProvider`, :class:`OpenRouterProvider`,
    and :class:`ZAIProvider` instances. The list can be registered with
    a :class:`ProviderManager`.
    """
    return [
        ZAIProvider(),
        OllamaProvider(mcp_manager=mcp_manager),
        OpenRouterProvider(mcp_manager=mcp_manager),
    ]


def register_live_providers(
    manager: Any,
    mcp_manager: Any = None,
) -> Any:
    """Register live providers with a :class:`ProviderManager`.

    The ZAI provider is made the default. Returns the manager for
    chaining.
    """
    providers = create_live_providers(mcp_manager=mcp_manager)
    for provider in providers:
        make_default = provider.name == "zai"
        manager.register(provider, make_default=make_default)
    return manager


__all__ = [
    "OllamaProvider",
    "OpenRouterProvider",
    "ZAIProvider",
    "create_live_providers",
    "register_live_providers",
]
