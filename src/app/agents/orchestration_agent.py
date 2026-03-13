"""
This module implements the OrchestrationAgent class, which serves as the top-level coordinator
for the Guardian Angel multi-agent system.

The OrchestrationAgent manages the complete agent ecosystem by:
- Loading and coordinating multiple specialized agents (single and multi-agent)
- Managing conversation state and memory through PostgreSQL checkpointing
- Orchestrating complex workflows across different agent capabilities
- Providing unified interface for external system integration
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRequest, dynamic_prompt
from langchain_core.messages import (
    AIMessageChunk,
    HumanMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph

from agents.agent import Agent
from agents.agent_config import AgentConfig
from agents.agent_context_schema import AgentContextSchema
from agents.agent_update import AgentUpdate, AgentUpdateEvent
from core.config import get_config
from core.exceptions import AgentProcessingError
from core.logging_config import get_logger
from core.models import Applicant, User
from core.utils import (
    add_date_to_prompt_template,
    build_before_model_middleware,
    extract_content_as_string,
    load_prompt_template,
)
from services.llm_service import get_llm
from services.session_context import SessionContext
from services.tools_service import ToolsService
from tools.tool_update import ToolUpdate
from tools.validation_tool import validate_input

EventType = Literal["response", "update", "done", "debug"]
"""SSE output event types

