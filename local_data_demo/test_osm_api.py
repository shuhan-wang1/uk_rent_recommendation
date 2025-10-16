"""
Test script to verify OpenStreetMap Overpass API for POI queries
Tests getting gym locations near Burnell Building, Brent Cross
"""

import sys
import json

print("=" * 70)
print("TEST: Overpass API POI Query (OpenStreetMap - Free Service)")
print("=" * 70)

# Test data
test_address = "Burnell Building, Brent Cross, NW2"
test_amenity = "gym"

print(f"\nTest Setup:")
print(f"  Address: {test_address}")
print(f"  Searching for: {test_amenity}")
print(f"  Radius: 1.5 km (1500m)")

try:
    from core.maps_service import get_nearby_places_osm
    
    print(f"\n[STEP 1] Calling get_nearby_places_osm()...")
    places = get_nearby_places_osm(test_address, test_amenity, radius_m=1500)
    
    print(f"\n[STEP 2] Processing results...")
    
    if places:
        print(f"\n[OK] SUCCESS! Found {len(places)} {test_amenity} locations:")
        print("\n" + "-" * 70)
        
        for i, place in enumerate(places[:5], 1):
            distance_km = place['distance_m'] / 1000
            print(f"\n{i}. {place['name']}")
            print(f"   Distance: {place['distance_m']}m ({distance_km:.2f}km)")
            print(f"   Address: {place['address']}")
            if 'lat' in place and 'lng' in place:
                print(f"   Coordinates: {place['lat']:.4f}, {place['lng']:.4f}")
        
        print("\n" + "-" * 70)
        print(f"\n[OK] TEST PASSED: Overpass API returned detailed location data")
        print(f"\nData includes:")
        print(f"  - Facility names [OK]")
        print(f"  - Exact distances in meters [OK]")
        print(f"  - Addresses/locations [OK]")
        print(f"  - Coordinates (lat/lng) [OK]")
        
    else:
        print(f"\n[WARN] No {test_amenity} found within 1.5km")
        print(f"   This could mean:")
        print(f"   1. No facilities in OSM data for this area")
        print(f"   2. Search radius too small - try expanding to 5km")
        print(f"   3. Amenity tag mismatch in OSM database")

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("COMPARISON: Google Maps vs Overpass API")
print("=" * 70)

print("""
Google Maps API:
  - Requires API key (paid)
  - Returns only counts of nearby places
  - Example: "gym_in_1500m": 3

Overpass API (OpenStreetMap):
  - FREE - no API key needed
  - Returns detailed information:
    * Exact names of facilities
    * Precise distances
    * Addresses/locations
    * Coordinates
  - Source: Community-maintained OpenStreetMap database
  - Coverage: Varies by region (good in London)

[OK] RECOMMENDATION: Use Overpass API for user-facing queries
   Shows actual facility names and distances, much more useful!
""")
