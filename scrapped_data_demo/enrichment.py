# enrichment.py

import asyncio
from free_maps_service import (
    calculate_travel_time, 
    find_nearby_places, 
    get_crime_data_by_location,
    get_environmental_data
)
from web_search import search_cost_of_living
from ollama_interface import extract_tags_from_description

async def enrich_property_data(property_dict: dict, criteria: dict) -> dict:
    """
    MODIFIED: This is now the central hub for all data enrichment.
    1.  It's fully asynchronous and robust, using `gather` with `return_exceptions=True`.
    2.  It calls all new and updated services (`environmental`, `smarter crime`, `flexible amenities`).
    3.  It enriches the property with tags extracted from its description by Gemini.
    """
    enriched_prop = property_dict.copy()
    address = enriched_prop.get('Address')
    postcode = enriched_prop.get('postcode')
    description = enriched_prop.get('Description', '')
    destination = criteria.get('destination')
    amenities = criteria.get('amenities_of_interest', ['supermarket', 'park', 'gym']) # Default amenities

    # If address is missing, we can't do much enrichment.
    if not address:
        return enriched_prop
        
    loop = asyncio.get_running_loop()

    print(f"  -> Starting deep enrichment for: {address}")

    # Create a list of all data-fetching tasks to run concurrently
    tasks = {
        'cost_of_living': loop.run_in_executor(None, search_cost_of_living, postcode or address),
        'amenities_nearby': loop.run_in_executor(None, find_nearby_places, address, amenities),
        'crime_data_summary': loop.run_in_executor(None, get_crime_data_by_location, address),
        'environmental_data': loop.run_in_executor(None, get_environmental_data, address),
        'description_tags': loop.run_in_executor(None, extract_tags_from_description, description if isinstance(description, str) else ""),
        # Add multiple travel modes
        'travel_time_transit': loop.run_in_executor(None, calculate_travel_time, address, destination, "transit"),
        'travel_time_cycling': loop.run_in_executor(None, calculate_travel_time, address, destination, "bicycling"),
    }
    
    # Run all tasks concurrently and wait for them to complete
    # return_exceptions=True ensures that even if one API fails, the others complete
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    
    # Safely map results back to the property dictionary
    results_map = dict(zip(tasks.keys(), results))
    
    for key, value in results_map.items():
        if isinstance(value, Exception):
            print(f"    - WARNING: Failed to get '{key}' for {address}. Reason: {value}")
            enriched_prop[key] = {"error": str(value)}
        else:
            # If the result is a dictionary, update the main dict, otherwise set the key
            if isinstance(value, dict):
                enriched_prop.update(value)
            else:
                enriched_prop[key] = value
            
    return enriched_prop