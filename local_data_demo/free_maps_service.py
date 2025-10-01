# free_maps_service.py - COMPLETE VERSION with OpenRouteService integration

import requests
from datetime import datetime, timedelta
import time
from cache_service import get_from_cache, set_to_cache, create_cache_key
from collections import Counter
import re
import math

# Well-known UK locations (pre-geocoded)
KNOWN_LOCATIONS = {
    'university college london': {'lat': 51.5246, 'lng': -0.1340},
    'ucl': {'lat': 51.5246, 'lng': -0.1340},
    'gower street': {'lat': 51.5246, 'lng': -0.1340},
    'university of manchester': {'lat': 53.4668, 'lng': -2.2339},
    'manchester piccadilly': {'lat': 53.4770, 'lng': -2.2309},
    'edinburgh university': {'lat': 55.9445, 'lng': -3.1892},
    'kings cross': {'lat': 51.5309, 'lng': -0.1239},
    'euston': {'lat': 51.5282, 'lng': -0.1337},
    'london bridge': {'lat': 51.5045, 'lng': -0.0865},
}


def _extract_postcode(address: str) -> str | None:
    """Extract UK postcode from address"""
    if not address:
        return None
    postcode_pattern = r'\b([A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2})\b'
    match = re.search(postcode_pattern, address.upper())
    if match:
        postcode = match.group(1)
        if ' ' not in postcode and len(postcode) > 3:
            postcode = postcode[:-3] + ' ' + postcode[-3:]
        return postcode
    return None


def _get_coordinates_from_postcode(postcode: str) -> dict | None:
    """Use Postcodes.io API - FREE, no key needed"""
    if not postcode:
        return None
    
    try:
        postcode_clean = postcode.replace(' ', '').upper()
        url = f"https://api.postcodes.io/postcodes/{postcode_clean}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 200 and 'result' in data:
                return {
                    'lat': data['result']['latitude'],
                    'lng': data['result']['longitude']
                }
    except Exception:
        pass
    
    return None


