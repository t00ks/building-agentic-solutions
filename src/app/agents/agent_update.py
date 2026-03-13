from enum import Enum
from typing import Any


class AgentUpdateEvent(Enum):
    START = "start"
    FINISH = "finish"

class AgentUpdate:
    def __init__(
        self,
        agent_name: str,
        agent_event: AgentUpdateEvent,
    ):
        self.agent_name: str = agent_name
        self.agent_event: AgentUpdateEvent = agent_event

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_event": self.agent_event.value
        }