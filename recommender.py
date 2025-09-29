# recommender.py

import asyncio
from data_loader import get_live_properties, filter_by_budget
from gemini_interface import extract_criteria, generate_recommendations
from enrichment import enrich_property_data
from maps_service import calculate_travel_time

async def find_apartments(user_query: str):
    """处理推荐过程的主函数 (异步版本)。"""
    
    # 步骤 1: 使用 Gemini 理解用户请求
    print("Step 1: Analyzing your request with Gemini...")
    criteria = extract_criteria(user_query)
    if not criteria:
        print("Could not understand your request. Please try again.")
        return
    print(f" -> Criteria found: {criteria}")
    
    # 为了演示，我们需要一个从目的地名称(如UCL)到Rightmove ID的转换。
    # 这是一个复杂的问题，这里我们硬编码一个ID。
    # REGION^87490 代表 London
    LOCATION_ID_FOR_SEARCH = "REGION^87490"
    SEARCH_RADIUS = 5 # 英里

    # 步骤 2: 实时抓取房源数据并按预算初步筛选
    print("\nStep 2: Performing live property search and filtering by budget...")
    all_properties = get_live_properties(
        location_id=LOCATION_ID_FOR_SEARCH,
        radius=SEARCH_RADIUS,
        min_price=1000, # 可以设置一个合理的最低价以减少结果
        max_price=criteria['max_budget'] + 200 # 稍微放宽范围
    )
    budget_filtered = filter_by_budget(all_properties, criteria['max_budget'])
    print(f" -> Found {len(budget_filtered)} properties within budget.")
    if not budget_filtered:
        print("No properties found within your budget in the searched area.")
        return

    # 步骤 3: 异步丰富化数据并按出行时间二次筛选
    print("\nStep 3: Concurrently enriching data and filtering by travel time...")
    final_candidates = []
    max_travel_time = criteria['max_travel_time']
    
    # 首先，并行计算所有房源的出行时间
    loop = asyncio.get_running_loop()
    travel_time_tasks = [
        loop.run_in_executor(None, calculate_travel_time, prop.get('Address', ''), criteria['destination'])
        for prop in budget_filtered
    ]
    travel_times = await asyncio.gather(*travel_time_tasks)
    
    # 筛选出符合出行时间的房源
    enrichment_candidates = []
    for prop, travel_time in zip(budget_filtered, travel_times):
        address = prop.get('Address', 'Unknown Address')
        if travel_time and travel_time <= max_travel_time:
            prop['travel_time_minutes'] = travel_time
            enrichment_candidates.append(prop)
            print(f"   -> OK: {address} (Travel time: {travel_time} mins)")
        else:
            print(f"   -> Skipped: {address} (Travel time: {travel_time} mins)")

    # 仅为符合条件的房源并行执行进一步的信息丰富化
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

    # 步骤 4: 将最终候选房源发送给 Gemini 进行排名和解释
    print(f"\nStep 4: Found {len(final_candidates)} final candidates. Generating recommendations...")
    recommendations = generate_recommendations(final_candidates, user_query)
    
    return recommendations