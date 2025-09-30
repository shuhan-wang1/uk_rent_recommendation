# interactive_main.py

import asyncio
import json
from data_loader import get_live_properties, filter_by_budget
from gemini_interface import clarify_and_extract_criteria, generate_recommendations, refine_criteria_with_answer
from enrichment import enrich_property_data
from maps_service import calculate_travel_time
from user_session import add_to_favorites, print_favorites, add_to_history

# Global test switch
IS_TEST_MODE = True
TEST_PROPERTY_LIMIT = 5

# --- FIX START ---
# Updated the map with a more precise and correct location ID for the UCL area.
# EUSTON SQUARE is a station right next to UCL. We will also update Bloomsbury's ID.
LOCATION_TO_ID_MAP = {
    "bloomsbury": "STATION^3317", # Corrected ID for Euston Square, representing Bloomsbury/UCL area
    "euston": "STATION^3314",
    "fitzrovia": "REGION^541",
    "king's cross": "STATION^4988",
    "soho": "REGION^1232",
    "shoreditch": "REGION^1203",
    "london bridge": "STATION^5459",
    "richmond": "REGION^1127",
    "hampstead": "REGION^641",
}
# --- FIX END ---


async def find_apartments_interactive(criteria: dict):
    """
    This is the core search and recommendation flow.
    MODIFIED: This function now robustly returns a tuple (recommendations, candidates) in all cases.
    OPTIMIZED: It now uses Gemini's suggested locations for a much more relevant search.
    """
    SEARCH_RADIUS = 5 # For a station, we can use a smaller, more focused radius like 0.5 miles
    
    suggested_locations = criteria.get('suggested_search_locations', [])
    search_location_id = "REGION^87490" # Default to London if no suggestions
    
    if suggested_locations:
        first_suggestion = suggested_locations[0].lower()
        found_id = LOCATION_TO_ID_MAP.get(first_suggestion)
        if found_id:
            search_location_id = found_id
            print(f"\n[INFO] Gemini suggested searching in '{first_suggestion.title()}', using ID: {search_location_id}")
        else:
            print(f"\n[WARN] Could not find a location ID for '{first_suggestion.title()}', defaulting to general London search.")

    print("\nStep 2: Performing live property search and filtering...")
    scraper_limit = TEST_PROPERTY_LIMIT if IS_TEST_MODE else None
    
    all_properties = get_live_properties(
        location_id=search_location_id, radius=SEARCH_RADIUS,
        min_price=1000, max_price=criteria.get('max_budget', 2000) + 200,
        limit=scraper_limit
    )
    budget_filtered = filter_by_budget(all_properties, criteria.get('max_budget', 2000))
    print(f" -> Found {len(budget_filtered)} properties within budget.")
    if not budget_filtered:
        return (None, [])

    print("\nStep 3: Concurrently enriching data and filtering by travel time...")
    max_travel_time = criteria.get('max_travel_time', 40)
    
    loop = asyncio.get_running_loop()
    travel_time_tasks = [
        loop.run_in_executor(None, calculate_travel_time, prop.get('Address', ''), criteria.get('destination'))
        for prop in budget_filtered
    ]
    travel_times = await asyncio.gather(*travel_time_tasks, return_exceptions=True)
    
    enrichment_candidates = []
    for prop, travel_time in zip(budget_filtered, travel_times):
        if isinstance(travel_time, Exception) or travel_time is None:
            print(f" - Skipping {prop.get('Address')} due to travel time calculation error.")
            continue
            
        if travel_time <= max_travel_time:
            prop['travel_time_minutes'] = travel_time
            enrichment_candidates.append(prop)
    
    if not enrichment_candidates:
        print("No properties found that match your travel time criteria.")
        return (None, [])

    print(f"\n -> Found {len(enrichment_candidates)} candidates. Starting deep enrichment...")
    
    enrichment_tasks = [enrich_property_data(prop, criteria) for prop in enrichment_candidates]
    
    final_candidates = await asyncio.gather(*enrichment_tasks)
    
    print(f"\nStep 4: Found {len(final_candidates)} final candidates. Generating recommendations...")
    soft_preferences = criteria.get("soft_preferences", "User did not specify any soft preferences.")
    
    recommendations_json = generate_recommendations(final_candidates, json.dumps(criteria), soft_preferences)
    
    add_to_history(criteria, len(final_candidates))
    
    return recommendations_json, final_candidates


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