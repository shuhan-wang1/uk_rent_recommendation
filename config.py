import os
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

# Get API keys from environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
CSV_FILE_PATH = 'combined_search_results.csv'

# Exit if API keys are not found
if not GEMINI_API_KEY or not GOOGLE_MAPS_API_KEY:
    print("ERROR: API keys for Gemini or Google Maps are not found.")
    print("Please create a .env file and add your API keys.")
    sys.exit(1)