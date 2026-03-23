import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from agents.agent import Agent
from routers.sse_agent_router import (
    QueryRequest,
    create_sse_response,
    load_agent_config,
)
from services.session_context import SessionContext
from services.tools_service import ToolsService

router = APIRouter()


@router.post("/step2")
async def process_request(request: Request, body: QueryRequest) -> StreamingResponse:
    query = body.query

    async def produce(queue: asyncio.Queue) -> None:
        try:
            tools_service = await ToolsService().load_tools()
            agent_config = load_agent_config("stage2_agents_config.json")

            agent = await Agent.create(
                agent_config=agent_config,
                tools_service=tools_service,
                checkpointer=None,
            )

            async with tools_service._mcp_client.session("travelAgentTools") as session:
                async with SessionContext(session):
                    async for event in agent.stream(query=query, debug=True):
                        await queue.put(("event", event))
        except Exception as e:
            await queue.put(("error", e))
        finally:
            await queue.put(("done", None))

    return create_sse_response(request, produce, "/step2")

