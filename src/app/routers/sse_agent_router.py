import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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

DEFAULT_QUERY = "Plan and book a 2-day sightseeing itinerary in Lisbon with 3 stops for a family of 4 travelers who like coffee and architecture."


class QueryRequest(BaseModel):
    query: str = DEFAULT_QUERY


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


def load_agent_configs(config_filename: str) -> list[AgentConfig]:
    """Load all agent configs from a stage config file."""
    config_path = _AGENTS_DIR / config_filename
    with config_path.open("r", encoding="utf-8") as f:
        agents_config = json.load(f)

    if not isinstance(agents_config, list) or len(agents_config) == 0:
        raise ValueError(f"{config_filename} must contain at least one agent config")

    return [AgentConfig(**cfg) for cfg in agents_config]


def load_agent_config(config_filename: str) -> AgentConfig:
    """Load the first agent config from a stage config file."""
    return load_agent_configs(config_filename)[0]


SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Transfer-Encoding": "chunked",
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
}


def create_sse_response(
    request: Request,
    producer: Callable[[asyncio.Queue], Coroutine[Any, Any, None]],
    endpoint: str,
) -> StreamingResponse:
    """
    Create a StreamingResponse that consumes AgentEvents from a producer coroutine.

    The producer receives an asyncio.Queue and should put tuples of:
      ("event", AgentEvent), ("error", Exception), or ("done", None).
    """
    request_logger = get_logger(__name__).bind(step=endpoint)

    heartbeat_ms = int(os.getenv("SSE_HEARTBEAT_MS", "10000"))
    heartbeat_interval = heartbeat_ms / 1000.0

    async def event_generator() -> AsyncIterator[bytes]:
        queue: asyncio.Queue[tuple[str, AgentEvent | Exception | None]] = asyncio.Queue()

        producer_task = asyncio.create_task(producer(queue))
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
        return StreamingResponse(event_generator(), headers=SSE_HEADERS)
    except AgentException as e:
        request_logger.error("Agent error", error_message=e.message, exc_info=True)
        raise HTTPException(status_code=500, detail="Agent processing error") from None
