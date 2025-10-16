# location_resolver.py - Updated with working IDs

from cache_service import get_from_cache, set_to_cache, create_cache_key

UK_LOCATIONS = {
    # London - Use REGION IDs instead of STATION IDs (more stable) 是Rightmove网站的内部区域ID
    'london': ('REGION^87490', 5.0),
    'greater london': ('REGION^87490', 5.0),

    # Other major cities
    'edinburgh': ('REGION^1101', 5.0),
    'birmingham': ('REGION^950', 5.0),
    'bristol': ('REGION^1183', 5.0),
    'leeds': ('REGION^1194', 5.0),
    'glasgow': ('REGION^1112', 5.0),
    'liverpool': ('REGION^1246', 5.0),
}

def find_location_match(location_name: str) -> tuple[str, float] | None:
    """Finds the best match for a location name."""
    location_lower = location_name.lower().strip()
    
    # Direct match
    if location_lower in UK_LOCATIONS:
        return UK_LOCATIONS[location_lower]
    
    # Partial match
    for key, value in UK_LOCATIONS.items():
        if key in location_lower or location_lower in key:
            return value
    
    return None

def validate_radius(radius: float) -> float:
    """Ensures the radius is one of Rightmove's accepted values."""
    valid_radii = [0.0, 0.25, 0.5, 1.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0]
    closest = min(valid_radii, key=lambda x: abs(x - radius))
    
    if closest != radius:
        print(f"  [WARN] Adjusted radius from {radius} to {closest} (Rightmove requirement)")
    
    return closest

def get_best_location_id(suggested_locations: list[str], fallback_city: str = "London") -> tuple[str, float]:
    """Tries to find a Rightmove ID from suggested locations."""
    
    print(f"\n[LOCATION RESOLVER] Analyzing suggestions: {suggested_locations}")
    # [LOCATION RESOLVER] Analyzing suggestions: ['Bloomsbury', "King's Cross", 'Camden']
    
    # Try each suggested location
    for location in suggested_locations:
        result = find_location_match(location)
        if result:
            location_id, radius = result
            radius = validate_radius(radius)
            print(f"  ✓ Matched '{location}' → {location_id} (radius: {radius} miles)")
            return (location_id, radius)
        else:
            print(f"  ✗ No match for '{location}'")
    
    # Fallback to city
    print(f"\n[WARN] No match found. Trying city: '{fallback_city}'") # [WARN] No match found. Trying city: 'London'
    fallback_result = find_location_match(fallback_city)
    
    if fallback_result:
        location_id, radius = fallback_result
        radius = validate_radius(radius)
        print(f"  ✓ Using city fallback: {location_id} (radius: {radius} miles)") # ✓ Using city fallback: REGION^87490 (radius: 5.0 miles)
        return (location_id, radius)
    
    # Ultimate fallback
    print(f"\n[ERROR] Could not resolve '{fallback_city}'. Defaulting to Greater London.")
    return ("REGION^87490", 5.0)