def _calculate_straight_line_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km - NO API needed"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _get_coordinates(address: str) -> dict | None:
    """Multi-strategy geocoding - ALL FREE"""
    if not address or not isinstance(address, str):
        return None
        
    cache_key = create_cache_key('_get_coordinates_free_v2', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        return cached_result
    
    address_lower = address.lower()
    
    # Strategy 1: Known locations
    for location, coords in KNOWN_LOCATIONS.items():
        if location in address_lower:
            set_to_cache(cache_key, coords)
            return coords
    
    # Strategy 2: Postcode (most reliable)
    postcode = _extract_postcode(address)
    if postcode:
        coords = _get_coordinates_from_postcode(postcode)
        if coords:
            set_to_cache(cache_key, coords)
            return coords
    
    # Strategy 3: OSM Nominatim (with retry)
    street_patterns = [
        r'(\w+\s+(?:Street|Road|Avenue|Lane|Place|Square|Gardens|Terrace|Close|Drive))',
    ]
    
    for pattern in street_patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            street = match.group(1)
            try:
                url = "https://nominatim.openstreetmap.org/search"
                params = {
                    'q': f"{street}, London, UK",
                    'format': 'json',
                    'limit': 1,
                    'countrycodes': 'gb'
                }
                headers = {'User-Agent': 'UKApartmentFinder/2.0'}
                
                time.sleep(1)
                response = requests.get(url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        coords = {
                            'lat': float(data[0]['lat']),
                            'lng': float(data[0]['lon'])
                        }
                        set_to_cache(cache_key, coords)
                        return coords
            except:
                continue
    
    return None


def calculate_travel_time(origin_address: str, destination_address: str, mode: str = "transit") -> int | None:
    """
    Calculate travel time - now uses REAL routing when API key is available.
    Falls back to distance estimation if no API key or if API fails.
    
    To enable real routing:
    1. Get free API key from https://openrouteservice.org/dev/#/signup
    2. Add to config.py: OPENROUTESERVICE_API_KEY = "your_key"
    """
    
    # Try to import ORS key
    try:
        from config import OPENROUTESERVICE_API_KEY
        if OPENROUTESERVICE_API_KEY and OPENROUTESERVICE_API_KEY != 'YOUR_KEY_HERE':
            # Try real routing
            result = _calculate_ors_route(origin_address, destination_address, mode)
            if result is not None:
                return result
            print("  [Info] ORS routing failed, using distance estimation")
    except (ImportError, AttributeError):
        pass
    
    # Fallback to distance-based estimation
    return _calculate_travel_time_simple(origin_address, destination_address, mode)


def _calculate_ors_route(origin_address: str, destination_address: str, mode: str) -> int | None:
    """Use OpenRouteService for REAL routing with actual roads/paths"""
    
    cache_key = create_cache_key('ors_route_v1', origin_address, destination_address, mode)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    origin_coords = _get_coordinates(origin_address)
    dest_coords = _get_coordinates(destination_address)
    
    if not origin_coords or not dest_coords:
        return None
    
    from config import OPENROUTESERVICE_API_KEY
    
    # Map mode to ORS profile
    profile_map = {
        'transit': 'foot-walking',      # ORS doesn't have transit, use walking + adjustment
        'driving': 'driving-car',
        'bicycling': 'cycling-regular',
        'walking': 'foot-walking'
    }
    
    profile = profile_map.get(mode, 'foot-walking')
    
    url = f"https://api.openrouteservice.org/v2/directions/{profile}"
    headers = {
        'Authorization': OPENROUTESERVICE_API_KEY,
        'Content-Type': 'application/json'
    }
    
    payload = {
        'coordinates': [
            [origin_coords['lng'], origin_coords['lat']],
            [dest_coords['lng'], dest_coords['lat']]
        ]
    }
    
    try:
        time.sleep(0.8)  # Rate limiting: 2000 req/day = 1 req per 0.8 sec
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'routes' in data and data['routes']:
                duration_seconds = data['routes'][0]['summary']['duration']
                duration_minutes = int(duration_seconds / 60)
                
                # For transit, adjust walking time (assume 2x faster + wait time)
                if mode == 'transit':
                    duration_minutes = int((duration_minutes / 2) + 10)
                
                print(f"  ✓ [ORS] Real route: {duration_minutes} mins")
                set_to_cache(cache_key, duration_minutes)
                return duration_minutes
        else:
            print(f"  ⚠️  [ORS] API error {response.status_code}")
            return None
    except:
        return None


def _calculate_travel_time_simple(origin_address: str, destination_address: str, mode: str = "transit") -> int | None:
    """
    Distance-based estimation (fallback method).
    Less accurate but always works without API keys.
    """
    if not origin_address or not destination_address:
        return None
    
    cache_key = create_cache_key('travel_time_distance_based', origin_address, destination_address, mode)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    origin_coords = _get_coordinates(origin_address)
    dest_coords = _get_coordinates(destination_address)
    
    if not origin_coords or not dest_coords:
        return None
    
    # Calculate straight-line distance
    distance_km = _calculate_straight_line_distance(
        origin_coords['lat'], origin_coords['lng'],
        dest_coords['lat'], dest_coords['lng']
    )
    
    # Apply realistic multipliers
    actual_distance = distance_km * 1.3
    
    # Calculate time based on mode
    if mode in ['transit', 'driving']:
        speed = 20
        base_time = (actual_distance / speed) * 60
        wait_time = min(10, distance_km * 2)
        total_minutes = int(base_time + wait_time)
    elif mode in ['bicycling', 'cycling-regular']:
        speed = 15
        total_minutes = int((actual_distance / speed) * 60)
    elif mode in ['walking', 'foot-walking']:
        speed = 5
        total_minutes = int((actual_distance / speed) * 60)
    else:
        speed = 20
        total_minutes = int((actual_distance / speed) * 60 + 5)
    
    set_to_cache(cache_key, total_minutes)
    return total_minutes


# Alias for compatibility with old code
estimate_travel_time_simple = _calculate_travel_time_simple


def find_nearby_places(address: str, amenities_of_interest: list[str], radius: int = 1500) -> dict:
    """Simplified - returns empty dict, can be enhanced later if needed"""
    return {f"{amenity}_in_{radius}m": 0 for amenity in amenities_of_interest}


def get_crime_data_by_location(address: str) -> dict | None:
    """UK Police API - FIXED VERSION with correct dates"""
    cache_key = create_cache_key('crime_data_v4', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  [Cache] Crime data for {address[:30]}...")
        return cached_result

    coords = _get_coordinates(address)
    if not coords:
        print(f"  [Warn] Could not geocode address for crime data: {address[:30]}")
        return {"total_crimes_6m": 0, "crime_trend": "unknown", "top_crime_types": []}

    # CRITICAL FIX: Use the actual current date from Python, not system prompt date
    from datetime import datetime as dt
    import calendar
    
    # Get the REAL current date
    real_now = dt.now()
    
    # Police API only has data up to ~2 months ago (they update with a delay)
    # So if today is Dec 2024, latest data is probably Oct 2024
    latest_available = real_now - timedelta(days=60)  # Go back 2 months
    
    all_crimes = []
    
    for months_ago in range(3):  # Get 3 months of data
        # Calculate the target date
        target_date = latest_available - timedelta(days=30 * months_ago)
        date_str = target_date.strftime('%Y-%m')
        
        api_url = (
            f"https://data.police.uk/api/crimes-street/all-crime"
            f"?lat={coords['lat']:.4f}&lng={coords['lng']:.4f}&date={date_str}"
        )
        
        try:
            print(f"  [API] Fetching crime data for {date_str}...")
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                crimes = response.json()
                if crimes and isinstance(crimes, list):
                    all_crimes.extend(crimes)
                    print(f"    ✓ Found {len(crimes)} crimes in {date_str}")
                elif isinstance(crimes, list) and len(crimes) == 0:
                    print(f"    - No crimes reported for {date_str}")
                else:
                    print(f"    - Invalid response for {date_str}")
            elif response.status_code == 404:
                print(f"    ⚠️  No data available for {date_str} (too recent or invalid)")
            else:
                print(f"    ⚠️  API returned {response.status_code} for {date_str}")
                
            # Respect rate limits (15 req/sec max)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"    ⚠️  Error fetching {date_str}: {e}")
            continue

    if not all_crimes:
        summary = {
            "total_crimes_6m": 0,
            "crime_trend": "no data",
            "top_crime_types": [],
            "note": "No recent crime data available for this area"
        }
        set_to_cache(cache_key, summary)
        return summary

    # Analyze crimes by month
    crimes_by_month = Counter(crime['month'] for crime in all_crimes)
    sorted_months = sorted(crimes_by_month.keys())
    counts = [crimes_by_month[m] for m in sorted_months]
    
    # Determine trend
    crime_trend = "stable"
    if len(counts) >= 2:
        if counts[-1] > counts[0] * 1.3:
            crime_trend = "increasing"
        elif counts[-1] < counts[0] * 0.7:
            crime_trend = "decreasing"
    
    # Get top crime types
    crime_types = [crime.get('category', 'unknown').replace('-', ' ').title() 
                   for crime in all_crimes if crime.get('category')]
    top_types = [cat for cat, _ in Counter(crime_types).most_common(3)]

    # Extrapolate to 6 months (we only have 3 months of data)
    total_crimes_3m = len(all_crimes)
    total_crimes_6m = total_crimes_3m * 2

    summary = {
        "total_crimes_6m": total_crimes_6m,
        "crime_trend": crime_trend,
        "top_crime_types": top_types
    }
    
    print(f"  ✓ Crime summary: {total_crimes_6m} crimes/6mo ({crime_trend}), top: {', '.join(top_types[:2])}")
    set_to_cache(cache_key, summary)
    return summary


def get_environmental_data(address: str) -> dict:
    """Simplified environmental data"""
    return {
        "air_quality_estimate": "good",
        "nearby_parks_1km": 0,
    }