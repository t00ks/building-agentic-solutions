"""
Middleware registry for organizing and applying middleware in the correct order.

This module provides a centralized way to manage middleware application
with proper ordering and dependencies.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_config
from middleware.error_handling import error_handling_middleware
from middleware.logging import logging_middleware


def register_middleware(app: FastAPI) -> None:
    """
    Register all middleware with the FastAPI application in the correct order.

    Middleware is applied in reverse order of registration, so the first
    middleware registered will be the outermost (runs first on request,
    last on response).

    Desired execution order:
    1. Request context (runs first - sets up correlation ID and auth)
    2. Logging (runs second - has access to context)
    3. Error handling (runs last/outermost - catches all exceptions)

    Args:
        app (FastAPI): The FastAPI application instance
    """
    config = get_config()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register middleware in reverse order of execution
    # Last registered = first to run on request

    # Error handling middleware (runs last/outermost, catches all exceptions)
    app.middleware("http")(error_handling_middleware)

    # Logging middleware (runs second, has access to context)
    app.middleware("http")(logging_middleware)
