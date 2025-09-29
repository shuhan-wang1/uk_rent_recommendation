# enrichment.py

import asyncio
from maps_service import calculate_travel_time, find_nearby_places
from web_search import search_crime_data, search_cost_of_living

async def enrich_property_data(property_dict: dict, destination: str) -> dict:
    """
    异步地用出行时间、犯罪、生活成本和周边设施数据丰富单个房源字典。
    """
    enriched_prop = property_dict.copy()
    address = enriched_prop.get('Address')
    postcode = enriched_prop.get('postcode')
    
    # 使用 run_in_executor 在 asyncio 事件循环中运行同步的 SDK 调用
    loop = asyncio.get_running_loop()

    # 1. 添加出行时间 (已在 recommender 中预先计算)
    # 2. 添加犯罪和生活成本数据
    print(f"  -> Enriching web data for: {postcode or address}")
    crime_task = loop.run_in_executor(None, search_crime_data, postcode)
    cost_task = loop.run_in_executor(None, search_cost_of_living, postcode)
    
    # 3. 添加周边设施数据
    places_task = loop.run_in_executor(None, find_nearby_places, address)

    # 等待所有 API 调用完成
    crime_info, cost_info, places_info = await asyncio.gather(
        crime_task, cost_task, places_task
    )
    
    enriched_prop['crime_info_snippet'] = crime_info
    enriched_prop['cost_of_living_snippet'] = cost_info
    enriched_prop.update(places_info)
    
    return enriched_prop