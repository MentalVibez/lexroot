"""Main plugin class for The Living Lexicon LangChain integration."""

from typing import List, Optional

from langchain_core.tools import BaseTool

from .tools import EraTimelineTool, GuardrailsTool, SearchTool, SemanticDriftTool, WordLookupTool


class LexiconPlugin:
    """Plugin class that provides LangChain tools for The Living Lexicon API.

    This plugin allows chatbots to integrate etymology and historical word context
    capabilities by calling a remote Living Lexicon service.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ):
        """Initialize the plugin.

        Args:
            base_url: Base URL of the Living Lexicon API service
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retries for failed requests
            backoff_factor: Exponential backoff factor for retries
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Initialize tools with common config
        tool_kwargs = {
            "base_url": base_url,
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
            "backoff_factor": backoff_factor,
        }

        self._tools = {
            "word_lookup": WordLookupTool(**tool_kwargs),
            "semantic_drift": SemanticDriftTool(**tool_kwargs),
            "era_timeline": EraTimelineTool(**tool_kwargs),
            "lexicon_search": SearchTool(**tool_kwargs),
            "guardrails_check": GuardrailsTool(**tool_kwargs),
        }

    def get_tools(self) -> List[BaseTool]:
        """Get all available tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> BaseTool:
        """Get a specific tool by name."""
        if name not in self._tools:
            available = list(self._tools.keys())
            raise ValueError(f"Tool '{name}' not found. Available tools: {available}")
        return self._tools[name]

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tools.keys())

    async def close(self):
        """Close all HTTP clients used by the tools."""
        for tool in self._tools.values():
            if hasattr(tool, '_close_client'):
                await tool._close_client()