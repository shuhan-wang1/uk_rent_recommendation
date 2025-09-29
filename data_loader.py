# data_loader.py

import pandas as pd
import re
from scrapper.rightmove_scraper import find_properties as find_on_rightmove
from scrapper.scrape_zoopla_listings import find_properties_zoopla as find_on_zoopla

def parse_price(price_str: str) -> float | None:
    """将'£1,200 pcm'这样的价格字符串转换为浮点数。"""
    if not isinstance(price_str, str): return None
    if 'poa' in price_str.lower(): return None
    try:
        price = re.sub(r'[£,pcm]', '', price_str).strip()
        return float(price)
    except (ValueError, TypeError):
        return None

def extract_postcode(address: str) -> str | None:
    """从地址字符串中提取并标准化英国邮编。"""
    if not isinstance(address, str): return None
    postcode_regex = r'([A-Z]{1,2}[0-9R][0-9A-Z]?\s?[0-9][A-Z]{2})'
    match = re.search(postcode_regex, address, re.IGNORECASE)
    if match:
        postcode = match.group(1).upper().replace(" ", "")
        if len(postcode) > 3:
            return f"{postcode[:-3]} {postcode[-3:]}"
        return postcode
    return None

def get_live_properties(location_id: str, radius: float, min_price: int, max_price: int) -> list[dict]:
    """
    实时从Rightmove和Zoopla获取房源，然后清洗数据。
    注意: Zoopla的location_slug需要根据location_id进行转换，这里为了简化演示使用硬编码。
    """
    print("\n--- Starting Live Property Scraping ---")
    
    # 这里的 location_slug 需要一个从 id 到 slug 的转换逻辑
    # 为了演示，我们硬编码一个与UCL区域相关的slug
    location_map = {
        "REGION^87490": "london" # London
        # 实际应用中需要一个查找服务
    }
    zoopla_slug = location_map.get(location_id, "london")

    print(f"-> Searching on Rightmove (ID: {location_id})...")
    rm_properties = find_on_rightmove(
        location_identifier=location_id, radius=radius,
        min_price=min_price, max_price=max_price
    )
    for prop in rm_properties: prop['Platform'] = 'Rightmove'
    print(f"   -> Found {len(rm_properties)} properties on Rightmove.")

    # Zoopla 抓取比较慢，可以根据需要启用/禁用
    # print(f"-> Searching on Zoopla (Slug: {zoopla_slug})...")
    # zp_properties = find_on_zoopla(
    #     location_slug=zoopla_slug, radius=radius,
    #     min_price=min_price, max_price=max_price
    # )
    # for prop in zp_properties: prop['Platform'] = 'Zoopla'
    # print(f"   -> Found {len(zp_properties)} properties on Zoopla.")
    
    # all_properties = rm_properties + zp_properties
    all_properties = rm_properties # 本次演示仅使用 Rightmove 以提高速度
    print(f"--- Live Scraping Finished. Total Found: {len(all_properties)} ---")

    if not all_properties:
        return []

    # 数据清洗
    for prop in all_properties:
        prop['parsed_price'] = parse_price(prop.get('Price', ''))
        prop['postcode'] = extract_postcode(prop.get('Address', ''))
        
    return [p for p in all_properties if p['parsed_price'] is not None]

def filter_by_budget(properties: list[dict], max_price: float) -> list[dict]:
    """按最高价格筛选房源列表。"""
    return [p for p in properties if p.get('parsed_price', float('inf')) <= max_price]