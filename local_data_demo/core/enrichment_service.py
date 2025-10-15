# enrichment.py - FIXED VERSION

import asyncio
from .maps_service import (
    calculate_travel_time,
    find_nearby_places, 
    get_crime_data_by_location,
    get_environmental_data
)
from .web_search import search_cost_of_living

async def enrich_property_data(property_dict: dict, criteria: dict) -> dict:
    """
    FIXED: Central hub for data enrichment.
    Now properly preserves nested crime data structure.
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
            # CRITICAL FIX: Keep crime data nested, don't flatten
            if key == 'crime_data_summary':
                print(f"    -> Crime data: {value}")
                enriched_prop['crime_data_summary'] = value  # ✅ Keep nested!
            elif isinstance(value, dict) and key not in ['amenities_nearby', 'environmental_data']:
                # For other dict results, we can flatten
                enriched_prop.update(value)
            else:
                enriched_prop[key] = value
            
    return enriched_prop