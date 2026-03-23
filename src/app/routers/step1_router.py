from fastapi import APIRouter, Request
from langchain.agents import create_agent

from routers.sse_agent_router import QueryRequest
from services.llm_service import get_llm
from tools.step1_place_info_tool import place_info_tool

router = APIRouter()


@router.post("/step1")
async def process_request(request: Request, body: QueryRequest):
    agent = create_agent(model=get_llm().bind_tools([place_info_tool]), tools=[place_info_tool], system_prompt="", name="ItineraryAgent")

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": body.query,
                }
            ]
        }
    )

    return result["messages"]
