# test_ors.py - Run this to verify OpenRouteService is working

import sys
sys.path.append('.')

print("=" * 60)
print("OpenRouteService Configuration Test")
print("=" * 60)

# Test 1: Check if API key is loaded
print("\n1. Checking API Key Configuration...")
try:
    from config import OPENROUTESERVICE_API_KEY
    if OPENROUTESERVICE_API_KEY and OPENROUTESERVICE_API_KEY != 'YOUR_KEY_HERE':
        print(f"   ✓ API Key found: {OPENROUTESERVICE_API_KEY[:20]}...")
        key_valid = True
    else:
        print("   ❌ API Key not configured or still set to default")
        print("   → Add to config.py: OPENROUTESERVICE_API_KEY = 'your_key'")
        key_valid = False
except ImportError:
    print("   ❌ Could not import OPENROUTESERVICE_API_KEY from config.py")
    key_valid = False

# Test 2: Try a real API call
if key_valid:
    print("\n2. Testing OpenRouteService API...")
    import requests
    
    url = "https://api.openrouteservice.org/v2/directions/foot-walking"
    headers = {
        'Authorization': OPENROUTESERVICE_API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Test route: UCL to King's Cross
    payload = {
        'coordinates': [
            [-0.1340, 51.5246],  # UCL
            [-0.1239, 51.5309]   # King's Cross
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            duration_minutes = int(data['routes'][0]['summary']['duration'] / 60)
            distance_km = data['routes'][0]['summary']['distance'] / 1000
            print(f"   ✓ API is working!")
            print(f"   ✓ Test route (UCL → King's Cross): {duration_minutes} mins, {distance_km:.1f} km")
        elif response.status_code == 401:
            print(f"   ❌ Authentication failed (401)")
            print(f"   → Your API key is invalid")
        elif response.status_code == 403:
            print(f"   ❌ Forbidden (403)")
            print(f"   → Rate limit exceeded or key expired")
        else:
            print(f"   ❌ API returned status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Request failed: {e}")

# Test 3: Check if free_maps_service.py has ORS integration
print("\n3. Checking free_maps_service.py integration...")
try:
    from free_maps_service import calculate_travel_time
    import inspect
    source = inspect.getsource(calculate_travel_time)
    
    if '_calculate_ors_route' in source or 'openrouteservice' in source.lower():
        print("   ✓ ORS integration found in calculate_travel_time()")
    else:
        print("   ❌ ORS integration NOT found in calculate_travel_time()")
        print("   → You need to update free_maps_service.py with the version from artifacts")
except Exception as e:
    print(f"   ❌ Error checking integration: {e}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)