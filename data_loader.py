# data_loader.py

import pandas as pd
import re
from scrapper.rightmove_scraper import find_properties as find_on_rightmove
# REMOVED: Zoopla import is gone as requested.

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
    # This regex is quite good, but let's make it a bit more robust for UK postcodes
    postcode_regex = r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})'
    match = re.search(postcode_regex, address, re.IGNORECASE)
    if match:
        # Standardize postcode format (e.g., N19AA -> N1 9AA)
        postcode = match.group(1).upper().replace(" ", "")
        if len(postcode) > 3:
            return f"{postcode[:-3]} {postcode[-3:]}"
        return postcode
    return None

def get_live_properties(location_id: str, radius: float, min_price: int, max_price: int, limit: int | None = None) -> list[dict]:
    """
    Updated to preserve image data from scrapers
    """
    print("\n--- Starting Live Property Scraping ---")
    
    if limit:
        print(f"/!\\ Scraper limit set to {limit} properties. /!\\")

    print(f"-> Searching on Rightmove (ID: {location_id})...")
    rm_properties = find_on_rightmove(
        location_identifier=location_id, radius=radius,
        min_price=min_price, max_price=max_price,
        limit=limit
    )
    for prop in rm_properties: 
        prop['Platform'] = 'Rightmove'
        # Ensure Images key exists
        if 'Images' not in prop:
            prop['Images'] = []
    print(f"   -> Found {len(rm_properties)} properties on Rightmove.")

    all_properties = rm_properties
    print(f"--- Live Scraping Finished. Total Found: {len(all_properties)} ---")

    if not all_properties:
        return []

    # Process properties
    processed_properties = []
    for prop in all_properties:
        prop['parsed_price'] = parse_price(prop.get('Price'))
        prop['postcode'] = extract_postcode(prop.get('Address'))
        if prop['parsed_price'] is not None:
             processed_properties.append(prop)
        
    return processed_properties

def filter_by_budget(properties: list[dict], max_price: float) -> list[dict]:
    return [p for p in properties if p.get('parsed_price', float('inf')) <= max_price]