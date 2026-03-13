import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.agent_update import AgentUpdate
from agents.orchestration_agent import AgentEvent
from core.exceptions import AgentException
from core.logging_config import get_logger
from core.models import Applicant, User
from tools.tool_update import ToolUpdate

router = APIRouter()

class OrchestratorRequest(BaseModel):
    query: str
    conversation_id: str
    user: User
    applicants: list[Applicant] | None = None
    debug: bool = False


class AgentContextResponse(BaseModel):
    final_answer: str
    context: dict[str, Any]


def format_sse_event(event: AgentEvent):
    """
    Build a single SSE frame (bytes).
    - data: any JSON-serializable object (will be json.dumps'd)
    - event: 'response' when its a token output from the LLM, 'update' when it's a state change
    """
    lines = []
    lines.append(f"event: {event.event_type}")

    if event.event_type == "debug" and (isinstance(event.data, ToolUpdate) or isinstance(event.data, AgentUpdate)):
        payload = json.dumps(event.data.to_dict(), ensure_ascii=False, separators=(",", ":"))
    else:
        payload = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))

    for ln in payload.splitlines():
        lines.append(f"data: {ln}")

    lines.append("")  # terminator
    return ("\n".join(lines) + "\n").encode("utf-8")


@router.post("/")
async def process_request(payload: OrchestratorRequest, request: Request) -> StreamingResponse:
    """
    Handle incoming POST requests to the / endpoint with server-sent events streaming.

    This endpoint receives a request payload, delegates processing to the OrchestrationAgent,
    and returns a streaming response with server-sent events containing the orchestration
    response data.

    Args:
        payload (OrchestratorRequest): The incoming request payload containing query,
                                      lead_id, and debug flag.

    Returns:
        StreamingResponse: A streaming response with server-sent events containing
                          orchestration data, with appropriate headers for SSE including
                          CORS support.

    Raises:
        HTTPException: Returns a 500 status code if an AgentException occurs during
                      orchestration processing.
    """
    request_logger = get_logger(__name__).bind(
        conversation_id=payload.conversation_id, query_length=len(payload.query)
    )

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        # Additional headers for Kong compatibility
        "Transfer-Encoding": "chunked",
        "X-Content-Type-Options": "nosniff",
        # CORS headers
        "Access-Control-Allow-Origin": "*",
    }

    try:
        orchestration_response = request.app.state.orchestration_agent.stream(
            query=payload.query,
            conversation_id=payload.conversation_id,
            requesting_user=payload.user,
            applicants=payload.applicants,
            debug=True,
        )

        heartbeat_ms = int(os.getenv("SSE_HEARTBEAT_MS", "10000"))  # default 10s
        heartbeat_interval = heartbeat_ms / 1000.0

        async def event_generator() -> AsyncIterator[bytes]:
            import asyncio
            from contextlib import suppress

            queue: asyncio.Queue[tuple[str, AgentEvent | Exception | None]] = asyncio.Queue()

            async def produce():
                try:
                    async for event in orchestration_response:
                        await queue.put(("event", event))
                except Exception as e:  # capture producer exception
                    await queue.put(("error", e))
                finally:
                    await queue.put(("done", None))

            producer_task = asyncio.create_task(produce())
            try:
                while True:
                    try:
                        kind, payload_obj = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    except asyncio.TimeoutError:
                        # Emit heartbeat comment frame (ignored by EventSource but keeps connection alive)
                        yield b": heartbeat\n\n"
                        continue

                    if kind == "event" and isinstance(payload_obj, AgentEvent):
                        yield format_sse_event(payload_obj)
                    elif kind == "error":
                        request_logger.error("Error during orchestration", exc_info=payload_obj)
                        # Only surface error details to client if debug enabled.
                        if payload.debug and isinstance(payload_obj, Exception):
                            debug_evt = AgentEvent(
                                event_type="debug",
                                data={
                                    "type": "stream_error",
                                    "message": str(payload_obj),
                                },
                            )
                            yield format_sse_event(debug_evt)
                        # Regardless, break the loop; stream ends gracefully.
                        break
                    elif kind == "done":
                        break
            finally:
                if not producer_task.done():
                    producer_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await producer_task

        return StreamingResponse(event_generator(), headers=headers)

    except AgentException as e:
        request_logger.error("Agent error", error_message=e.message, exc_info=True)
        raise HTTPException(status_code=500, detail="Agent processing error") from None


@router.post("/test")
async def test_request(payload: OrchestratorRequest, request: Request) -> AgentContextResponse:
    """
    Handle incoming POST requests to the /test endpoint for testing without streaming.
    """
    request_logger = get_logger(__name__).bind(lead_id=payload.metadata.lead_id, query_length=len(payload.query))

    try:
        orchestration_response = request.app.state.orchestration_agent.stream(
            query=payload.query,
            conversation_id=payload.conversation_id,
            lead_id=payload.metadata.lead_id,
            requesting_user=payload.user,
            applicants=payload.metadata.applicants,
            current_screen=payload.metadata.current_screen,
            debug=True,
        )

        response: str = ""
        retrieval_data_sources: list[str] = []
        retrieval_data: list[Any] = []

        async for event in orchestration_response:
            if event.event_type == "response":
                response += event.data.get("value", "")
            if event.event_type == "debug" and isinstance(event.data, ToolUpdate):
                update: ToolUpdate = event.data
                retrieval_data_sources.append(update.tool_name)
                retrieval_data.append(update.tool_data)

        return AgentContextResponse(
            final_answer=response,
            context={
                "retrieval_data_sources": retrieval_data_sources,
                "retrieval_data": retrieval_data,
            },
        )

    except AgentException as e:
        request_logger.error("Agent error", error_message=e.message, exc_info=True)
        raise HTTPException(status_code=500, detail="Agent processing error") from None


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify the service is running.

    Returns:
        dict: A dictionary indicating the service is healthy.
              Example:
              {
                  "status": "healthy"
              }
    """
    return {"status": "healthy"}
