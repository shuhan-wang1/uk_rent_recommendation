# location_resolver.py

from cache_service import get_from_cache, set_to_cache, create_cache_key

# Comprehensive UK Location Mapping for Rightmove
# Format: 'search_term': ('LOCATION_ID', radius_in_miles)
# IMPORTANT: Radius must be one of: 0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0
# location_resolver.py - 最小可靠版本

UK_LOCATIONS = {
    # 只使用大区域，这些ID更稳定
    'manchester': ('REGION^904', 3.0),  # Greater Manchester - 这个是确定的
    'london': ('REGION^87490', 5.0),     # Greater London - 确定的
    'birmingham': ('REGION^376', 3.0),   # Birmingham - 确定的
    'edinburgh': ('REGION^552', 3.0),    # Edinburgh - 确定的
    'glasgow': ('REGION^617', 3.0),      # Glasgow - 确定的
    'bristol': ('REGION^398', 3.0),      # Bristol - 确定的
    'leeds': ('REGION^764', 3.0),        # Leeds - 确定的
    'liverpool': ('REGION^790', 3.0),    # Liverpool - 确定的
    'sheffield': ('REGION^1203', 3.0),   # Sheffield - 确定的
    'newcastle': ('REGION^920', 3.0),    # Newcastle - 确定的
    'nottingham': ('REGION^952', 3.0),   # Nottingham - 确定的
}

def find_location_match(location_name: str) -> tuple[str, float] | None:
    """
    Finds the best match for a location name in our comprehensive mapping.
    Returns (location_id, radius) or None.
    """
    location_lower = location_name.lower().strip()
    
    # Direct match
    if location_lower in UK_LOCATIONS:
        return UK_LOCATIONS[location_lower]
    
    # Partial match (for cases like "Manchester Piccadilly station" -> "manchester piccadilly")
    for key, value in UK_LOCATIONS.items():
        if key in location_lower or location_lower in key:
            return value
    
    return None


def validate_radius(radius: float) -> float:
    """
    Ensures the radius is one of Rightmove's accepted values.
    Valid values: 0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0
    """
    valid_radii = [0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0]
    
    # Find the closest valid radius
    closest = min(valid_radii, key=lambda x: abs(x - radius))
    
    if closest != radius:
        print(f"  [WARN] Adjusted radius from {radius} to {closest} (Rightmove requirement)")
    
    return closest


def get_best_location_id(suggested_locations: list[str], fallback_city: str = "London") -> tuple[str, float]:
    """
    Tries to find a Rightmove ID from a list of suggested locations.
    Returns (location_id, recommended_radius).
    """
    
    print(f"\n[LOCATION RESOLVER] Analyzing suggestions: {suggested_locations}")
    
    # Try each suggested location in order
    for location in suggested_locations:
        result = find_location_match(location)
        if result:
            location_id, radius = result
            radius = validate_radius(radius)  # Ensure it's a valid Rightmove radius
            print(f"  ✓ Matched '{location}' → {location_id} (radius: {radius} miles)")
            return (location_id, radius)
        else:
            print(f"  ✗ No match for '{location}'")
    
    # Fallback: try the city name itself
    print(f"\n[WARN] Could not match suggested locations. Trying city: '{fallback_city}'")
    fallback_result = find_location_match(fallback_city)
    
    if fallback_result:
        location_id, radius = fallback_result
        radius = validate_radius(radius)
        print(f"  ✓ Using city fallback: {location_id} (radius: {radius} miles)")
        return (location_id, radius)
    
    # Ultimate fallback: Greater London
    print(f"\n[ERROR] Could not resolve '{fallback_city}'. Defaulting to Greater London.")
    return ("REGION^87490", 5.0)