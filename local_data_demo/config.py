# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API (optional if using Ollama)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Google Maps API (PAID - most accurate)
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')

# OpenRouteService (FREE - less accurate but good enough)
OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY', '')

# Choose which service to use for travel time calculation
# Options: 'google' (accurate, paid), 'openroute' (free, approximate)
USE_TRAVEL_SERVICE = 'google'  # Change to 'openroute' if you want free