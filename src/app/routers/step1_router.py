import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain.agents import AgentState, create_agent
from pydantic import BaseModel

from agents.agent_update import AgentUpdate
from core.exceptions import AgentException
from core.logging_config import get_logger
from core.models import Applicant, User
from services.llm_service import get_llm
from tools.step1_place_info_tool import place_info_tool
from tools.tool_update import ToolUpdate

router = APIRouter()


@router.get("/step1")
async def process_request(request: Request):
    agent = create_agent(model=get_llm().bind_tools([place_info_tool]), tools=[place_info_tool], system_prompt="", name="ItineraryAgent")

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Plan a 1-day sightseeing itinerary in Lisbon with 3 stops for a solo traveler who likes coffee and architecture.",
                }
            ]
        }
    )

    return result["messages"]
