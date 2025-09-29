# data_loader.py

import pandas as pd
import re
from scrapper.rightmove_scraper import find_properties as find_on_rightmove
# from scrapper.scrape_zoopla_listings import find_properties_zoopla as find_on_zoopla

def parse_price(price_str: str) -> float | None:
    if not isinstance(price_str, str): return None
    if 'poa' in price_str.lower(): return None
    try:
        price = re.sub(r'[£,pcm]', '', price_str).strip()
        return float(price)
    except (ValueError, TypeError):
        return None

def extract_postcode(address: str) -> str | None:
    if not isinstance(address, str): return None
    postcode_regex = r'([A-Z]{1,2}[0-9R][0-9A-Z]?\s?[0-9][A-Z]{2})'
    match = re.search(postcode_regex, address, re.IGNORECASE)
    if match:
        postcode = match.group(1).upper().replace(" ", "")
        if len(postcode) > 3:
            return f"{postcode[:-3]} {postcode[-3:]}"
        return postcode
    return None

# 在函数签名中添加 limit 参数
def get_live_properties(location_id: str, radius: float, min_price: int, max_price: int, limit: int | None = None) -> list[dict]:
    print("\n--- Starting Live Property Scraping ---")
    
    if limit:
        print(f"/!\\ Scraper limit set to {limit} properties. /!\\")

    print(f"-> Searching on Rightmove (ID: {location_id})...")
    rm_properties = find_on_rightmove(
        location_identifier=location_id, radius=radius,
        min_price=min_price, max_price=max_price,
        limit=limit # 将 limit 参数传递下去
    )
    for prop in rm_properties: prop['Platform'] = 'Rightmove'
    print(f"   -> Found {len(rm_properties)} properties on Rightmove.")

    all_properties = rm_properties
    print(f"--- Live Scraping Finished. Total Found: {len(all_properties)} ---")

    if not all_properties:
        return []

    for prop in all_properties:
        prop['parsed_price'] = parse_price(prop.get('Price', ''))
        prop['postcode'] = extract_postcode(prop.get('Address', ''))
        
    return [p for p in all_properties if p['parsed_price'] is not None]

def filter_by_budget(properties: list[dict], max_price: float) -> list[dict]:
    return [p for p in properties if p.get('parsed_price', float('inf')) <= max_price]