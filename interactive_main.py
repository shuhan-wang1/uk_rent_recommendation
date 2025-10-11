# interactive_main.py

import asyncio
import json
from data_loader import get_live_properties, filter_by_budget
# Switched from gemini_interface to ollama_interface
# from gemini_interface import clarify_and_extract_criteria, generate_recommendations, refine_criteria_with_answer
from ollama_interface import clarify_and_extract_criteria, generate_recommendations, refine_criteria_with_answer
from enrichment import enrich_property_data
# from maps_service import calculate_travel_time
from free_maps_service import calculate_travel_time

from user_session import add_to_favorites, print_favorites, add_to_history
from location_resolver import get_best_location_id  # NEW IMPORT

# Global test switch
IS_TEST_MODE = True
TEST_PROPERTY_LIMIT = 25

# REMOVED: The old LOCATION_TO_ID_MAP is no longer needed!


async def find_apartments_interactive(criteria: dict): # 这个函数的作用就是可能会遇到I/O等待，允许等待的时候去做其他的任务
    """
    TWO-STAGE APPROACH:
    1. Quick filter using estimated travel times
    2. Accurate calculation only for top candidates
    """
    from location_resolver import get_best_location_id
    
    suggested_locations = criteria.get('suggested_search_locations', [])
    city_context = criteria.get('city_context', 'London')
    
    search_location_id, search_radius = get_best_location_id(
        suggested_locations, 
        fallback_city=city_context
    )
    
    print(f"\n[INFO] Searching in: {city_context}")
    print(f"[INFO] Using Location ID: {search_location_id} with radius: {search_radius} miles")

    print("\nStep 2: Performing live property search and filtering...")
    scraper_limit = TEST_PROPERTY_LIMIT if IS_TEST_MODE else None # 25
    
    all_properties = get_live_properties(
        location_id=search_location_id,
        radius=search_radius,
        min_price=1000,
        max_price=criteria.get('max_budget', 2000) + 200,
        limit=scraper_limit
    )
    print(f" -> Retrieved {len(all_properties)} total properties from scrapers.")
    '''
    [{'Price': '£1,250 pcm', 'Address': 'Antigallican, London, SE7', 'Description': 'Studio flat', 'URL': 'https://www.rightmove.co.uk/properties/167994398#/?channel=RES_LET', 'Available From': 'Ask agent', 'Images': ['https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/239k/238769/167994398/238769_VAC009ANTI_IMG_00_0000_max_476x317.jpeg', 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/239k/238769/167994398/238769_VAC009ANTI_IMG_01_0000_max_476x317.jpeg', 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/239k/238769/167994398/238769_VAC009ANTI_IMG_02_0000_max_476x317.jpeg', 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/239k/238769/167994398/238769_VAC009ANTI_IMG_03_0000_max_476x317.jpeg', 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/239k/238769/167994398/238769_VAC009ANTI_IMG_04_0000_max_476x317.jpeg', 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/239k/238769/167994398/238769_VAC009ANTI_IMG_05_0000_max_476x317.jpeg'], 'Platform': 'Rightmove', 'parsed_price': 1250.0, 'postcode': None}]
    '''
    budget_filtered = filter_by_budget(all_properties, criteria.get('max_budget', 2000))
    print(f" -> Found {len(budget_filtered)} properties within budget.") # 使用budget来filter，形状是list of dict
    
    if not budget_filtered:
        return (None, [])

    # STAGE 1: Quick filter using simple distance estimation
    print("\nStep 3a: Quick filtering by estimated travel time...")
    from free_maps_service import estimate_travel_time_simple # 通过免费的API进行简单估算
    
    max_travel_time = criteria.get('max_travel_time', 40)
    quick_candidates = []
    
    for prop in budget_filtered:
        estimated_time = estimate_travel_time_simple(
            prop.get('Address', ''), 
            criteria.get('destination')
        ) # 没有标出使用哪种交通方式，默认是transit
        
        if estimated_time and estimated_time <= max_travel_time + 10:  # Add 10 min buffer
            prop['estimated_time'] = estimated_time
            quick_candidates.append(prop)
    
    print(f" -> {len(quick_candidates)} properties pass quick filter")
    print(quick_candidates)
    
    if not quick_candidates:
        print("No properties within estimated travel time.")
        return (None, [])
    
    # STAGE 2: Accurate travel times for top candidates only
    print("\nStep 3b: Getting accurate travel times for top candidates...")
    '''
    先根据快速估算的通勤时间排序
    挑选前15个最有希望的房源，避免后面计算太慢
    并发计算准确通勤时间
    '''
    
    # Sort by estimated time and take top 15 
    quick_candidates.sort(key=lambda x: x.get('estimated_time', 999))
    top_candidates = quick_candidates[:15] # 形状是list of dict
    
    loop = asyncio.get_running_loop() # 并行执行
    # loop.run_in_executor(executor, func, *args)
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
    
    enrichment_candidates = []
    for prop, travel_time in zip(top_candidates, travel_times):
        if isinstance(travel_time, Exception):
            travel_time = prop.get('estimated_time')  # Use estimate if accurate fails
        
        if travel_time and travel_time <= max_travel_time:
            prop['travel_time_minutes'] = travel_time
            enrichment_candidates.append(prop)
            print(f"   ✓ {prop.get('Address')[:50]}... ({travel_time} mins)")
    print(enrichment_candidates)

    if not enrichment_candidates:
        print("No properties found within accurate travel time.")
        return (None, [])

    print(f"\n -> Found {len(enrichment_candidates)} final candidates. Starting enrichment...")
    # 在已经筛选出来的候选房源基础上，进一步补充和加工额外的信息，让推荐结果更完整、更符合用户偏好
    
    enrichment_tasks = [enrich_property_data(prop, criteria) for prop in enrichment_candidates]
    final_candidates = await asyncio.gather(*enrichment_tasks) # 形状是list of dict
    print(final_candidates)
    
    print(f"\nStep 4: Generating recommendations...")
    soft_preferences = criteria.get("soft_preferences", "")
    
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