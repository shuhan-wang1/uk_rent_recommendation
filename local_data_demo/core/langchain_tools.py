"""
LangChain Tool Wrappers

Thin @tool wrappers around existing tool implementations for LangGraph compatibility.
Each wrapper delegates to the existing async implementation functions and returns
JSON-serialized results.

NOTE: Actual tool execution in the LangGraph agent still goes through ToolRegistry
for retry logic, stats tracking, and input validation. These wrappers provide
schema definitions and are available for future direct use with bind_tools().
"""

import json
import asyncio
from langchain_core.tools import tool


@tool
async def search_properties(user_query: str, location: str = None, max_budget: float = None,
                             max_commute_time: int = None) -> str:
    """Search for rental properties from the database.
    Use when user wants to FIND/SHOW/SEARCH specific properties.

    Args:
        user_query: The user's search query in natural language
        location: University name or area (e.g., 'UCL', 'Bloomsbury')
        max_budget: Maximum monthly budget in GBP
        max_commute_time: Maximum commute time in minutes
    """
    from core.tools.search_properties import search_properties_tool
    result = await search_properties_tool.execute(
        user_query=user_query, location=location,
        max_budget=max_budget, max_commute_time=max_commute_time
    )
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def calculate_commute(origin: str, destination: str, mode: str = "transit") -> str:
    """Calculate commute time between two locations.

    Args:
        origin: Starting address
        destination: Destination address
        mode: Travel mode (transit, walking, cycling, driving)
    """
    from core.tools.calculate_commute import calculate_commute_tool
    result = await calculate_commute_tool.execute(origin=origin, destination=destination, mode=mode)
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def calculate_commute_cost(from_address: str, to_address: str,
                                  travel_type: str = "student", mode: str = "transit") -> str:
    """Calculate commute time AND monthly transport cost between two addresses.
    Use for specific commute cost analysis.

    Args:
        from_address: Full property address
        to_address: Destination address (e.g., university)
        travel_type: 'student' or 'adult'
        mode: Travel mode
    """
    from core.tools.calculate_commute_cost import calculate_commute_cost_tool
    result = await calculate_commute_cost_tool.execute(
        from_address=from_address, to_address=to_address,
        travel_type=travel_type, mode=mode
    )
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def check_safety(address: str, area: str = None, user_query: str = None) -> str:
    """Check crime statistics and safety score for a UK address.

    Args:
        address: Full street address including postcode
        area: Area name (alternative to address)
        user_query: Original user question for context
    """
    from core.tools.check_safety import check_safety_tool
    result = await check_safety_tool.execute(address=address, area=area, user_query=user_query)
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def get_weather(location: str) -> str:
    """Get current weather information for a location.

    Args:
        location: City name (e.g., 'London', 'Manchester')
    """
    from core.tools.get_weather import get_weather_tool
    result = await get_weather_tool.execute(location=location)
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def web_search(query: str) -> str:
    """Search the web for general information, advice, and comparisons.
    Results are filtered to authoritative sources for factual queries.

    Args:
        query: Search query (should be in English, include '2025' for current data)
    """
    from core.tools.web_search import web_search_tool
    result = await web_search_tool.execute(query=query)
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def search_nearby_pois(address: str, user_query: str = None,
                              radius: int = 1000, poi_type: str = None) -> str:
    """Search for nearby points of interest using OpenStreetMap.

    Args:
        address: Full street address to search around
        user_query: Original user question for context
        radius: Search radius in meters (default 1000)
        poi_type: Type of POI (supermarket, gym, restaurant, cafe, park, tube_station, etc.)
    """
    from core.tools.search_nearby_pois import search_nearby_pois_tool
    result = await search_nearby_pois_tool.execute(
        address=address, user_query=user_query,
        radius=radius, poi_type=poi_type
    )
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def get_property_details(property_name: str) -> str:
    """Get full details for a specific property from the database.

    Args:
        property_name: Name of the property (e.g., 'Scape Bloomsbury')
    """
    from core.tools.get_property_details import get_property_details_tool
    result = await get_property_details_tool.execute(property_name=property_name)
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


@tool
async def check_transport_cost(end_zone: int, travel_type: str = "student") -> str:
    """Get transport ticket prices for London zones.

    Args:
        end_zone: End zone number (1-6)
        travel_type: 'student' or 'adult'
    """
    from core.tools.check_transport_cost import check_transport_cost_tool
    result = await check_transport_cost_tool.execute(end_zone=end_zone, travel_type=travel_type)
    return json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False)


# Export all tool wrappers
ALL_TOOLS = [
    search_properties,
    calculate_commute,
    calculate_commute_cost,
    check_safety,
    get_weather,
    web_search,
    search_nearby_pois,
    get_property_details,
    check_transport_cost,
]
