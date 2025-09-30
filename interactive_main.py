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

async def find_apartments_interactive(criteria: dict):
    """
    This is the core search and recommendation flow.
    MODIFIED: This function now robustly returns a tuple (recommendations, candidates) in all cases.
    """
    LOCATION_ID_FOR_SEARCH = "REGION^87490"  # London
    SEARCH_RADIUS = 5

    print("\nStep 2: Performing live property search and filtering...")
    scraper_limit = TEST_PROPERTY_LIMIT if IS_TEST_MODE else None
    
    all_properties = get_live_properties(
        location_id=LOCATION_ID_FOR_SEARCH, radius=SEARCH_RADIUS,
        min_price=1000, max_price=criteria.get('max_budget', 2000) + 200,
        limit=scraper_limit
    )
    budget_filtered = filter_by_budget(all_properties, criteria.get('max_budget', 2000))
    print(f" -> Found {len(budget_filtered)} properties within budget.")
    if not budget_filtered:
        # FIX: Always return a tuple
        return (None, [])

    print("\nStep 3: Concurrently enriching data and filtering by travel time...")
    max_travel_time = criteria.get('max_travel_time', 30)
    
    loop = asyncio.get_running_loop()
    travel_time_tasks = [
        loop.run_in_executor(None, calculate_travel_time, prop.get('Address', ''), criteria.get('destination'))
        for prop in budget_filtered
    ]
    travel_times = await asyncio.gather(*travel_time_tasks)
    
    enrichment_candidates = []
    for prop, travel_time in zip(budget_filtered, travel_times):
        # Ensure travel_time is not None before comparing
        if travel_time is not None and travel_time <= max_travel_time:
            prop['travel_time_minutes'] = travel_time
            enrichment_candidates.append(prop)
    
    if not enrichment_candidates:
        print("No properties found that match your travel time criteria.")
        # FIX: Always return a tuple
        return (None, [])

    print(f"\n -> Found {len(enrichment_candidates)} candidates. Starting deep enrichment...")
    enrichment_tasks = [enrich_property_data(prop, criteria.get('destination')) for prop in enrichment_candidates]
    final_candidates = await asyncio.gather(*enrichment_tasks)
    
    print(f"\nStep 4: Found {len(final_candidates)} final candidates. Generating recommendations...")
    soft_preferences = criteria.get("soft_preferences", "User did not specify any soft preferences.")
    recommendations = generate_recommendations(final_candidates, json.dumps(criteria), soft_preferences)
    
    add_to_history(criteria, len(final_candidates))
    
    return recommendations, final_candidates


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
            
            # The function now safely returns a tuple
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
                print("----------------------------------------------")
                
                # Feedback loop
                while True:
                    fav_input = input("\nEnter the RANK number of a property to add to favorites, or type 'search again' or 'exit'.\n> ")
                    if fav_input.lower() in ['search again', 'new search', 'refine search']:
                        criteria = None
                        break
                    if fav_input.lower() in ['exit', 'quit']:
                        return
                    try:
                        rank_to_fav = int(fav_input)
                        selected_rec = next((r for r in recs if r.get('rank') == rank_to_fav), None)
                        if selected_rec:
                            full_prop_data = next((p for p in final_candidates if p.get('Address') == selected_rec.get('address')), None)
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