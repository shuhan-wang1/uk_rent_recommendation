# recommender.py

import asyncio
from data_loader import get_live_properties, filter_by_budget
from gemini_interface import extract_criteria, generate_recommendations
from enrichment import enrich_property_data
from maps_service import calculate_travel_time

async def find_apartments(user_query: str, is_test: bool = False, test_limit: int = 5):
    """处理推荐过程的主函数 (异步版本)，增加了测试模式。"""
    
    print("Step 1: Analyzing your request with Gemini...")
    criteria = extract_criteria(user_query)
    if not criteria:
        print("Could not understand your request. Please try again.")
        return
    print(f" -> Criteria found: {criteria}")
    
    LOCATION_ID_FOR_SEARCH = "REGION^87490"
    SEARCH_RADIUS = 5

    print("\nStep 2: Performing live property search and filtering by budget...")
    
    # 在测试模式下，将限制数量传递给抓取函数
    scraper_limit = test_limit if is_test else None
    
    all_properties = get_live_properties(
        location_id=LOCATION_ID_FOR_SEARCH,
        radius=SEARCH_RADIUS,
        min_price=1000,
        max_price=criteria['max_budget'] + 200,
        limit=scraper_limit # 传递限制
    )
    budget_filtered = filter_by_budget(all_properties, criteria['max_budget'])
    print(f" -> Found {len(budget_filtered)} properties within budget.")
    if not budget_filtered:
        print("No properties found within your budget in the searched area.")
        return
        
    # 注意：之前在这里的截断逻辑已被移除，因为抓取时已经限制了数量

    print("\nStep 3: Concurrently enriching data and filtering by travel time...")
    final_candidates = []
    max_travel_time = criteria['max_travel_time']
    
    loop = asyncio.get_running_loop()
    travel_time_tasks = [
        loop.run_in_executor(None, calculate_travel_time, prop.get('Address', ''), criteria['destination'])
        for prop in budget_filtered
    ]
    travel_times = await asyncio.gather(*travel_time_tasks)
    
    enrichment_candidates = []
    for prop, travel_time in zip(budget_filtered, travel_times):
        address = prop.get('Address', 'Unknown Address')
        if travel_time and travel_time <= max_travel_time:
            prop['travel_time_minutes'] = travel_time
            enrichment_candidates.append(prop)
            print(f"   -> OK: {address} (Travel time: {travel_time} mins)")
        else:
            print(f"   -> Skipped: {address} (Travel time: {travel_time} mins)")

    if enrichment_candidates:
        print(f"\n -> Found {len(enrichment_candidates)} candidates. Starting deep enrichment (web search, places)...")
        enrichment_tasks = [
            enrich_property_data(prop, criteria['destination'])
            for prop in enrichment_candidates
        ]
        final_candidates = await asyncio.gather(*enrichment_tasks)
    
    if not final_candidates:
        print("No properties found that match your budget and travel time criteria.")
        return

    print(f"\nStep 4: Found {len(final_candidates)} final candidates. Generating recommendations...")
    recommendations = generate_recommendations(final_candidates, user_query)
    
    return recommendations