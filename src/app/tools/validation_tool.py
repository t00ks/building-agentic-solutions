import json
import re

from langchain_core.tools import tool
from langgraph.config import get_stream_writer

from core.logging_config import get_logger
from core.utils import extract_content_as_string, load_prompt_template
from services.llm_service import get_llm
from tools.tool_update import ToolUpdate

PROMPT_TEMPLATE: str = load_prompt_template("validation_tool_prompt.md")
OUTPUT_SANITISATION_REGEX = re.compile(r"^```(json|)((\n)|\\n)|((\n)|\\n)```$", re.S)


@tool(parse_docstring=True)
async def validate_input(agent_output: str) -> dict:
    """
    Validate the input from the agent and return the validation result. The validator returns
    a dictionary with the following structure:
        {
            "state": "Accepted" | "Rejected" | "Accepted with Changes",
            "required_changes": [list of required changes if any],  
            "breach_detail": "Details of the breach if rejected"
        }

    Args:
        agent_output: The output from the agent to be validated.
    """
    logger = get_logger(__name__)

    prompt = PROMPT_TEMPLATE.replace("##AGENT_OUTPUT##", agent_output)

    llm = get_llm().bind(temperature=1)

    output = await llm.ainvoke([{"role": "user", "content": prompt}])
    output_text = extract_content_as_string(output)
    output_text = OUTPUT_SANITISATION_REGEX.sub("", output_text).strip()

    parsed_output = json.loads(output_text)

    state = parsed_output.get("state", "Rejected")
    required_changes = parsed_output.get("required_changes", [])

    breach_detail: str = ""
    if state.lower() == "rejected":
        breach_detail = parsed_output.get("breach_detail", "No details provided")
        logger.warning(f"Guardrail breach detected: {breach_detail}")

    writer = get_stream_writer()
    writer(ToolUpdate(tool_name="validate_input", tool_data=[state, breach_detail, *required_changes]))

    return {"state": state, "required_changes": required_changes, "breach_detail": breach_detail}
