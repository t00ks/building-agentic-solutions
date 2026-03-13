from fastapi import FastAPI

from core.logging_config import configure_structlog
from lifespan import lifespan
from middleware.registry import register_middleware
from routers.orchestrator_router import router as orchestrator_router
from routers.voice_router import router as voice_router

configure_structlog()

app = FastAPI(
    title="CGI LangGraph Agentic Framework API",
    description="Multi-agent system for knowledge retrieval and form population",
    version="1.0.0",
    lifespan=lifespan,
)

# Register all middleware
register_middleware(app)

# Register routers
app.include_router(orchestrator_router, prefix="")
app.include_router(voice_router)
