import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maps_service import calculate_travel_time

def run_maps_test():
    """Tests the Google Maps service for travel time calculation."""
    print("\n--- Running Test 4: Google Maps Travel Time ---")
    
    # Define a sample origin and destination for testing
    origin_address = "Wembley Park Station, London"
    destination_address = "UCL, Gower Street, London"
    
    print(f"Calculating travel time from '{origin_address}' to '{destination_address}'...")
    
    travel_time = calculate_travel_time(origin_address, destination_address)
    
    if travel_time is not None:
        print(f"✅ Success! Estimated public transport time: {travel_time} minutes.")
        if 20 < travel_time < 60:
            print("  - The result is within a reasonable range.")
        else:
            print("  - Warning: The result is outside the expected range (20-60 mins).")
    else:
        print("❌ FAILED to calculate travel time. Check your Google Maps API key and ensure the 'Directions API' is enabled.")
        
    print("\n--- Test 4 Finished ---")

if __name__ == "__main__":
    run_maps_test()