from contextvars import ContextVar

import structlog
from mcp import ClientSession

CURRENT_MCP_SESSION = ContextVar[ClientSession]("CURRENT_MCP_SESSION")
CONVERSATION_ID = ContextVar[str]("CONVERSATION_ID")


class SessionContext:
    """
    Context manager to set and reset the current MCP session in context.

    This is useful for ensuring that the MCP session is available in the current
    context for the duration of a request or operation, and is properly cleaned up
    afterwards.

    Example usage:
        async with SessionContext(mcp_session):
            # Within this block, CURRENT_MCP_SESSION.get() will return mcp_session
            ...

    Args:
        mcp_session (ClientSession): The MCP session to set in context.
    """

    def __init__(self, mcp_session: ClientSession, conversation_id: str):
        self.mcp_session = mcp_session
        self.mcp_session_token = None

        self.conversation_id = conversation_id
        self.conversation_id_token = None

        self.structlog_tokens = None

    async def __aenter__(self):
        self.mcp_session_token = CURRENT_MCP_SESSION.set(self.mcp_session)
        self.conversation_id_token = CONVERSATION_ID.set(self.conversation_id)

        self.structlog_tokens = structlog.contextvars.bind_contextvars(
            conversation_id=self.conversation_id
        )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.structlog_tokens:
            structlog.contextvars.reset_contextvars(**self.structlog_tokens)
        if self.mcp_session_token:
            CURRENT_MCP_SESSION.reset(self.mcp_session_token)
        if self.conversation_id_token:
            CONVERSATION_ID.reset(self.conversation_id_token)