- `"response"`: Emit response tokens from LLM output
- `"update"`: Emit state changes and workflow updates  
- `"done"`: Emit completion signal when workflow finishes
- `"debug"`: Emit debug information and internal state
"""


class AgentEvent:
    def __init__(self, event_type: EventType, data: Any):
        self.event_type = event_type
        self.data = data


class OrchestrationAgent:
    """
    The top-level orchestrator for the Guardian Angel multi-agent system.

    This agent coordinates the entire ecosystem of specialized agents, managing:
        - Agent lifecycle and configuration loading
        - Cross-agent workflow orchestration using LangGraph supervisor pattern
        - Persistent conversation state with PostgreSQL checkpointing
        - Tool service integration and MCP session management
        - External API interface for system integration

    The OrchestrationAgent acts as the primary entry point for complex multi-step
    reasoning tasks that require coordination between multiple specialized agents.
    """

    def __init__(self, config_path: str):
        """
        Initialize the OrchestrationAgent with agent configuration.

        Args:
            config_path (str): Path to the JSON configuration file containing
                agent definitions, relative to the agents directory.
        """
        self.logger = get_logger(__name__)

        self.base_dir: Path = Path(__file__).parent.parent
        self.config_path: Path = self.base_dir / "agents" / config_path
        self.agent_configs: dict[str, AgentConfig] = self._load_agent_configs()
        self.sub_agent_names: list[str] = list(self.agent_configs.keys())

        self._orchestrator_name: str = "system_orchestrator"

        self._debug: bool = False

        self._workflow: StateGraph | None = None

        self._checkpointer: AsyncPostgresSaver | None = None

        self._tools_service: ToolsService
        self.config = get_config()

        self._prompt: str | None = None

        # Read default temperature from environment variables
        self._temperature = self.config.llm.orchestrator_temperature
        self._llm_run_limit: int = self.config.llm.orchestrator_run_limit

    def _load_agent_configs(self):
        """
        Load agent configurations from the JSON configuration file.

        Returns:
            dict[str, AgentConfig]: Dictionary mapping agent names to their configurations.
        """
        with open(self.config_path, encoding="utf-8") as f:
            return {agent["name"]: AgentConfig(**agent) for agent in json.load(f)}

    @classmethod
    async def create(cls, checkpointer: AsyncPostgresSaver, config_path: str = "agents_config.json"):
        """
        Asynchronously create and initialize an OrchestrationAgent instance.

        This factory method handles the complete setup process including:
        - Loading agent configurations
        - Setting up PostgreSQL checkpointer for state management
        - Initializing the workflow with all agents
        - Configuring tools and AWS Bedrock integration

        Args:
            config_path (str, optional): Path to agent configuration JSON file.
                Defaults to "agents_config.json".
            debug (bool, optional): Whether to enable debug mode for workflows.
                Defaults to False.

        Returns:
            OrchestrationAgent: A fully initialized orchestration agent instance.

        Raises:
            AgentResourceError: If PostgreSQL checkpointer setup fails or other
                initialization errors occur.
        """
        self = cls(config_path)
        self._checkpointer = checkpointer

        # Build the agent and tools using MCP session
        await self._build_workflow()
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

    async def _build_workflow(self):
        """
        Build the orchestration workflow by creating and coordinating all agents.

        This method:
        1. Loads the orchestration prompt template
        2. Initializes the tools service with MCP integration
        3. Sets up AWS Bedrock LLM client
        4. Creates all configured agents (both single and multi-agent types)
        5. Creates the supervisor workflow to coordinate all agents

        Raises:
            AgentResourceError: If AWS Bedrock initialization fails or other
                resource setup errors occur.
        """

        # Load system prompt
        prompt_template = self._load_prompt("orchestration_agent.md")

        @dynamic_prompt
        def get_system_prompt(request: ModelRequest) -> str:
            return add_date_to_prompt_template(prompt_template)

        self._tools_service = await ToolsService().load_tools()

        self._llm = get_llm().bind(temperature=self._temperature)

        agents_tools = [
            (await Agent.create(agent, self._tools_service, self._checkpointer)).as_tool()
            for agent in self.agent_configs.values()
        ]

        self._graph = create_agent(
            tools=[validate_input, *agents_tools],
            model=self._llm,
            middleware=[
                get_system_prompt,
                build_before_model_middleware(self._orchestrator_name),
                ModelCallLimitMiddleware(run_limit=self._llm_run_limit),
            ],
            name=self._orchestrator_name,
            context_schema=AgentContextSchema,
            checkpointer=self._checkpointer,
        )

    async def stream(
        self,
        query: str,
        conversation_id: str,
        requesting_user: User,
        applicants: list[Applicant] | None = None,
        debug: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        """
        Orchestrate a complex query across multiple agents with session management.

        This method:
        1. Compiles the workflow with checkpointer for state persistence
        2. Sets up MCP session context for tool execution
        3. Executes the query through the agent supervisor workflow
        4. Extracts and formats the final answer and tool contexts

        Args:
            query (str): The user query to process across the agent system.
            conversation_id (str): The conversation id of this thread.
            lead_id (str): Unique identifier for conversation session to maintain
                state and context across interactions.

        Returns:
            OrchestrationResponse:
                An object with the answer and context.
                {
                    "answer": "This is what you wanted to know.",
                    "context": List of tool execution contexts with names and content, e.g.
                }

        Raises:
            Exception: Various exceptions may be raised during workflow execution,
                MCP session management, or tool execution.
        """
        config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}

        # Establish MCP session context for tool execution with proper cleanup
        async with self._tools_service._mcp_client.session("populationTools") as mcp_session:
            async with SessionContext(mcp_session, conversation_id):
                try:
                    # Initialize tracking variables for workflow state
                    validator_approved: bool = False  # Track if validation agent approved the response
                    final_response: str = ""  # Store the final response from the orchestrator
                    current_agent: str = self._orchestrator_name
                    last_orchestrator_message: str = ""

                    async for _meta, mode, message_chunk in self._graph.astream(
                        {"messages": [HumanMessage(content=query)]},
                        stream_mode=["messages", "updates", "custom"],
                        config=config,
                        context={
                            "applicants": applicants,
                            "user": requesting_user,
                        },
                        subgraphs=True,  # Include worker agent subgraphs in the stream
                        debug=debug,
                    ):
                        # Handle workflow state updates (agent transitions, tool calls, etc.)
                        if mode == "updates":
                            self.logger.debug(message_chunk)

                        # Handle streaming message chunks (token-by-token output)
                        elif mode == "messages":
                            # Stream orchestrator responses only after validation approval
                            if validator_approved:
                                if isinstance(message_chunk[0], AIMessageChunk):
                                    # Extract and stream individual tokens from the orchestrator
                                    text = extract_content_as_string(message_chunk[0])
                                    if text is not None and text.strip():
                                        final_response += text
                                        yield AgentEvent(
                                            event_type="response",
                                            data={"value": text},
                                        )
                            elif current_agent == self._orchestrator_name:
                                # Capture orchestrator output until validation approval
                                if isinstance(message_chunk[0], AIMessageChunk):
                                    text = extract_content_as_string(message_chunk[0])
                                    if text is not None and text.strip():
                                        last_orchestrator_message += text

                        elif mode == "custom":
                            if isinstance(message_chunk, ToolUpdate):
                                tool_update: ToolUpdate = message_chunk
                                if tool_update.tool_name == "validate_input":
                                    validator_approved = tool_update.tool_data[0].lower() != "rejected"
                            if isinstance(message_chunk, AgentUpdate):
                                agent_update: AgentUpdate = message_chunk
                                if agent_update.agent_event == AgentUpdateEvent.START:
                                    current_agent = agent_update.agent_name
                                    yield AgentEvent(event_type="update", data={"agent": agent_update.agent_name})
                                    self.logger.info(f"Switching to agent: {agent_update.agent_name}")
                                if (
                                    agent_update.agent_event == AgentUpdateEvent.FINISH
                                    and agent_update.agent_name in self.sub_agent_names
                                ):
                                    current_agent = self._orchestrator_name
                                    yield AgentEvent(event_type="update", data={"agent": self._orchestrator_name})
                                    self.logger.info(f"Switching to agent: {self._orchestrator_name}")

                            if debug:
                                yield AgentEvent(event_type="debug", data=message_chunk)

                    if last_orchestrator_message and not final_response:
                        yield AgentEvent(
                            event_type="response",
                            data={"value": last_orchestrator_message},
                        )

                    # Signal completion of the workflow execution
                    yield AgentEvent(
                        event_type="done",
                        data={},
                    )
                except Exception as e:
                    self.logger.error(f"Error running agent stream: {e}")
                    raise AgentProcessingError("Error running agent stream") from e
