import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gemini_interface import extract_criteria

def run_gemini_test():
    """Tests the Gemini interface for criteria extraction."""
    print("\n--- Running Test 3: Gemini Criteria Extraction ---")
    
    test_query = "Find me a studio flat near King's Cross, London. My budget is £1400 per month and I need to get there in under 25 minutes."
    
    print(f"Sending test query to Gemini:\n'{test_query}'")
    
    criteria = extract_criteria(test_query)
    
    if criteria and isinstance(criteria, dict):
        print("\n✅ Gemini responded with valid JSON.")
        print("Extracted Criteria:")
        print(json.dumps(criteria, indent=2))
        
        # Basic validation
        if 'max_budget' in criteria and criteria['max_budget'] == 1400:
            print("  - ✅ Max budget correctly extracted.")
        else:
            print("  - ❌ Max budget seems incorrect.")
            
        if 'max_travel_time' in criteria and criteria['max_travel_time'] == 25:
            print("  - ✅ Max travel time correctly extracted.")
        else:
            print("  - ❌ Max travel time seems incorrect.")
            
        if 'destination' in criteria and 'king\'s cross' in criteria['destination'].lower():
            print("  - ✅ Destination correctly extracted.")
        else:
            print("  - ❌ Destination seems incorrect.")
    else:
        print("\n❌ FAILED to get a valid response from Gemini. Check your API key and the prompt in `gemini_interface.py`.")
        
    print("\n--- Test 3 Finished ---")

if __name__ == "__main__":
    run_gemini_test()