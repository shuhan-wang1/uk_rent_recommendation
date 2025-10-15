# interactive_main.py

import asyncio
import json
from core.data_loader import get_live_properties, filter_by_budget
from core.llm_interface import clarify_and_extract_criteria, generate_recommendations, refine_criteria_with_answer
from core.enrichment_service import enrich_property_data
from core.maps_service import calculate_travel_time, estimate_travel_time_simple
from core.user_session import add_to_favorites, print_favorites, add_to_history
from core.location_service import get_rightmove_location_identifier

# Global test switch
IS_TEST_MODE = True
TEST_PROPERTY_LIMIT = 25

# REMOVED: The old LOCATION_TO_ID_MAP is no longer needed!


async def find_apartments_interactive(criteria: dict):
    """
    TWO-STAGE APPROACH:
    1. Quick filter using estimated travel times
    2. Accurate calculation only for top candidates
    """
    
    suggested_locations = criteria.get('suggested_search_locations', [])
    city_context = criteria.get('city_context', 'London')
    
    # Use the first suggested location, or fallback to city context
    location_to_search = suggested_locations[0] if suggested_locations else city_context
    search_location_id = get_rightmove_location_identifier(location_to_search)
    
    # If no specific location ID found, default to London
    if not search_location_id:
        print(f"[WARN] Could not find specific location ID for '{location_to_search}'. Defaulting to London.")
        search_location_id = 'REGION^87490'
        search_radius = 5.0
    else:
        search_radius = 5.0
    
    print(f"\n[INFO] Searching in: {city_context}")
    print(f"[INFO] Using Location ID: {search_location_id} with radius: {search_radius} miles")

    print("\nStep 2: Performing live property search and filtering...")
    scraper_limit = TEST_PROPERTY_LIMIT if IS_TEST_MODE else None
    
    all_properties = get_live_properties(
        location_id=search_location_id,
        radius=search_radius,
        min_price=1000,
        max_price=criteria.get('max_budget', 2000) + 200,
        limit=scraper_limit
    )
    
    budget_filtered = filter_by_budget(all_properties, criteria.get('max_budget', 2000))
    print(f" -> Found {len(budget_filtered)} properties within budget.")
    
    if not budget_filtered:
        return (None, [])

    # STAGE 1: Quick filter using simple distance estimation
    print("\nStep 3a: Quick filtering by estimated travel time...")
    
    max_travel_time = criteria.get('max_travel_time', 40)
    
    # If travel time is unlimited (999), we skip the time filter entirely.
    if max_travel_time >= 999:
        print(" -> Travel time is unlimited, skipping time-based filtering.")
        quick_candidates = budget_filtered
        for prop in quick_candidates:
            prop['estimated_time'] = 0 # Set a default value
    else:
        quick_candidates = []
        for prop in budget_filtered:
            estimated_time = estimate_travel_time_simple(
                prop.get('Address', ''), 
                criteria.get('destination')
            )
            
            # Add a 10-minute buffer to the check
            if estimated_time and estimated_time <= max_travel_time + 10:
                prop['estimated_time'] = estimated_time
                quick_candidates.append(prop)
    
    print(f" -> {len(quick_candidates)} properties pass quick filter")
    
    if not quick_candidates:
        print("No properties within estimated travel time.")
        return (None, [])
    
    # STAGE 2: Accurate travel times for top candidates only
    enrichment_candidates = []
    
    # If travel time is unlimited, all quick candidates are final candidates.
    if max_travel_time >= 999:
        print("\nStep 3b: Bypassing accurate travel time check due to unlimited preference.")
        for prop in quick_candidates:
            prop['travel_time_minutes'] = 0 # Set a default of 0 for display
        enrichment_candidates = quick_candidates
    else:
        print("\nStep 3b: Getting accurate travel times for top candidates...")
        
        # Sort by estimated time and take top 15 for accurate checks
        quick_candidates.sort(key=lambda x: x.get('estimated_time', 999))
        top_candidates = quick_candidates[:15]
        
        loop = asyncio.get_running_loop()
        travel_time_tasks = [
            loop.run_in_executor(
                None, 
                calculate_travel_time, 
                prop.get('Address', ''), 
                criteria.get('destination')
            )
            for prop in top_candidates
        ]
        
        travel_times = await asyncio.gather(*travel_time_tasks, return_exceptions=True)
        
        for prop, travel_time in zip(top_candidates, travel_times):
            if isinstance(travel_time, Exception):
                travel_time = prop.get('estimated_time') # Fallback to estimate
            
            if travel_time and travel_time <= max_travel_time:
                prop['travel_time_minutes'] = travel_time
                enrichment_candidates.append(prop)
                print(f"   ✓ {prop.get('Address')[:50]}... ({travel_time} mins)")
    
    if not enrichment_candidates:
        print("No properties found within accurate travel time.")
        return (None, [])

    print(f"\n -> Found {len(enrichment_candidates)} final candidates. Starting enrichment...")
    
    enrichment_tasks = [enrich_property_data(prop, criteria) for prop in enrichment_candidates]
    final_candidates = await asyncio.gather(*enrichment_tasks)
    
    print(f"\nStep 4: Generating recommendations...")
    soft_preferences = criteria.get("soft_preferences") or ""
    
    recommendations_json = generate_recommendations(final_candidates, json.dumps(criteria), soft_preferences)
    
    add_to_history(criteria, len(final_candidates))
    
    return recommendations_json, final_candidates

