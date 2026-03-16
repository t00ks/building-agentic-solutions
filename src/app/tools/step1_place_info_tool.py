import random
from typing import TypedDict

from langchain_core.tools import tool

_rng = random.Random()


class PlaceInfo(TypedDict):
    name: str
    type: str
    open_hours: str
    avg_visit_minutes: int
    entry_fee_eur: float
    popularity_score: float
    description: str
    address: str


@tool
def place_info_tool(place_name: str) -> PlaceInfo:
    """Return basic info about a named place (mock)."""
    name_lower = place_name.lower()
    place_type = "museum" if "museum" in name_lower else "park" if "park" in name_lower else "attraction"
    avg_visit_minutes = 90 if place_type == "museum" else 45
    entry_fee_eur = 12.50 if place_type == "museum" else 0.0
    popularity_score = round(0.5 + _rng.random() * 0.5, 2)

    return {
        "name": place_name,
        "type": place_type,
        "open_hours": "09:00-18:00",
        "avg_visit_minutes": avg_visit_minutes,
        "entry_fee_eur": entry_fee_eur,
        "popularity_score": popularity_score,
        "description": f"Mock description for {place_name}. A popular {place_type}.",
        "address": f"123 {place_name} St.",
    }