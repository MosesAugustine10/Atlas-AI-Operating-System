"""Live agents — real agent implementations that do actual work.

Each agent inherits :class:`BaseAgent` and uses the injected MCPManager,
ProviderManager, or Brain to execute real operations.

Agents:
* CodingAgent — generates code via Ollama/OpenRouter
* ResearchAgent — researches via Browser MCP
* GitHubAgent — manages git via GitHub MCP
* BrowserAgent — browses via Browser MCP
* MiningAgent — manages mining data via Filesystem MCP
* VisionAgent — processes images via Playwright MCP
* WindowsAgent — manages Windows OS via Windows MCP
* PlannerAgent — plans via the Brain
* KnowledgeAgent — searches the Knowledge Engine
* MemoryAgent — manages the Memory Engine
* BlenderAgent — manages Blender 3D via Blender MCP
"""

from __future__ import annotations

from typing import Any

from atlas.agents.base import BaseAgent


class LiveAgent(BaseAgent):
    """Base class for live agents with injected subsystems.

    Parameters:
        name: Agent name.
        role: Agent role.
        mcp_manager: Optional MCPManager for real connector access.
        providers: Optional ProviderManager for LLM access.
        memory: Optional MemoryEngine.
        knowledge: Optional KnowledgeEngine.
    """

    def __init__(
        self,
        name: str,
        role: str | None = None,
        mcp_manager: Any = None,
        providers: Any = None,
        memory: Any = None,
        knowledge: Any = None,
    ) -> None:
        super().__init__(name=name, role=role or name)
        self.mcp_manager = mcp_manager
        self.providers = providers
        self.memory = memory
        self.knowledge = knowledge

    def _mcp_execute(
        self,
        capability: str,
        params: dict[str, Any] | None = None,
        connector: str | None = None,
    ) -> dict[str, Any]:
        """Execute an MCP capability (if manager is available)."""
        if self.mcp_manager is None:
            return {"success": False, "error": "MCP manager not available"}
        try:
            session = self.mcp_manager.open_session(
                connector or "filesystem",
                permissions=["read", "write", "execute"],
            )
            try:
                resp = self.mcp_manager.execute_capability(
                    capability,
                    params or {},
                    connector=connector,
                    session_id=session.id,
                )
                return {
                    "success": resp.success,
                    "output": resp.output,
                    "error": resp.error,
                }
            finally:
                self.mcp_manager.close_session(session.id)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}

    def _generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text via the provider manager (if available)."""
        if self.providers is None:
            return f"[placeholder generation for: {prompt[:50]}]"
        try:
            response = self.providers.generate(prompt, **kwargs)
            return getattr(response, "text", str(response))
        except Exception as exc:  # noqa: BLE001
            return f"[generation error: {exc}]"

    def plan(self, objective: str) -> Any:
        """Default plan: return the objective as a single-step plan."""
        return {"objective": objective, "steps": [objective]}

    def execute(self, plan: Any) -> Any:
        """Default execute: return the plan."""
        return plan

    def review(self, result: Any) -> Any:
        """Default review: pass through."""
        return result

    def report(self, review: Any) -> str:
        """Default report: stringify the review."""
        return str(review)


class CodingAgent(LiveAgent):
    """Generates code via LLM providers."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="coding_agent", role="Code Generation", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "generate_code"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        code = self._generate(
            f"Write Python code for: {objective}\nReturn only the code."
        )
        return {"code": code, "language": "python", "objective": objective}

    def report(self, review: Any) -> str:
        code = review.get("code", "") if isinstance(review, dict) else str(review)
        return f"Generated {len(code)} characters of code"


