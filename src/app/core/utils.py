from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from langchain.agents.middleware import AgentState, before_model
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import (
    REMOVE_ALL_MESSAGES,
)
from langgraph.runtime import Runtime

from core.exceptions import AgentResourceError
from core.logging_config import get_logger

logger = get_logger(__name__)


def add_date_to_prompt_template(template: str) -> str:
    """Inject dynamic values (date) into prompt template."""
    current_date_iso = datetime.now(UTC).date().isoformat()
    return template.replace("<<CURRENT_DATE_ISO>>", current_date_iso)


def load_prompt_template(prompt_filename: str) -> str:
    base_dir: Path = Path(__file__).parent.parent

    try:
        prompt_path = base_dir / "prompts" / prompt_filename
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise AgentResourceError("Failed to load prompt template") from e


def extract_content_as_string(response: BaseMessage) -> str:
    """
    Extract string content from ChatBedrockConverse response regardless of format.

    Handles various response formats including strings, lists of content blocks,
    and structured message objects to ensure consistent string output.

    Args:
        response (BaseMessage): The message response from ChatBedrockConverse.

    Returns:
        str: Extracted string content from the response.
    """
    content = response.content

    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Handle list of strings/dicts
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif hasattr(item, "content"):
                parts.append(str(item.content))  # type: ignore
        return "".join(parts)
    else:
        return str(content)


def build_before_model_middleware(agent_name: str) -> Callable[[AgentState], AgentState | dict[str, list[BaseMessage]]]:
    HISTORY_MESSAGE_PREFIX: str = "Here is the summary of our conversation so far."
    history_message: str = f"{HISTORY_MESSAGE_PREFIX}\nThis is for reference only:\n"

    def is_instanceof_history_message(message: BaseMessage) -> bool:
        return message.content.startswith(HISTORY_MESSAGE_PREFIX)

    @before_model
    def before_model_middleware(state: AgentState, runtime: Runtime):
        messages = state["messages"]

        if len([m for m in messages if isinstance(m, HumanMessage)]) < 2 or (
            len([m for m in messages if isinstance(m, HumanMessage)]) < 3 and is_instanceof_history_message(messages[0])
        ):
            return

        summary_text: str | None = None
        if is_instanceof_history_message(messages[0]):
            summary_text = messages[0].content
            messages = messages[1:]
        else:
            summary_text = history_message

        last_user_message = extract_content_as_string(messages[0])
        last_ai_message = extract_content_as_string(messages[-2])

        summary_text += f"---\nUser: {last_user_message}\nAssistant: {last_ai_message}\n"

        chunked_history = summary_text.split("---")
        if chunked_history and len(chunked_history) > 6:
            summary_text = chunked_history[0] + "---" + "---".join(chunked_history[1:][-6:])

        summary_message = [HumanMessage(content=summary_text)]
        preserved_messages = messages[-1:]

        logger.debug(f"[{agent_name}] Reduced message history for model call.\n{preserved_messages}\n{summary_text}")

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *summary_message,
                *preserved_messages,
            ]
        }

    return before_model_middleware
