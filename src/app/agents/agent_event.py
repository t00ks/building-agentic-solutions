
from typing import Any, Literal

EventType = Literal["response", "update", "done", "debug"]

class AgentEvent:
    def __init__(self, event_type: EventType, data: Any):
        self.event_type = event_type
        self.data = data