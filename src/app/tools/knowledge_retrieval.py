from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from core.logging_config import get_logger
from services.vector_store import KnowledgeStore
from tools.tool_update import ToolUpdate


@tool
def knowledge_retrieval(user_query: str) -> str:
    """Returns a list of relevant context chunks to the user's query about mortgage knowledge."""

    logger = get_logger(__name__)

    store = KnowledgeStore()
    context_chunks = store.retrieve_context(user_query, search_variations=False)

    logger.info(f"Retrieved {len(context_chunks)} context chunks for query.")

    # write out chunks to custom stream channel
    writer = get_stream_writer()
    writer(ToolUpdate(tool_name="knowledge_retrieval", tool_data=context_chunks))

    return "\n\n".join(context_chunks)
