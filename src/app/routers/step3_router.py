import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from agents.agent import Agent
from agents.agent_event import AgentEvent
from routers.sse_agent_router import (
    QueryRequest,
    create_sse_response,
    load_agent_configs,
)
from services.session_context import SessionContext
from services.tools_service import ToolsService

router = APIRouter()


async def _stream_agent_and_capture(
    agent: Agent,
    messages: list[BaseMessage],
    queue: asyncio.Queue,
) -> str:
    """Stream an agent's events to the queue and return the captured text output."""
    captured: list[str] = []
    async for event in agent.stream(messages=messages, debug=True):
        await queue.put(("event", event))
        if event.event_type == "response" and isinstance(event.data, dict):
            value = event.data.get("value")
            if value:
                captured.append(value)
    return "".join(captured)


@router.post("/step3")
async def process_request(request: Request, body: QueryRequest) -> StreamingResponse:
    query = body.query

    async def produce(queue: asyncio.Queue) -> None:
        try:
            configs = load_agent_configs("stage3_agents_config.json")
            itinerary_config = next(c for c in configs if c.name == "itinerary_agent")
            local_info_config = next(c for c in configs if c.name == "local_info_agent")
            booking_config = next(c for c in configs if c.name == "booking_agent")

            tools_service = await ToolsService().load_tools()

            itinerary_agent = await Agent.create(agent_config=itinerary_config, tools_service=tools_service)
            local_info_agent = await Agent.create(agent_config=local_info_config, tools_service=tools_service)
            booking_agent = await Agent.create(agent_config=booking_config, tools_service=tools_service)

            # Maintain a shared conversation history
            history: list[BaseMessage] = [HumanMessage(content=query)]

            async with tools_service._mcp_client.session("travelAgentTools") as session:
                async with SessionContext(session):
                    # 1. Run itinerary agent — stream & capture output
                    await queue.put(("event", AgentEvent(event_type="update", data={"agent": "itinerary_agent"})))
                    itinerary_output = await _stream_agent_and_capture(itinerary_agent, history, queue)
                    history.append(AIMessage(content=itinerary_output))

                    # 2. Run local info agent
                    await queue.put(("event", AgentEvent(event_type="update", data={"agent": "local_info_agent"})))
                    local_info_output = await _stream_agent_and_capture(local_info_agent, history, queue)
                    history.append(AIMessage(content=local_info_output))

                    # 3. Run booking agent
                    await queue.put(("event", AgentEvent(event_type="update", data={"agent": "booking_agent"})))
                    await _stream_agent_and_capture(booking_agent, history, queue)

        except Exception as e:
            await queue.put(("error", e))
        finally:
            await queue.put(("done", None))

    return create_sse_response(request, produce, "/step3")

