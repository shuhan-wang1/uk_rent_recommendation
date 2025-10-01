# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Gemini API (now optional if using Ollama)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Google Maps (NO LONGER NEEDED!)
# GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

# OpenRouteService (FREE!)
OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY', 'YOUR_KEY_HERE')