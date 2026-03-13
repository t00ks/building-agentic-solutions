class AgentException(Exception):
    """Base exception for agent-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class AgentConfigurationError(AgentException):
    """Raised when agent configuration is invalid."""
    pass

class AgentProcessingError(AgentException):
    """Raised when agent processing fails."""
    pass

class AgentResourceError(AgentException):
    """Raised when external resources (DB, MCP, etc.) fail."""
    pass