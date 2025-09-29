import os
import sys

# Adjust the path to import from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import GEMINI_API_KEY, GOOGLE_MAPS_API_KEY, CSV_FILE_PATH

def run_config_test():
    """Tests if the configuration is loaded correctly."""
    print("--- Running Test 1: Configuration and API Keys ---")
    
    has_error = False
    
    # Test Gemini API Key
    if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
        print("✅ Gemini API Key: Loaded successfully.")
    else:
        print("❌ Gemini API Key: FAILED to load. Check your .env file.")
        has_error = True
        
    # Test Google Maps API Key
    if GOOGLE_MAPS_API_KEY and len(GOOGLE_MAPS_API_KEY) > 10:
        print("✅ Google Maps API Key: Loaded successfully.")
    else:
        print("❌ Google Maps API Key: FAILED to load. Check your .env file.")
        has_error = True
        
    # Test CSV File Path
    if os.path.exists(CSV_FILE_PATH):
        print(f"✅ CSV File: Found at '{CSV_FILE_PATH}'.")
    else:
        print(f"❌ CSV File: NOT FOUND at '{CSV_FILE_PATH}'. Make sure it's in the correct directory.")
        has_error = True
        
    print("\n--- Test 1 Finished ---")
    if has_error:
        print("⚠️ Please fix the configuration errors before proceeding.")
    else:
        print("🎉 Configuration test passed!")

if __name__ == "__main__":
    run_config_test()