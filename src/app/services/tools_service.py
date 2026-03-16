"""
This module implements the ToolsService class, which provides centralized management
for tools from multiple sources in the multi-agent system.

The ToolsService handles:
- Loading and managing internal tools (custom domain-specific tools)
- Integration with external MCP (Model Context Protocol) servers
- Tool filtering and selection based on agent requirements
- Tool wrapping for consistent LangChain compatibility
- Session-aware tool execution with proper context management
"""

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool, Tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.config import get_stream_writer
from pydantic import BaseModel

from core.config import get_config
from core.exceptions import AgentConfigurationError, AgentProcessingError, AgentResourceError
from core.logging_config import get_logger
from services.session_context import CURRENT_MCP_SESSION
from tools.tool_update import ToolUpdate


class ToolsService:
    """
    Centralized service for loading and managing tools from multiple sources.

    The ToolsService provides a unified interface for tool management across the
    agentic system, handling both internal custom tools and external
    MCP (Model Context Protocol) tools.

    Key responsibilities:
        - Initialize and manage internal tool registry
        - Establish connections to external MCP servers
        - Load and wrap tools for LangChain compatibility
        - Filter tools based on agent-specific requirements
        - Manage tool execution contexts and sessions
    """

    def __init__(self):
        """
        Initialize the ToolsService with internal tools and MCP client configuration.

        Sets up:
        - Logger for service operations
        - Configuration loading
        - Internal tool registry with domain-specific tools
        - MCP client configuration for external tool server connections
        """
        # Load configuration
        self.logger = get_logger(__name__)
        self.config = get_config()

        self._tools: dict[str, Any] = {
        }

        self._mcp_client = MultiServerMCPClient({"populationTools": {"url": self.config.services.mcp_server_url, "transport": "streamable_http"}})

    @property
    def tools(self):
        """
        Get the complete tools collection.

        Returns:
            dict[str, Any]: Dictionary mapping tool names to tool instances.

        Raises:
            AgentProcessingError: If tools have not been loaded yet.
        """
        if self._tools is None:
            raise AgentProcessingError("tools not loaded yet")
        return self._tools

    async def load_tools(self) -> "ToolsService":
        """
        Load and initialize tools from MCP server and merge with internal tools.

        This method:
        1. Establishes a session with the MCP server
        2. Loads available tools from the MCP server
        3. Wraps MCP tools for LangChain compatibility
        4. Adds wrapped tools to the internal tool registry
        5. Returns self for method chaining

        Args:
            lead_id (str): The lead ID to associate with the tools.

        Returns:
            ToolsService: Self reference for method chaining.

        Raises:
            AgentResourceError: If MCP server connection fails or tool loading fails.
        """

        try:
            async with self._mcp_client.session("populationTools") as session:
                raw_tools = await load_mcp_tools(session)

            for tool in raw_tools:
                self._tools[tool.name] = self.wrap_mcp_tool(tool)

        except Exception as e:
            raise AgentResourceError("Failed to initialize MCP tools") from e

        return self

    def filter_tools(self, tools: list[str]) -> list[Tool | BaseTool]:
        """
        Filter the loaded tools based on the provided list of tool names.

        This method extracts only the tools specified in the tools list from the
        complete tool registry, allowing agents to work with a focused subset
        of available tools.

        Args:
            tools (list[str]): List of tool names to filter and return.

        Returns:
            list[Tool | BaseTool]: List of filtered tools matching the requested names.

        Note:
            Tools not found in the registry will be silently skipped.
        """
        return list({key: self._tools[key] for key in tools}.values())

    def wrap_mcp_tool(self, tool: BaseTool) -> BaseTool:
        """
        Wrap an MCP tool for LangChain compatibility with session-aware execution.

        This method creates a LangChain-compatible wrapper around MCP tools that:
        - Preserves the original tool's schema and description
        - Handles session context management automatically
        - Provides consistent error handling and logging
        - Returns properly formatted tool responses

        Args:
            tool (BaseTool): The MCP tool to wrap for LangChain compatibility.

        Returns:
            Tool: A LangChain StructuredTool wrapper with session-aware execution.

        Raises:
            AgentConfigurationError: If the MCP tool is missing required args_schema.
        """

        args_schema = getattr(tool, "args_schema", None)

        if args_schema is None:
            raise AgentConfigurationError("MCP Tool is missing args_schema")

        async def arun(**kwargs: dict) -> str:
            self.logger.info(f"Calling tool: {tool.name} with args: {kwargs}")

            session = CURRENT_MCP_SESSION.get()
            if session is None:
                raise RuntimeError("MCP session not set for this turn")

            try:
                result = await session.call_tool(tool.name, kwargs)
                # Consolidate all text parts
                content = "".join(c.text for c in getattr(result, "content", []) if getattr(c, "text", None))
                self.logger.info(f"Tool response: {result}")
            except Exception as e:
                content = f"Tool '{tool.name}' failed: {str(e)}"

            writer = get_stream_writer()
            writer(ToolUpdate(tool_name=tool.name, tool_data=[content]))

            return content

        return StructuredTool.from_function(
            name=tool.name,
            func=None,
            coroutine=arun,
            description=tool.description,
            args_schema=args_schema,
        )
