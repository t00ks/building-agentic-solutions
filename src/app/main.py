from fastapi import FastAPI

from core.logging_config import configure_structlog
from middleware.registry import register_middleware
from routers.step1_router import router as step1_router
from routers.step2_router import router as step2_router
from routers.step3_router import router as step3_router
from routers.step4_router import router as step4_router
from routers.step5_router import router as step5_router

configure_structlog()

app = FastAPI(title="CGI LangGraph Agentic Framework API", description="Multi-agent system for knowledge retrieval and form population", version="1.0.0")

# Register all middleware
register_middleware(app)

# Register routers
app.include_router(step1_router)
app.include_router(step2_router)
app.include_router(step3_router)
app.include_router(step4_router)
app.include_router(step5_router)
