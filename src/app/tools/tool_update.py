from typing import Any


class ToolUpdate:
    def __init__(
        self,
        tool_name: str,
        tool_data: list[str],
    ):
        self.tool_name: str = tool_name
        self.tool_data: list[str] = tool_data

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "tool_data": self.tool_data
        }