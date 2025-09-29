import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from web_search import search_crime_data, search_cost_of_living

def run_web_search_test():
    """Tests the web search functionality using DuckDuckGo."""
    print("\n--- Running Test 5: DuckDuckGo Web Search ---")
    
    test_area = "Islington, London"
    
    print(f"Searching for crime data for '{test_area}'...")
    crime_info = search_crime_data(test_area)
    if crime_info and "Could not retrieve" not in crime_info:
        print("✅ Success! Retrieved crime info snippet:")
        print(f"  -> {crime_info[:150]}...") # Print first 150 chars
    else:
        print("❌ FAILED to retrieve crime info.")
        
    print(f"\nSearching for cost of living for '{test_area}'...")
    cost_info = search_cost_of_living(test_area)
    if cost_info and "Could not retrieve" not in cost_info:
        print("✅ Success! Retrieved cost of living snippet:")
        print(f"  -> {cost_info[:150]}...") # Print first 150 chars
    else:
        print("❌ FAILED to retrieve cost of living info.")
        
    print("\n--- Test 5 Finished ---")
    
if __name__ == "__main__":
    run_web_search_test()