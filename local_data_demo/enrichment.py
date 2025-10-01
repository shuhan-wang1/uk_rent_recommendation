# enrichment.py - OPTIMIZED VERSION (removes slow tag extraction)

import asyncio
from travel_service import calculate_travel_time
from maps_service import (
    find_nearby_places, 
    get_crime_data_by_location,
    get_environmental_data
)
from web_search import search_cost_of_living
# Don't import extract_tags_from_description - it's too slow and not used
async def enrich_property_data(property_dict: dict, criteria: dict) -> dict:
    """
    OPTIMIZED: Central hub for data enrichment.
    """
    enriched_prop = property_dict.copy()
    address = enriched_prop.get('Address')
    postcode = enriched_prop.get('postcode')
    description = enriched_prop.get('Description', '')
    destination = criteria.get('destination')
    amenities = criteria.get('amenities_of_interest', ['supermarket', 'park', 'gym'])

    if not address:
        return enriched_prop
        
    loop = asyncio.get_running_loop()

    print(f"  -> Enriching: {address[:50]}")

    tasks = {
        'cost_of_living': loop.run_in_executor(None, search_cost_of_living, postcode or address),
        'amenities_nearby': loop.run_in_executor(None, find_nearby_places, address, amenities),
        'crime_data_summary': loop.run_in_executor(None, get_crime_data_by_location, address),
        'environmental_data': loop.run_in_executor(None, get_environmental_data, address),
    }
    
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    results_map = dict(zip(tasks.keys(), results))
    
    for key, value in results_map.items():
        if isinstance(value, Exception):
            print(f"    ⚠️  Failed to get '{key}': {value}")
            enriched_prop[key] = {"error": str(value)}
        else:
            # ADD THIS DEBUG LINE
            if key == 'crime_data_summary':
                print(f"    -> Crime data: {value}")
            
            if isinstance(value, dict):
                enriched_prop.update(value)
            else:
                enriched_prop[key] = value
            
    return enriched_prop