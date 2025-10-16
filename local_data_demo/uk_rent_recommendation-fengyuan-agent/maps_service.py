# maps_service.py

import requests
import googlemaps
from config import GOOGLE_MAPS_API_KEY
from datetime import datetime
import pandas as pd
from cache_service import get_from_cache, set_to_cache, create_cache_key
from collections import Counter
import asyncio

# Initialize Google Maps Client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

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
        
        location = geocode_result[0]['geometry']['location'] # lat and lng
        set_to_cache(cache_key, location)
        return location
    except Exception as e:
        print(f"An error occurred during geocoding: {e}")
        return None


def calculate_travel_time(origin_address: str, destination_address: str, mode: str = "transit") -> int | None:
    """
    MODIFIED: Now supports multiple travel modes ('transit', 'bicycling', 'driving')
    and has more robust error handling.
    """
    if not origin_address or not destination_address:
        return None
        
    cache_key = create_cache_key('calculate_travel_time', origin_address, destination_address, mode)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        print(f"  -> [Cache HIT] Travel time for: {origin_address} ({mode})")
        return cached_result

    print(f"  -> [API Call] Getting travel time for: {origin_address} ({mode})")
    try:
        now = datetime.now()
        # For transit, we still want to query for a weekday morning commute
        if mode == "transit":
            departure_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            departure_time = now

        directions_result = gmaps.directions(
            origin_address, destination_address,
            mode=mode, departure_time=departure_time
        )
        
        if directions_result and 'legs' in directions_result[0]:
            duration_seconds = directions_result[0]['legs'][0]['duration']['value']
            minutes = round(duration_seconds / 60)
            set_to_cache(cache_key, minutes)
            return minutes
        return None
    except Exception as e:
        print(f"An error occurred with Google Maps API ({mode}): {e}")
        return None

def find_nearby_places(address: str, amenities_of_interest: list[str], radius: int = 1500) -> dict:
    """
    MODIFIED: This function is now much more flexible.
    Instead of fixed categories, it takes a list of amenities the user is interested in
    (extracted by Gemini) and finds counts for each within a specified radius (default 1.5km).
    """
    cache_key = create_cache_key('find_nearby_places', address, tuple(sorted(amenities_of_interest)), radius)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Nearby places for: {address}")
        return cached_result

    print(f"  -> [API Call] Getting nearby places for: {address}")
    
    location = _get_coordinates(address)
    if not location:
        return {}

    # Dynamically build the summary dict
    poi_summary = {f"{poi}_in_{radius}m": 0 for poi in amenities_of_interest}
    
    async def fetch_place(poi_type):
        try:
            # Note: gmaps library is not async, so we run it in an executor
            loop = asyncio.get_running_loop()
            places_result = await loop.run_in_executor(
                None, 
                lambda: gmaps.places_nearby(location=location, radius=radius, type=poi_type)
            )
            key = f"{poi_type}_in_{radius}m"
            poi_summary[key] = len(places_result.get('results', []))
        except Exception as e:
            print(f"An error occurred with Google Places API for type '{poi_type}': {e}")

    # Asynchronously fetch all amenity types
    # This is a good pattern but requires the calling function to be async.
    # For simplicity in this refactor, we'll keep it sequential, but async is the next step.
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
    """
    MODIFIED: This function is now much more insightful.
    1.  It fetches data for the last 6 months to analyze trends.
    2.  It determines if the crime rate is 'increasing', 'decreasing', or 'stable'.
    """
    cache_key = create_cache_key('get_crime_data_by_location', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Crime data for: {address}")
        return cached_result

    print(f"  -> [API Call] Getting official crime data for: {address}")
    location = _get_coordinates(address)
    if not location:
        return {"error": "Could not geocode address."}

    # Fetch data for the last 6 months for trend analysis
    # Police API data is often delayed by ~2 months
    base_date = datetime.now().replace(day=1) - pd.DateOffset(months=2)
    dates_to_fetch = [(base_date - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(6)]
    
    all_crimes = []
    for date_str in dates_to_fetch:
        api_url = f"https://data.police.uk/api/crimes-at-location?date={date_str}&lat={location['lat']}&lng={location['lng']}"
        try:
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            crimes = response.json()
            if crimes:
                all_crimes.extend(crimes)
        except requests.exceptions.RequestException:
            # It's common for some months to have no data or API errors, so we continue
            print(f" - Could not fetch crime data for {date_str}, skipping.")
            continue
        except json.JSONDecodeError:
            print(f" - Invalid JSON for {date_str}, skipping.")
            continue

    if not all_crimes:
        summary = {"total_crimes_6m": 0, "crime_trend": "stable", "category_breakdown": "No crime data reported for this location in the last 6 months."}
        set_to_cache(cache_key, summary)
        return summary

    # Trend Analysis
    crimes_by_month = Counter(crime['month'] for crime in all_crimes)
    # Sort months chronologically
    sorted_months = sorted(crimes_by_month.keys())
    counts = [crimes_by_month[m] for m in sorted_months]
    
    crime_trend = "stable"
    if len(counts) > 3: # Need at least 4 data points for a simple trend
        # Compare first half average vs second half average
        first_half_avg = sum(counts[:len(counts)//2]) / (len(counts)//2)
        second_half_avg = sum(counts[len(counts)//2:]) / (len(counts)//2)
        if second_half_avg > first_half_avg * 1.2: # 20% increase
            crime_trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8: # 20% decrease
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
    """
    NEW FUNCTION: Fetches environmental data for a given address.
    This is a placeholder for a real API, using nearby parks as a proxy for green space.
    A real implementation would call an Air Quality API.
    """
    cache_key = create_cache_key('get_environmental_data', address)
    cached_result = get_from_cache(cache_key)
    if cached_result:
        print(f"  -> [Cache HIT] Environmental data for: {address}")
        return cached_result
    
    print(f"  -> [API Call] Getting environmental data for: {address}")
    
    location = _get_coordinates(address)
    if not location:
        return {}

    # Proxy for Green Space: Count parks within 1km
    parks_in_1km = 0
    try:
        places_result = gmaps.places_nearby(location=location, radius=1000, type='park')
        parks_in_1km = len(places_result.get('results', []))
    except Exception as e:
        print(f"Could not fetch park data: {e}")

    # Placeholder for Air Quality
    # In a real app, you would call an API like OpenAQ here using lat/lng
    # For now, we'll simulate it based on park count.
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