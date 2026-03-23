"""
This module implements the Agent class, which can operate as either a standalone agent
with its own toolset or as a multi-agent supervisor coordinating specialized child agents.

This agent supports:
- Multi-agent coordination using LangGraph supervisor pattern when children are defined
- Standalone execution using custom tool collections without child agents
- Dynamic tool routing to appropriate child agents or local tools
- Hierarchical agent architecture with specialized capabilities
- Custom prompts to define supervisor or standalone behavior
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRequest, dynamic_prompt
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.tools import BaseTool, StructuredTool, Tool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.config import get_stream_writer
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import get_runtime

from agents.agent_config import AgentConfig
from agents.agent_event import AgentEvent
from agents.agent_update import AgentUpdate, AgentUpdateEvent
from core.config import get_config
from core.exceptions import AgentProcessingError
from core.logging_config import get_logger
from core.utils import add_date_to_prompt_template, extract_content_as_string, load_prompt_template
from services.llm_service import get_llm
from services.tools_service import ToolsService


class Agent:
    """
    A flexible LangGraph-based agent that can run standalone or supervise multiple
    specialized child agents to handle complex tasks requiring different capabilities.

    In standalone mode the agent:
        - Operates with its own toolset and prompt configuration
        - Provides a unified interface for single-agent reasoning workflows

    In supervisor mode the agent additionally:
        - Manages multiple child agents with specialized tools and prompts
        - Routes tasks to appropriate child agents based on context
        - Coordinates communication between child agents
        - Integrates with AWS Bedrock for natural language processing
    """

    def __init__(self, agent_config: AgentConfig):
        """
        Initialize the Agent with configuration for standalone or supervising behavior.

        Args:
            agent_config (AgentConfig): The configuration for the multi-agent system,
        including child agent definitions, tools, and supervisor prompt.

        Raises:
            AgentConfigurationError: If the agent_config is not of type "multi".
        """
        self.logger = get_logger(__name__)
        # Store the prompt file name - will be read during _build_graph
        self.agent_config = agent_config
        # Load configuration
        self.config = get_config()

        self._temperature = self.agent_config.temperature or self.config.llm.agent_temperature
        self._llm_run_limit: int = self.agent_config.llm_run_limit or self.config.llm.agent_run_limit
        self._recursion_limit: int = 75

        self._prompt: str | None = None
        self._llm: BaseChatModel | None = None

        self._graph: CompiledStateGraph | None = None
        self._tools: list[Tool | BaseTool] = []

    def as_tool(self):
        """
        Returns the compiled LangGraph for the single agent.

        Returns:
            CompiledStateGraph: The compiled graph that manages agent execution and state.

        Raises:
            AgentProcessingError: If the agent has not been built yet.
        """
        if self._graph is None:
            raise AgentProcessingError("agent not built, check logs for errors")

        async def arun(
            request: Annotated[str, "A description of the users request"],
        ) -> AgentState:
            writer = get_stream_writer()
            writer(AgentUpdate(agent_name=self.agent_config.name, agent_event=AgentUpdateEvent.START))

            messages = [{"role": "user", "content": request}]

            response = await self._graph.ainvoke({"messages": messages})

            writer(AgentUpdate(agent_name=self.agent_config.name, agent_event=AgentUpdateEvent.FINISH))

            return response["messages"][-1].text

        return StructuredTool.from_function(
            name=self.agent_config.name,
            func=None,
            coroutine=arun,
            description=self.agent_config.description,
        )

    @classmethod
    async def create(cls, agent_config: AgentConfig, tools_service: ToolsService, checkpointer: AsyncPostgresSaver) -> "Agent":
        """
        Asynchronously creates and configures an Agent instance with child agents.

        This factory method handles the complete initialization process including:
        - Creating child agent instances when provided
        - Setting up the supervisor workflow if child agents exist
        - Configuring tools and AWS Bedrock integration
        - Compiling the final (single or multi-agent) graph

        Args:
            agent_config (AgentConfig): Configuration for the multi-agent system.
            tools_service (ToolsService): Service for managing and filtering tools.

        Returns:
            MultiAgent: A fully configured and ready-to-use multi-agent instance.

        Raises:
            AgentConfigurationError: If the agent configuration is invalid.
            AgentResourceError: If AWS Bedrock or other resources fail to initialize.
        """
        self = cls(agent_config)

        # Build the agent and tools using MCP session
        await self._build_workflow(tools_service, checkpointer)

        return self

    def _load_prompt(self, prompt_filename: str) -> str:
        """
        Load a prompt template from the prompts directory.

        Args:
            prompt_filename (str): Name of the prompt file to load.

        Returns:
            str: The contents of the prompt file.

        Raises:
            AgentResourceError: If the prompt file cannot be loaded.
        """
        if self._prompt is None:
            self._prompt = load_prompt_template(prompt_filename)

        return self._prompt

    async def _build_workflow(self, tools_service: ToolsService, checkpointer: AsyncPostgresSaver):
        """
        Build the agent workflow by creating child agents (if any) and supervisor.

        This method:
        1. Filters and loads tools based on agent configuration
        2. Loads the supervisor prompt template
        3. Creates and initializes all child agents when defined
        4. Sets up AWS Bedrock LLM client
        5. Creates the supervisor workflow using LangGraph when supervising
        6. Compiles the final agent graph supporting standalone or multi-agent modes

        Args:
            tools_service (ToolsService): Service for managing and filtering available tools.

        Raises:
            AgentResourceError: If AWS Bedrock initialization fails or prompt loading fails.
        """

        # Load desired tools from tools service
        self._tools = tools_service.filter_tools(self.agent_config.tools) if self.agent_config.tools else []

        @dynamic_prompt
        def get_system_prompt(request: ModelRequest) -> str:
            runtime = get_runtime()
            system_msg = self._load_prompt(self.agent_config.prompt_file)
            system_msg = add_date_to_prompt_template(system_msg)

            if len(self.agent_config.context) > 0:
                for ctx in self.agent_config.context:
                    system_msg = system_msg.replace(ctx.property_placeholder, getattr(runtime.context, ctx.property_name))

            return system_msg

        agents_tools = [(await Agent.create(agent, tools_service, checkpointer)).as_tool() for agent in self.agent_config.children or []]

        combined_tools = [*self._tools, *agents_tools]

        self._llm = get_llm().bind(temperature=self._temperature)

        self._graph = create_agent(
            model=self._llm.bind_tools(combined_tools),
            tools=combined_tools,
            middleware=[get_system_prompt, ModelCallLimitMiddleware(run_limit=self._llm_run_limit)],
            name=self.agent_config.name,
            checkpointer=checkpointer,
        ).with_config(recursion_limit=self._recursion_limit)

    async def stream(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        """
        Stream the agent's response to a query, yielding events as they occur.

        This method streams through the agent's graph, handling message chunks,
        state updates, and custom events from child agents.

        Args:
            query: The user query to process.
            context: Optional context dict to pass to the agent graph.
            debug: Whether to emit debug events.

        Yields:
            AgentEvent: Events of type "response", "update", "done", or "debug".

        Raises:
            AgentProcessingError: If the agent graph has not been built or streaming fails.
        """
        if self._graph is None:
            raise AgentProcessingError("agent not built, check logs for errors")

        try:
            final_response: str = ""
            current_agent: str = self.agent_config.name

            async for _meta, mode, message_chunk in self._graph.astream(
                {"messages": [HumanMessage(content=query)]},
                stream_mode=["messages", "updates", "custom"],
                context=context or {},
                subgraphs=True,
                debug=debug,
            ):
                if mode == "updates":
                    self.logger.debug(message_chunk)

                elif mode == "messages":
                    if isinstance(message_chunk[0], AIMessageChunk):
                        text = extract_content_as_string(message_chunk[0])
                        if text is not None and text.strip():
                            final_response += text
                            yield AgentEvent(
                                event_type="response",
                                data={"value": text},
                            )

                elif mode == "custom":
                    if isinstance(message_chunk, AgentUpdate):
                        agent_update: AgentUpdate = message_chunk
                        if agent_update.agent_event == AgentUpdateEvent.START:
                            current_agent = agent_update.agent_name
                            yield AgentEvent(event_type="update", data={"agent": agent_update.agent_name})
                            self.logger.info(f"Switching to agent: {agent_update.agent_name}")
                        if agent_update.agent_event == AgentUpdateEvent.FINISH:
                            current_agent = self.agent_config.name
                            yield AgentEvent(event_type="update", data={"agent": self.agent_config.name})
                            self.logger.info(f"Switching to agent: {self.agent_config.name}")

                    if debug:
                        yield AgentEvent(event_type="debug", data=message_chunk)

            yield AgentEvent(
                event_type="done",
                data={},
            )
        except Exception as e:
            self.logger.error(f"Error running agent stream: {e}")
            raise AgentProcessingError("Error running agent stream") from e
