"""
Logging and performance monitoring middleware.

This middleware handles:
- Access logging in structured format
- Request/response timing and performance metrics
- Request/response size monitoring
- HTTP status code tracking
"""

import time

from fastapi import Request, Response

from core.logging_config import get_logger


async def logging_middleware(request: Request, call_next) -> Response:
    """
    Middleware to handle access logging and performance monitoring.

    This middleware:
    1. Records request start time
    2. Processes the request through the chain
    3. Calculates processing time
    4. Logs structured access information
    5. Adds performance headers to response

    Args:
        request (Request): The incoming FastAPI request
        call_next: The next middleware/handler in the chain

    Returns:
        Response: The response with performance headers added
    """
    access_logger = get_logger("api.access")

    # Record start time
    start_time = time.perf_counter_ns()

    # Process the request
    response = await call_next(request)

    # Calculate processing time
    process_time = time.perf_counter_ns() - start_time
    process_time_seconds = process_time / 10**9

    # Extract request information
    status_code = response.status_code
    url = request.url.path
    if request.query_params:
        query_string = str(request.query_params)
        url = f"{url}?{query_string}"

    # Get client information
    if request.client:
        client_host = request.client.host
        client_port = request.client.port
    else:
        client_host = "unknown"
        client_port = -1

    http_method = request.method
    http_version = request.scope["http_version"]

    # Log structured access information
    access_logger.info(
        f'{client_host}:{client_port} - "{http_method} {url} HTTP/{http_version}" {status_code}',
        http={
            "url": str(request.url),
            "status_code": status_code,
            "method": http_method,
            "version": http_version,
            "path": request.url.path,
            "query_params": dict(request.query_params),
        },
        network={"client": {"ip": client_host, "port": client_port}},
        performance={
            "duration_ns": process_time,
            "duration_seconds": process_time_seconds,
        },
        request_size=request.headers.get("content-length"),
        response_size=response.headers.get("content-length"),
    )

    # Add performance header to response
    response.headers["X-Process-Time"] = str(process_time_seconds)

    return response
