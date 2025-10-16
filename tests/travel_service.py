# travel_service.py - Unified travel time interface

from config import USE_TRAVEL_SERVICE, GOOGLE_MAPS_API_KEY, OPENROUTESERVICE_API_KEY

def calculate_travel_time(origin: str, destination: str, mode: str = "transit") -> int | None:
    """
    Unified interface for travel time calculation.
    Automatically uses the configured service (Google Maps or OpenRouteService).
    """
    
    if USE_TRAVEL_SERVICE == 'google' and GOOGLE_MAPS_API_KEY:
        print(f"  [Using Google Maps for accurate routing]")
        from maps_service import calculate_travel_time as google_calc
        return google_calc(origin, destination, mode)
    
    elif USE_TRAVEL_SERVICE == 'openroute' or not GOOGLE_MAPS_API_KEY:
        print(f"  [Using OpenRouteService for free routing]")
        from free_maps_service import calculate_travel_time as ors_calc
        return ors_calc(origin, destination, mode)
    
    else:
        print(f"  [ERROR] No valid travel service configured")
        return None