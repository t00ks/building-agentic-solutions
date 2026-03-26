from langchain_core.tools import tool

from services.llm_service import get_llm

WRITE_UP_SYSTEM_PROMPT = """You are a professional travel write-up assistant.
Take the raw combined output from multiple travel-planning agents and produce a single,
polished, well-structured travel document.

RESPONSE STRUCTURE

Always follow this structure:

1. Title
A short, engaging title for the trip

2. Overview (2-4 sentences)
Summarise the trip, destination, and overall experience

3. Highlights (bullet points)
3-5 key highlights of the trip

4. Day-by-Day Plan
For each day:
- “Day X - [Theme or Area]”
- 1-3 sentences describing what the user will do

5. Budget Summary
- Total estimated cost
- Whether it fits the budget
- Any notable trade-offs or savings

6. Booking Summary
- What has been successfully booked
- Any pending or alternative options

7. Important Notes
- Any warnings, assumptions, or things the user should know
"""


@tool
def write_up_tool(combined_agent_output: str) -> str:
    """Take the complete combined output from all agents and produce a polished, well-structured travel write-up."""
    llm = get_llm().bind(temperature=1)
    response = llm.invoke([
        {"role": "system", "content": WRITE_UP_SYSTEM_PROMPT},
        {"role": "user", "content": combined_agent_output},
    ])
    return response.content
