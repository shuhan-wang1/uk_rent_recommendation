"""
Debug script to test Overpass API query format
"""

import requests
import math

def test_overpass_query():
    """Test different query formats for Overpass API"""
    
    # Coordinates for Burnell Building, Brent Cross
    lat, lng = 51.5646, -0.2232
    radius_m = 1500
    
    print("Testing Overpass API Query Formats")
    print("=" * 70)
    print(f"Target: {lat:.4f}, {lng:.4f}")
    print(f"Radius: {radius_m}m")
    
    # Calculate bounding box
    lat_offset = (radius_m / 1000) / 111.0
    lng_offset = (radius_m / 1000) / (111.0 * math.cos(math.radians(lat)))
    
    south = lat - lat_offset
    west = lng - lng_offset
    north = lat + lat_offset
    east = lng + lng_offset
    
    print(f"\nBounding box: ({south:.6f},{west:.6f},{north:.6f},{east:.6f})")
    
    # Try Query Format 1: Using node query with multiple tags
    query1 = f"""[out:json];
(
  node["leisure"="fitness_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
  node["leisure"="sports_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
);
out center;"""
    
    print("\n" + "-" * 70)
    print("Query Format 1 (Multiple tags as separate queries):")
    print(query1)
    
    try:
        print("\nTrying POST request...")
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query1,
            timeout=5,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])
            print(f"Found {len(elements)} elements")
            if elements:
                print("SUCCESS!")
        else:
            print(f"Error: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Try Query Format 2: Using OR syntax
    query2 = f"""[out:json];
(
  node["leisure"~"fitness_centre|sports_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
);
out center;"""
    
    print("\n" + "-" * 70)
    print("Query Format 2 (Using regex OR):")
    print(query2)
    
    try:
        print("\nTrying POST request...")
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query2,
            timeout=5
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            elements = data.get('elements', [])
            print(f"Found {len(elements)} elements")
            if elements:
                print("SUCCESS!")
        else:
            print(f"Error: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_overpass_query()
