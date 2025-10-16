"""
Debug script to see what Overpass API actually returns
"""

import requests
import json
import math

def debug_overpass_response():
    """Debug what Overpass API returns"""
    
    # Coordinates for Burnell Building, Brent Cross
    lat, lng = 51.5646, -0.2232
    radius_m = 1500
    
    # Calculate bounding box
    lat_offset = (radius_m / 1000) / 111.0
    lng_offset = (radius_m / 1000) / (111.0 * math.cos(math.radians(lat)))
    
    south = lat - lat_offset
    west = lng - lng_offset
    north = lat + lat_offset
    east = lng + lng_offset
    
    query = f"""[out:json];
(
  node["leisure"="fitness_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
  node["leisure"="sports_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
  way["leisure"="fitness_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
  way["leisure"="sports_centre"]({south:.6f},{west:.6f},{north:.6f},{east:.6f});
);
out center;"""
    
    print("Sending query to Overpass API...")
    response = requests.post("https://overpass-api.de/api/interpreter", data=query, timeout=5)
    
    if response.status_code == 200:
        data = response.json()
        elements = data.get('elements', [])
        
        print(f"\nFound {len(elements)} elements")
        print(f"\nFirst element structure:")
        if elements:
            print(json.dumps(elements[0], indent=2))
            
            # Check what keys are available
            elem = elements[0]
            print(f"\nKeys in first element: {elem.keys()}")
            if 'center' in elem:
                print(f"center keys: {elem['center'].keys()}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    debug_overpass_response()