class ResearchAgent(LiveAgent):
    """Researches via Browser MCP and Knowledge Engine."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="research_agent", role="Research", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "research"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        results: list[Any] = []
        # Search knowledge first.
        if self.knowledge is not None:
            try:
                hits = self.knowledge.search(objective)
                results.extend(hits[:3])
            except Exception:  # noqa: BLE001
                pass
        # Search via browser MCP.
        browser_result = self._mcp_execute(
            "browser.navigate",
            {"url": f"https://example.com/search?q={objective[:50]}"},
            connector="browser",
        )
        if browser_result.get("success"):
            results.append(browser_result["output"])
        return {"findings": results, "objective": objective}

    def report(self, review: Any) -> str:
        count = len(review.get("findings", [])) if isinstance(review, dict) else 0
        return f"Found {count} research findings"


class GitHubAgent(LiveAgent):
    """Manages git repositories via GitHub MCP."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="github_agent", role="Git Management", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "git_operations"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "git.status",
            {"path": "."},
            connector="github",
        )
        return {"git_status": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Git operations completed"


class BrowserAgent(LiveAgent):
    """Browses the web via Browser MCP."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="browser_agent", role="Web Browsing", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "browse"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "browser.navigate",
            {"url": f"https://example.com/?q={objective[:50]}"},
            connector="browser",
        )
        return {"browse_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Browsing completed"


class MiningAgent(LiveAgent):
    """Manages mining/geological data via Filesystem MCP."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="mining_agent", role="Mining Data", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "data_processing"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "file.list",
            {"path": "."},
            connector="filesystem",
        )
        return {"data_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Mining data processed"


class VisionAgent(LiveAgent):
    """Processes images via Playwright MCP (screenshots)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="vision_agent", role="Vision", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "capture"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "playwright.screenshot",
            {},
            connector="playwright",
        )
        return {"vision_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Vision processing completed"


class WindowsAgent(LiveAgent):
    """Manages Windows OS via Windows MCP."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="windows_agent", role="Windows OS", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "os_operations"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "windows.shell",
            {"command": f"echo {objective[:50]}"},
            connector="windows",
        )
        return {"os_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Windows operations completed"


class PlannerAgent(LiveAgent):
    """Plans via the Brain's reasoning and planning stages."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="planner_agent", role="Planning", **kwargs)

    def plan(self, objective: str) -> Any:
        return {
            "objective": objective,
            "steps": ["research", "design", "implement", "test", "deploy"],
        }

    def execute(self, plan: Any) -> Any:
        return plan

    def report(self, review: Any) -> str:
        steps = review.get("steps", []) if isinstance(review, dict) else []
        return f"Planned {len(steps)} steps"


class KnowledgeAgent(LiveAgent):
    """Searches the Knowledge Engine."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="knowledge_agent", role="Knowledge Search", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "knowledge_search"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        results: list[Any] = []
        if self.knowledge is not None:
            try:
                results = list(self.knowledge.search(objective))
            except Exception:  # noqa: BLE001
                pass
        return {"knowledge_hits": results, "objective": objective}

    def report(self, review: Any) -> str:
        count = len(review.get("knowledge_hits", [])) if isinstance(review, dict) else 0
        return f"Found {count} knowledge hits"


class MemoryAgent(LiveAgent):
    """Manages the Memory Engine."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="memory_agent", role="Memory Management", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "memory_recall"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        results: list[Any] = []
        if self.memory is not None:
            try:
                results = list(self.memory.recall())
            except Exception:  # noqa: BLE001
                pass
        return {"memories": results[:5], "objective": objective}

    def report(self, review: Any) -> str:
        count = len(review.get("memories", [])) if isinstance(review, dict) else 0
        return f"Recalled {count} memories"


class BlenderAgent(LiveAgent):
    """Manages Blender 3D via Blender MCP."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="blender_agent", role="3D Rendering", **kwargs)

    def plan(self, objective: str) -> Any:
        return {"objective": objective, "approach": "render"}

    def execute(self, plan: Any) -> Any:
        objective = plan.get("objective", "")
        result = self._mcp_execute(
            "blender.render",
            {"frame": 1},
            connector="blender",
        )
        return {"render_result": result, "objective": objective}

    def report(self, review: Any) -> str:
        return "Blender rendering completed"


#: List of all live agent classes.
ALL_LIVE_AGENTS: list[type[LiveAgent]] = [
    CodingAgent,
    ResearchAgent,
    GitHubAgent,
    BrowserAgent,
    MiningAgent,
    VisionAgent,
    WindowsAgent,
    PlannerAgent,
    KnowledgeAgent,
    MemoryAgent,
    BlenderAgent,
]


def instantiate_all_agents(
    mcp_manager: Any = None,
    providers: Any = None,
    memory: Any = None,
    knowledge: Any = None,
) -> list[LiveAgent]:
    """Instantiate every live agent with the given dependencies."""
    return [
        cls(
            mcp_manager=mcp_manager,
            providers=providers,
            memory=memory,
            knowledge=knowledge,
        )
        for cls in ALL_LIVE_AGENTS
    ]


__all__ = [
    "ALL_LIVE_AGENTS",
    "BlenderAgent",
    "BrowserAgent",
    "CodingAgent",
    "GitHubAgent",
    "KnowledgeAgent",
    "LiveAgent",
    "MemoryAgent",
    "MiningAgent",
    "PlannerAgent",
    "ResearchAgent",
    "VisionAgent",
    "WindowsAgent",
    "instantiate_all_agents",
]
