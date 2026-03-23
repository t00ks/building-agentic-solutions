import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents.agent import Agent
from agents.agent_config import AgentConfig
from agents.agent_event import AgentEvent
from agents.agent_update import AgentUpdate
from core.exceptions import AgentException
from core.logging_config import get_logger
from services.session_context import SessionContext
from services.tools_service import ToolsService
from tools.tool_update import ToolUpdate

_AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"


def format_sse_event(event: AgentEvent) -> bytes:
    """Build a single SSE frame for AgentEvent payloads."""
    lines = [f"event: {event.event_type}"]

    if event.event_type == "debug" and (isinstance(event.data, ToolUpdate) or isinstance(event.data, AgentUpdate)):
        payload = json.dumps(event.data.to_dict(), ensure_ascii=False, separators=(",", ":"))
    else:
        payload = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))

    for ln in payload.splitlines():
        lines.append(f"data: {ln}")

    lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def load_agent_config(config_filename: str) -> AgentConfig:
    config_path = _AGENTS_DIR / config_filename
    with config_path.open("r", encoding="utf-8") as f:
        agents_config = json.load(f)

    if not isinstance(agents_config, list) or len(agents_config) == 0:
        raise ValueError(f"{config_filename} must contain at least one agent config")

    return AgentConfig(**agents_config[0])


def create_step_router(endpoint: str, config_filename: str) -> APIRouter:
    """Create an SSE-streaming step router backed by the given stage config file."""
    router = APIRouter()

    @router.get(endpoint)
    async def process_step_request(request: Request) -> StreamingResponse:
        request_logger = get_logger(__name__).bind(step=endpoint)

        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
        }

        heartbeat_ms = int(os.getenv("SSE_HEARTBEAT_MS", "10000"))
        heartbeat_interval = heartbeat_ms / 1000.0

        async def event_generator() -> AsyncIterator[bytes]:
            queue: asyncio.Queue[tuple[str, AgentEvent | Exception | None]] = asyncio.Queue()

            async def produce() -> None:
                try:
                    tools_service = await ToolsService().load_tools()
                    agent_config = load_agent_config(config_filename)
                    agent = await Agent.create(agent_config=agent_config, tools_service=tools_service, checkpointer=None)

                    async with tools_service._mcp_client.session("travelAgentTools") as session:
                        async with SessionContext(session):
                            async for event in agent.stream(
                                query="Plan and book a 2-day sightseeing itinerary in Lisbon with 3 stops for a family of 4 travelers who like coffee and architecture.",
                                debug=True,
                            ):
                                await queue.put(("event", event))
                except Exception as e:
                    await queue.put(("error", e))
                finally:
                    await queue.put(("done", None))

            producer_task = asyncio.create_task(produce())
            try:
                while True:
                    if await request.is_disconnected():
                        break

                    try:
                        kind, payload_obj = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    except TimeoutError:
                        yield b": heartbeat\n\n"
                        continue

                    if kind == "event" and isinstance(payload_obj, AgentEvent):
                        yield format_sse_event(payload_obj)
                    elif kind == "error":
                        request_logger.error(f"Error during {endpoint} stream", exc_info=payload_obj)
                        break
                    elif kind == "done":
                        break
            finally:
                if not producer_task.done():
                    producer_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await producer_task

        try:
            return StreamingResponse(event_generator(), headers=headers)
        except AgentException as e:
            request_logger.error("Agent error", error_message=e.message, exc_info=True)
            raise HTTPException(status_code=500, detail="Agent processing error") from None

    return router