# The main_loop() function remains the same - no changes needed!


async def main_loop():
    """Interactive command-line loop."""
    print("Welcome to the Smart Apartment Finder!")
    
    criteria = None
    original_query = ""

    while True:
        if not criteria:
            user_input = input("\nHow can I help you find an apartment today?\n> ")
            original_query = user_input
        else:
            user_input = input("\nWhat would you like to do next? (e.g., 'refine search', 'view favorites', 'exit')\n> ")

        if user_input.lower() in ['exit', 'quit']:
            print("Thank you for using the finder. Goodbye!")
            break
        
        if user_input.lower() in ['view favorites', 'favorites', 'favs']:
            print_favorites()
            continue
            
        if not criteria:
            response = clarify_and_extract_criteria(user_input)
        else:
            response = refine_criteria_with_answer(json.dumps(criteria), user_input)

        if response.get('status') == 'clarification_needed':
            clarification_question = response['data']['question']
            user_answer = input(f"\n[ASSISTANT] {clarification_question}\n> ")
            response = refine_criteria_with_answer(original_query, user_answer)

        if response.get('status') == 'success':
            criteria = response['data']
            print(f"\nGreat! I will start searching with the following criteria: \n{json.dumps(criteria, indent=2)}")
            
            recommendations, final_candidates = await find_apartments_interactive(criteria)
            
            if recommendations and 'recommendations' in recommendations:
                print("\n==============================================")
                print("         APARTMENT RECOMMENDATIONS")
                print("==============================================")
                recs = recommendations['recommendations']
                for rec in recs:
                    print(f"\n--- RANK {rec.get('rank', 'N/A')} ---")
                    print(f"Address: {rec.get('address', 'N/A')}")
                    print(f"Price: {rec.get('price', 'N/A')}")
                    print(f"Travel Time: {rec.get('travel_time', 'N/A')} minutes")
                    print("\nExplanation:")
                    print(rec.get('explanation', 'No explanation provided.'))
                    print(f"URL: {rec.get('url', 'N/A')}")
                print("----------------------------------------------")
                
                while True:
                    fav_input = input("\nEnter the RANK number to add to favorites, or 'search again'/'exit'.\n> ")
                    if fav_input.lower() in ['search again', 'new search', 'refine search']:
                        criteria = None
                        break
                    if fav_input.lower() in ['exit', 'quit']:
                        return
                    try:
                        rank_to_fav = int(fav_input)
                        selected_rec = next((r for r in recs if r.get('rank') == rank_to_fav), None)
                        if selected_rec:
                            full_prop_data = next((p for p in final_candidates if p.get('URL') == selected_rec.get('url')), None)
                            if full_prop_data:
                                add_to_favorites(full_prop_data)
                            else:
                                print("Could not find full property data to favorite.")
                        else:
                            print(f"Invalid rank number. Please choose from {[r.get('rank') for r in recs]}.")
                    except (ValueError, StopIteration):
                        print("Invalid input. Please enter a number, 'search again', or 'exit'.")

            else:
                print("\nSorry, I could not generate any recommendations based on your criteria.")
                criteria = None
        else:
            print("I'm sorry, I'm having trouble understanding. Let's try again.")
            criteria = None


if __name__ == "__main__":
    asyncio.run(main_loop())