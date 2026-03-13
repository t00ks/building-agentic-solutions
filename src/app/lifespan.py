from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agents.orchestration_agent import OrchestrationAgent
from core.config import get_config
from core.exceptions import AgentResourceError
from core.logging_config import get_logger
from services.checkpoints_ttl_service import schedule_checkpoints_ttl, shutdown_checkpoints_ttl

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up the checkpointer via async context, then persist
    try:
        schedule_checkpoints_ttl(app)  # Set up TTL scrubbing of short term memory according to config.
        config = get_config()
        serde = JsonPlusSerializer(pickle_fallback=True)
        cp_cm = AsyncPostgresSaver.from_conn_string(config.database.postgres_uri, serde=serde)
        cp = await cp_cm.__aenter__()
        await cp.setup()
        app.state.orchestration_agent = await OrchestrationAgent.create(cp, "agents_config.json")
        logger.info("API startup completed")
        yield
    except Exception as e:
        raise AgentResourceError("Failed to set up checkpointer and orchestration agent") from e

    # Shutdown code to release resources.
    shutdown_checkpoints_ttl(app)
    logger.info("API shutdown completed")
