# maps_service.py

import googlemaps
from config import GOOGLE_MAPS_API_KEY
from datetime import datetime
import pandas as pd
from cache_service import get_from_cache, set_to_cache, create_cache_key

# 初始化 Google Maps 客户端
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def calculate_travel_time(origin_address: str, destination_address: str) -> int | None:
    """
    计算公共交通出行时间。
    返回分钟数，并使用缓存。
    """
    cache_key = create_cache_key('calculate_travel_time', origin_address, destination_address)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        print(f"  -> [Cache HIT] Travel time for: {origin_address}")
        return cached_result

    print(f"  -> [API Call] Getting travel time for: {origin_address}")
    try:
        now = datetime.now()
        today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
        days_ahead = (0 - today_9am.weekday() + 7) % 7
        if days_ahead == 0 and now.hour >= 9:
            days_ahead = 7
        monday_9am = today_9am + pd.to_timedelta(days_ahead, unit='d')

        directions_result = gmaps.directions(
            origin_address,
            destination_address,
            mode="transit",
            departure_time=monday_9am
        )
        
        if directions_result and 'legs' in directions_result[0]:
            duration_seconds = directions_result[0]['legs'][0]['duration']['value']
            minutes = round(duration_seconds / 60)
            set_to_cache(cache_key, minutes)
            return minutes
        return None
    except Exception as e:
        print(f"An error occurred with Google Maps API: {e}")
        return None

def find_nearby_places(address: str, radius: int = 1000) -> dict:
    """
    查找指定地址1公里半径内的关键设施（超市、公园、地铁站）。
    使用缓存。
    """
    cache_key = create_cache_key('find_nearby_places', address, radius)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        print(f"  -> [Cache HIT] Nearby places for: {address}")
        return cached_result

    print(f"  -> [API Call] Getting nearby places for: {address}")
    
    poi_summary = {
        'supermarkets_in_1km': 0,
        'parks_in_1km': 0,
        'subway_stations_in_1km': 0
    }
    
    try:
        geocode_result = gmaps.geocode(address)
        if not geocode_result:
            return poi_summary
        
        location = geocode_result[0]['geometry']['location']
        
        poi_types = {
            'supermarket': 'supermarkets_in_1km',
            'park': 'parks_in_1km',
            'subway_station': 'subway_stations_in_1km'
        }

        for place_type, key in poi_types.items():
            places_result = gmaps.places_nearby(
                location=location,
                radius=radius,
                type=place_type
            )
            poi_summary[key] = len(places_result.get('results', []))

        set_to_cache(cache_key, poi_summary)
        return poi_summary

    except Exception as e:
        print(f"An error occurred with Google Places API: {e}")
        return poi_summary