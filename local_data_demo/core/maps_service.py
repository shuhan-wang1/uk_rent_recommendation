# maps_service.py - FIXED to handle landmark names properly

import requests
import googlemaps
from datetime import datetime
import pandas as pd
from collections import Counter
import asyncio
import math
from config import GOOGLE_MAPS_API_KEY, OPENROUTESERVICE_API_KEY, USE_TRAVEL_SERVICE
from .cache_service import get_from_cache, set_to_cache, create_cache_key

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Map common landmarks to specific addresses that Google Maps API can route to
LANDMARK_TO_ADDRESS = {
    'university college london': 'Gower Street, London WC1E 6BT',
    'ucl': 'Gower Street, London WC1E 6BT',
    'kings cross': 'Kings Cross Station, London N1 9AP',
    'kings cross station': 'Kings Cross Station, London N1 9AP',
    'euston': 'Euston Station, London NW1 2RT',
    'euston station': 'Euston Station, London NW1 2RT',
    'london bridge': 'London Bridge Station, London SE1 9SP',
}

def _normalize_address_for_routing(address: str) -> str:
    """Convert landmark names to specific addresses for routing"""
    if not address:
        return address
    
    address_lower = address.lower().strip()
    
    # Check if it's a known landmark
    for landmark, specific_address in LANDMARK_TO_ADDRESS.items():
        if landmark in address_lower:
            print(f"  -> Converted '{address}' to '{specific_address}'")
            return specific_address
    
    return address

