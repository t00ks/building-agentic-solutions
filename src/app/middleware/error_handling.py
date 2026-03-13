"""
Error handling middleware for consistent exception management.

This middleware provides:
- Global exception catching and logging
- Consistent error response formatting
- Error classification and appropriate status codes
- Security-conscious error message sanitization
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from core.exceptions import AgentException
from core.logging_config import get_logger


async def error_handling_middleware(request: Request, call_next) -> Response:
    """
    Middleware to handle exceptions and provide consistent error responses.

    This middleware catches all unhandled exceptions and:
    1. Logs the exception with full context
    2. Returns appropriate HTTP status codes
    3. Provides sanitized error messages to clients
    4. Handles both application-specific and generic exceptions

    Args:
        request (Request): The incoming FastAPI request
        call_next: The next middleware/handler in the chain

    Returns:
        Response: Either the successful response or an error response
    """
    try:
        response = await call_next(request)
        return response
    except AgentException as e:
        # Handle known application exceptions
        get_logger("api.error").warning(
            "Agent exception occurred",
            exception_type=type(e).__name__,
            error_message=str(e),
            path=request.url.path,
            method=request.method,
        )

        # Return appropriate status code based on exception type
        status_code = getattr(e, "status_code", 500)

        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Agent processing error",
                "message": str(e),
                "type": type(e).__name__,
            },
        )
    except Exception as e:
        # Handle unexpected exceptions
        get_logger("api.error").error(
            "Uncaught exception occurred",
            exception_type=type(e).__name__,
            path=request.url.path,
            method=request.method,
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "message": "An unexpected error occurred"},
        )
