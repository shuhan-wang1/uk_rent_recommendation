# enrichment.py

import asyncio
# 导入新的犯罪数据函数
from maps_service import calculate_travel_time, find_nearby_places, get_crime_data_by_location
# 移除了 search_crime_data, 但保留 search_cost_of_living
from web_search import search_cost_of_living

async def enrich_property_data(property_dict: dict, destination: str) -> dict:
    """
    异步地用出行时间、犯罪、生活成本和周边设施数据丰富单个房源字典。
    """
    enriched_prop = property_dict.copy()
    address = enriched_prop.get('Address')
    postcode = enriched_prop.get('postcode')
    
    loop = asyncio.get_running_loop()

    # 1. 生活成本数据 (Web Search)
    print(f"  -> Enriching web & API data for: {address}")
    cost_task = loop.run_in_executor(None, search_cost_of_living, postcode or address)
    
    # 2. 周边设施数据 (Google Places API)
    places_task = loop.run_in_executor(None, find_nearby_places, address)
    
    # 3. 官方犯罪数据 (Police API)
    crime_task = loop.run_in_executor(None, get_crime_data_by_location, address)

    # 等待所有 API 调用完成
    cost_info, places_info, crime_info = await asyncio.gather(
        cost_task, places_task, crime_task
    )
    
    # 移除了不稳定的 crime_info_snippet
    enriched_prop['cost_of_living_snippet'] = cost_info
    # 新增了结构化的官方犯罪数据
    enriched_prop['crime_data_summary'] = crime_info
    enriched_prop.update(places_info)
    
    return enriched_prop