def _get_coordinates(address: str) -> dict | None:
    """Internal function: gets coordinates for an address and caches the result."""
    if not address or not isinstance(address, str):
        return None
    cache_key = create_cache_key('_get_coordinates', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        return cached_result
    
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result:
            return None
        
        location = geocode_result[0]['geometry']['location']
        set_to_cache(cache_key, location)
        return location
    except Exception as e:
        print(f"An error occurred during geocoding: {e}")
        return None


def calculate_travel_time(origin_address: str, destination_address: str, mode: str = "transit") -> int | None:
    """
    统一的出行时间计算接口。
    根据 config.py 的设置自动选择使用 Google Maps 或 OpenRouteService。
    """
    if not origin_address or not destination_address:
        return None
    
    # Normalize addresses for routing
    origin_normalized = _normalize_address_for_routing(origin_address)
    destination_normalized = _normalize_address_for_routing(destination_address)
    
    cache_key = create_cache_key('calculate_travel_time', origin_normalized, destination_normalized, mode)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        print(f"  -> [Cache HIT] Travel time for: {origin_address} ({mode})")
        return cached_result

    print(f"  -> [Google Maps API] Getting travel time: {origin_address} -> {destination_normalized} ({mode})")
    
    try:
        now = datetime.now()
        # For transit, query for weekday morning commute
        if mode == "transit":
            departure_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            departure_time = now

        directions_result = gmaps.directions(
            origin_normalized,           # Use normalized address
            destination_normalized,      # Use normalized address
            mode=mode, 
            departure_time=departure_time
        )
        
        if directions_result and 'legs' in directions_result[0]:
            duration_seconds = directions_result[0]['legs'][0]['duration']['value']
            minutes = round(duration_seconds / 60)
            print(f"  [OK] [Google Maps] Route found: {minutes} mins")
            set_to_cache(cache_key, minutes)
            return minutes
        else:
            print(f"  [WARN]  [Google Maps] No route found")
            return None
            
    except Exception as e:
        print(f"  ❌ [Google Maps API] Error: {e}")
        return None

def find_nearby_places(address: str, amenities_of_interest: list[str], radius: int = 1500) -> dict:
    """Find nearby places using Google Places API"""
    cache_key = create_cache_key('find_nearby_places', address, tuple(sorted(amenities_of_interest)), radius)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Nearby places for: {address}")
        return cached_result

    print(f"  -> [API Call] Getting nearby places for: {address}")
    
    location = _get_coordinates(address)
    if not location:
        return {}

    poi_summary = {f"{poi}_in_{radius}m": 0 for poi in amenities_of_interest}
    
    for place_type in amenities_of_interest:
        try:
            places_result = gmaps.places_nearby(location=location, radius=radius, type=place_type)
            key = f"{place_type}_in_{radius}m"
            poi_summary[key] = len(places_result.get('results', []))
        except Exception as e:
             print(f"An error occurred with Google Places API for type '{place_type}': {e}")

    set_to_cache(cache_key, poi_summary)
    return poi_summary


def get_crime_data_by_location(address: str) -> dict | None:
    """Get crime data from UK Police API with trend analysis"""
    cache_key = create_cache_key('get_crime_data_by_location', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Crime data for: {address}")
        return cached_result

    print(f"  -> [API Call] Getting official crime data for: {address}")
    location = _get_coordinates(address)
    
    if not location:
        print(f"     ❌ Could not geocode address: {address}")
        return {"error": "Could not geocode address.", "total_crimes_6m": "Unknown"}
    
    print(f"     [OK] Coordinates: {location['lat']}, {location['lng']}")

    base_date = datetime.now().replace(day=1) - pd.DateOffset(months=2)
    dates_to_fetch = [(base_date - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(6)]
    
    all_crimes = []
    for date_str in dates_to_fetch:
        api_url = f"https://data.police.uk/api/crimes-at-location?date={date_str}&lat={location['lat']}&lng={location['lng']}"
        try:
            print(f"     -> Fetching {date_str}...")
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            crimes = response.json()
            
            if crimes:
                print(f"       [OK] Found {len(crimes)} crimes in {date_str}")
                all_crimes.extend(crimes)
            else:
                print(f"       • No crimes in {date_str}")
        except requests.exceptions.Timeout:
            print(f"       [WARN]  Timeout for {date_str}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"       ❌ API error for {date_str}: {e}")
            continue

    if not all_crimes:
        print(f"     [WARN]  WARNING: No crime data found for any month!")
        summary = {
            "total_crimes_6m": "Unknown", 
            "crime_trend": "unknown", 
            "category_breakdown": "Crime data unavailable",
            "error": "No data returned from UK Police API"
        }
        set_to_cache(cache_key, summary)
        return summary

    print(f"     [OK] TOTAL: {len(all_crimes)} crimes across 6 months")
    
    crimes_by_month = Counter(crime['month'] for crime in all_crimes)
    sorted_months = sorted(crimes_by_month.keys())
    counts = [crimes_by_month[m] for m in sorted_months]
    
    crime_trend = "stable"
    if len(counts) > 3:
        first_half_avg = sum(counts[:len(counts)//2]) / (len(counts)//2)
        second_half_avg = sum(counts[len(counts)//2:]) / (len(counts)//2)
        if second_half_avg > first_half_avg * 1.2:
            crime_trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            crime_trend = "decreasing"

    category_counts = Counter(crime['category'].replace('-', ' ').title() for crime in all_crimes)
    
    summary = {
        "total_crimes_6m": len(all_crimes),
        "most_recent_month_count": counts[-1] if counts else 0,
        "crime_trend": crime_trend,
        "data_months": sorted_months,
        "category_breakdown": dict(category_counts.most_common(3))
    }
    set_to_cache(cache_key, summary)
    return summary


def get_environmental_data(address: str) -> dict:
    """Get environmental data (parks, air quality estimate)"""
    cache_key = create_cache_key('get_environmental_data', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Environmental data for: {address}")
        return cached_result
    
    print(f"  -> [API Call] Getting environmental data for: {address}")
    
    location = _get_coordinates(address)
    if not location:
        return {}

    parks_in_1km = 0
    try:
        places_result = gmaps.places_nearby(location=location, radius=1000, type='park')
        parks_in_1km = len(places_result.get('results', []))
    except Exception as e:
        print(f"Could not fetch park data: {e}")

    air_quality = "good"
    if parks_in_1km == 0:
        air_quality = "moderate"
    elif parks_in_1km >= 3:
        air_quality = "excellent"

    summary = {
        "air_quality_estimate": air_quality,
        "nearby_parks_1km": parks_in_1km,
    }
    set_to_cache(cache_key, summary)
    return summary


def estimate_travel_time_simple(origin_address: str, destination_address: str, mode: str = "transit") -> int | None:
    """
    Simple distance-based travel time estimation (no API calls).
    Used for quick filtering in the first stage.
    More accurate results use calculate_travel_time().
    """
    if not origin_address or not destination_address:
        return None
    
    cache_key = create_cache_key('estimate_travel_time_simple', origin_address, destination_address, mode)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Try to get coordinates
    origin_coords = _get_coordinates(origin_address)
    dest_coords = _get_coordinates(destination_address)
    
    if not origin_coords or not dest_coords:
        return None
    
    # Calculate straight-line distance using Haversine formula
    R = 6371  # Earth radius in kilometers
    
    lat1_rad = math.radians(origin_coords['lat'])
    lat2_rad = math.radians(dest_coords['lat'])
    dlat = math.radians(dest_coords['lat'] - origin_coords['lat'])
    dlng = math.radians(dest_coords['lng'] - origin_coords['lng'])
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    distance_km = R * c
    
    # Apply realistic multiplier (actual route is ~1.3x straight line)
    actual_distance = distance_km * 1.3
    
    # Calculate time based on mode
    if mode in ['transit', 'driving']:
        speed = 20  # km/h average
        base_time = (actual_distance / speed) * 60
        wait_time = min(10, distance_km * 2)
        total_minutes = int(base_time + wait_time)
    elif mode in ['bicycling', 'cycling-regular']:
        speed = 15  # km/h
        total_minutes = int((actual_distance / speed) * 60)
    elif mode in ['walking', 'foot-walking']:
        speed = 5  # km/h
        total_minutes = int((actual_distance / speed) * 60)
    else:
        speed = 20
        total_minutes = int((actual_distance / speed) * 60 + 5)
    
    set_to_cache(cache_key, total_minutes)
    return total_minutes


def get_nearby_supermarkets_detailed(address: str, radius: int = 2000, 
                                     chains: list[str] | None = None) -> list[dict]:
    """
    多源超市搜索 - 智能级联搜索策略
    
    搜索顺序：
    1. OSM品牌查询（brand=Lidl等）- 精准
    2. OSM通用超市查询（shop=supermarket等）- 通用
    3. 网页搜索回退 - 最后手段
    
    参数：
    - address: 搜索的地址
    - radius: 搜索半径（米）
    - chains: 目标超市品牌列表，如['Lidl', 'Aldi']，默认['Lidl', 'Aldi', 'Sainsbury', 'Tesco']
    
    返回：超市列表，按距离排序
    """
    if chains is None:
        chains = ['Lidl', 'Aldi', 'Sainsbury', 'Tesco']
    
    cache_key = create_cache_key('supermarkets_detailed_v2_multi', address, radius, tuple(chains))
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"    -> [缓存] 找到超市缓存: {address}")
        return cached_result
    
    print(f"    [SEARCH] [多源搜索] 搜索超市: {chains} near {address}")
    
    location = _get_coordinates(address)
    if not location:
        print(f"    -> [多源搜索] 无法地理编码: {address}")
        return []
    
    results = []
    
    # ===== 方法1：OSM品牌查询 =====
    print(f"      方法1: OSM品牌查询...")
    url = "https://overpass-api.de/api/interpreter"
    
    for chain in chains:
        query = f"""
        [out:json][timeout:10];
        (
          node["brand"="{chain}"]["shop"="supermarket"](around:{radius},{location['lat']},{location['lng']});
          node["brand"="{chain}"](around:{radius},{location['lat']},{location['lng']});
          way["brand"="{chain}"]["shop"="supermarket"](around:{radius},{location['lat']},{location['lng']});
          way["brand"="{chain}"](around:{radius},{location['lat']},{location['lng']});
        );
        out center;
        """
        
        try:
            import time as time_module
            time_module.sleep(0.5)
            response = requests.post(url, data={'data': query}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                brand_results = _parse_osm_elements(data.get('elements', []), location, chain)
                results.extend(brand_results)
                print(f"        [OK] {chain}: 找到 {len(brand_results)} 家")
        except Exception as e:
            print(f"        [WARN]  {chain} 搜索出错: {e}")
    
    # ===== 方法2：通用超市搜索 =====
    if len(results) < 3:
        print(f"      方法2: OSM通用超市搜索 (已找到 {len(results)} 家，需要补充)...")
        query = f"""
        [out:json][timeout:15];
        (
          node["shop"="supermarket"](around:{radius},{location['lat']},{location['lng']});
          way["shop"="supermarket"](around:{radius},{location['lat']},{location['lng']});
          node["shop"="convenience"](around:{radius},{location['lat']},{location['lng']});
          way["shop"="convenience"](around:{radius},{location['lat']},{location['lng']});
        );
        out center;
        """
        
        try:
            import time as time_module
            time_module.sleep(1)
            response = requests.post(url, data={'data': query}, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                generic_results = _parse_osm_elements(data.get('elements', []), location, 'generic')
                
                # 去重：只添加新的超市
                existing_names = {r.get('name', '').lower() for r in results}
                new_results = [r for r in generic_results if r.get('name', '').lower() not in existing_names]
                results.extend(new_results)
                print(f"        [OK] 通用搜索: 找到 {len(new_results)} 家新超市")
        except Exception as e:
            print(f"        [WARN]  通用搜索出错: {e}")
    
    # ===== 方法3：网页搜索回退 =====
    if not results:
        print(f"      方法3: 网页搜索回退...")
        try:
            from .web_search import get_search_snippets
            
            for chain in chains[:2]:  # 只搜索前两个品牌
                try:
                    query_text = f"{chain} supermarket near {address} London"
                    snippets = get_search_snippets(query_text, max_results=2)
                    
                    for snippet in snippets:
                        title = snippet.get('title', '')
                        if chain.lower() in title.lower():
                            web_result = {
                                'name': title,
                                'type': 'supermarket',
                                'address': snippet.get('snippet', 'Web result'),
                                'distance_m': None,
                                'source': 'web_search',
                                'url': snippet.get('link', '')
                            }
                            results.append(web_result)
                except Exception as e:
                    print(f"        [WARN]  {chain} 网页搜索出错: {e}")
        except Exception as e:
            print(f"        [WARN]  网页搜索模块不可用: {e}")
    
    # ===== 最终处理 =====
    # 去重、排序和限制数量
    results = _deduplicate_supermarkets(results)
    results.sort(key=lambda x: x.get('distance_m', 999999) if x.get('distance_m') else 999999)
    results = results[:10]  # 最多返回10个
    
    print(f"    [OK] [多源搜索] 总共找到 {len(results)} 家超市")
    set_to_cache(cache_key, results)
    return results


def _parse_osm_elements(elements: list, location: dict, source: str = 'osm') -> list[dict]:
    """
    解析OSM API返回的元素列表
    """
    supermarkets = []
    
    for element in elements:
        tags = element.get('tags', {})
        
        # 获取坐标
        if element['type'] == 'node':
            shop_lat = element['lat']
            shop_lng = element['lon']
        else:  # way (building)
            center = element.get('center', {})
            shop_lat = center.get('lat')
            shop_lng = center.get('lon')
        
        if not shop_lat or not shop_lng:
            continue
        
        # 计算距离（Haversine公式）
        lat1_rad = math.radians(location['lat'])
        lat2_rad = math.radians(shop_lat)
        dlat = math.radians(shop_lat - location['lat'])
        dlng = math.radians(shop_lng - location['lng'])
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance_m = int(6371000 * c)
        
        # 提取信息
        name = tags.get('name', 'Unnamed Shop')
        shop_type = tags.get('shop', 'supermarket')
        street = tags.get('addr:street', '')
        housenumber = tags.get('addr:housenumber', '')
        brand = tags.get('brand', '')
        
        supermarkets.append({
            'name': name,
            'type': shop_type,
            'address': f"{housenumber} {street}".strip() or "Address not available",
            'distance_m': distance_m,
            'lat': shop_lat,
            'lng': shop_lng,
            'brand': brand,
            'source': source
        })
    
    return supermarkets


def _deduplicate_supermarkets(results: list[dict]) -> list[dict]:
    """
    去重超市结果：按名称和距离
    优先级：osm_brand > osm_generic > web_search
    """
    seen_names = set()
    dedup_results = []
    
    # 优先级排序
    priority_map = {'osm': 0, 'generic': 1, 'web_search': 2}
    results_sorted = sorted(
        results,
        key=lambda x: (
            priority_map.get(x.get('source', 'web_search'), 999),
            x.get('distance_m', 999999) if x.get('distance_m') else 999999
        )
    )
    
    for result in results_sorted:
        name_lower = result.get('name', '').lower()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            dedup_results.append(result)
    
    return dedup_results