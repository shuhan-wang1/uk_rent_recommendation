"""
Property Amenity Map Generator
Integrates OpenStreetMap visualization for property recommendations
"""

import folium
from folium import plugins
import requests
import time
from typing import Dict, List, Tuple, Optional
import random
import math
from pathlib import Path


class PropertyAmenityMapGenerator:
    """
    Generate interactive maps showing properties and nearby amenities
    using OpenStreetMap data.
    """
    
    def __init__(self, radius_km: float = 1.5):
        """
        Initialize the map generator.
        
        Args:
            radius_km: Radius in kilometers to search for amenities (default: 1.5)
        """
        self.radius_km = radius_km
        self.radius_m = radius_km * 1000  # Convert to meters
        
        # Define amenity categories and their OSM tags
        # Matches the original property_amenity_map.py configuration
        self.amenity_config = {
            'supermarkets': {
                'osm_type': 'supermarket',
                'tags': {'shop': 'supermarket'},
                'color': 'blue',
                'icon': 'shopping-cart',
                'name': 'Supermarkets'
            },
            'convenience_stores': {
                'osm_type': 'convenience',
                'tags': {'shop': 'convenience'},
                'color': 'green',
                'icon': 'shopping-basket',
                'name': 'Convenience Stores'
            },
            'restaurants_chinese': {
                'osm_type': 'restaurant',
                'tags': {'amenity': 'restaurant'},
                'cuisine_filter': 'chinese',
                'color': 'darkred',
                'icon': 'cutlery',
                'name': 'Chinese Restaurants'
            },
            'restaurants_italian': {
                'osm_type': 'restaurant',
                'tags': {'amenity': 'restaurant'},
                'cuisine_filter': 'italian',
                'color': 'red',
                'icon': 'cutlery',
                'name': 'Italian Restaurants'
            },
            'restaurants_indian': {
                'osm_type': 'restaurant',
                'tags': {'amenity': 'restaurant'},
                'cuisine_filter': 'indian',
                'color': 'orange',
                'icon': 'cutlery',
                'name': 'Indian Restaurants'
            },
            'cafes': {
                'osm_type': 'cafe',
                'tags': {'amenity': 'cafe'},
                'color': 'lightblue',
                'icon': 'coffee',
                'name': 'Cafés'
            },
            'parks': {
                'osm_type': 'park',
                'tags': {'leisure': 'park'},
                'color': 'darkgreen',
                'icon': 'tree',
                'name': 'Parks'
            },
            'pharmacies': {
                'osm_type': 'pharmacy',
                'tags': {'amenity': 'pharmacy'},
                'color': 'purple',
                'icon': 'plus-sign',
                'name': 'Pharmacies'
            },
            'banks': {
                'osm_type': 'bank',
                'tags': {'amenity': 'bank'},
                'color': 'darkblue',
                'icon': 'gbp',
                'name': 'Banks'
            },
            'metro_stations': {
                'osm_type': 'station',
                'tags': {'railway': 'station'},
                'color': 'gray',
                'icon': 'train',
                'name': 'Metro Stations'
            }
        }
        
    def parse_geo_location(self, geo_location_str: str) -> Optional[Tuple[float, float]]:
        """
        Parse geo_location string into (lat, lon) tuple.
        
        Args:
            geo_location_str: String in format "lat, lon" or dict with lat/lng keys
            
        Returns:
            Tuple of (latitude, longitude) or None if parsing fails
        """
        if not geo_location_str:
            return None
        
        try:
            # Handle string format: "51.5525, -0.1350"
            if isinstance(geo_location_str, str):
                parts = geo_location_str.strip().split(',')
                if len(parts) == 2:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    
                    # Validate coordinates are within UK bounds
                    if 50.0 <= lat <= 59.0 and -8.0 <= lon <= 2.0:
                        return (lat, lon)
            # Handle dict format: {'lat': 51.5525, 'lng': -0.1350}
            elif isinstance(geo_location_str, dict):
                lat = float(geo_location_str.get('lat', 0))
                lon = float(geo_location_str.get('lng') or geo_location_str.get('lon', 0))
                if 50.0 <= lat <= 59.0 and -8.0 <= lon <= 2.0:
                    return (lat, lon)
        except (ValueError, AttributeError, TypeError) as e:
            print(f"    ✗ Failed to parse coordinates: {geo_location_str} - {e}")
            return None
        
        return None
    
    def query_osm_amenities_with_filter(self, lat: float, lon: float, 
                                        amenity_type: str, 
                                        cuisine_filter: str = None) -> List[dict]:
        """
        Query OpenStreetMap for amenities with optional cuisine filter.
        This replicates the original property_amenity_map.py query logic.
        
        Args:
            lat: Latitude of the center point
            lon: Longitude of the center point
            amenity_type: Type of amenity config key
            cuisine_filter: Optional cuisine type to filter (e.g., 'chinese', 'italian')
            
        Returns:
            List of amenity dictionaries
        """
        config = self.amenity_config[amenity_type]
        
        # Build Overpass QL query using tags from config
        query_parts = []
        for key, value in config['tags'].items():
            query_parts.append(f'  node["{key}"="{value}"](around:{self.radius_m},{lat},{lon});')
            query_parts.append(f'  way["{key}"="{value}"](around:{self.radius_m},{lat},{lon});')
        
        overpass_query = f"""
        [out:json][timeout:25];
        (
        {''.join(query_parts)}
        );
        out center;
        """
        
        overpass_url = "https://overpass-api.de/api/interpreter"
        
        try:
            import time
            time.sleep(1)  # Be respectful to Overpass API
            response = requests.post(overpass_url, data={'data': overpass_query}, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            amenities = []
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                
                # Filter by cuisine if specified
                if cuisine_filter:
                    cuisine = tags.get('cuisine', '').lower()
                    if cuisine_filter not in cuisine:
                        continue
                
                amenity = {
                    'name': tags.get('name', 'Unnamed'),
                }
                
                # Get coordinates based on element type
                if element['type'] == 'node':
                    amenity['lat'] = element['lat']
                    amenity['lon'] = element['lon']
                elif element['type'] == 'way' and 'center' in element:
                    amenity['lat'] = element['center']['lat']
                    amenity['lon'] = element['center']['lon']
                else:
                    continue
                
                # Add additional tags if available
                if 'cuisine' in tags:
                    amenity['cuisine'] = tags['cuisine']
                if 'opening_hours' in tags:
                    amenity['opening_hours'] = tags['opening_hours']
                
                # Calculate distance
                import math
                R = 6371000  # Earth's radius in meters
                lat1_rad = math.radians(lat)
                lat2_rad = math.radians(amenity['lat'])
                delta_lat = math.radians(amenity['lat'] - lat)
                delta_lng = math.radians(amenity['lon'] - lon)
                
                a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                amenity['distance_m'] = int(R * c)
                
                amenities.append(amenity)
            
            print(f"    Found {len(amenities)} {config['name']}")
            return amenities
            
        except Exception as e:
            print(f"    Error querying {config['name']}: {e}")
            return []
    
    def create_map_for_property(self, 
                                property_data: dict,
                                amenities_data: Dict[str, List[dict]],
                                output_path: str) -> bool:
        """
        Create an interactive map for a single property with amenity layers.
        
        Args:
            property_data: Dictionary containing property information
            amenities_data: Dictionary mapping amenity types to lists of amenity data
            output_path: Path where the HTML map will be saved
            
        Returns:
            True if successful, False otherwise
        """
        # Get coordinates
        geo_location = property_data.get('geo_location') or property_data.get('coordinates')
        coords = self.parse_geo_location(geo_location)
        
        if not coords:
            print(f"  ✗ No valid coordinates for property")
            return False
        
        lat, lon = coords
        
        # Create base map centered on the property
        m = folium.Map(
            location=[lat, lon],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
        
        # Add the property marker (always visible)
        property_popup = f"""
        <div style="font-family: Arial; min-width: 200px;">
            <h4 style="margin-bottom: 10px; color: #2c3e50;">🏠 Property</h4>
            <b>Price:</b> {property_data.get('Price', property_data.get('price', 'N/A'))}<br>
            <b>Address:</b> {property_data.get('Address', property_data.get('address', 'N/A'))}<br>
            <b>Travel Time:</b> {property_data.get('travel_time_minutes', property_data.get('travel_time', 'N/A'))} min<br>
        </div>
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(property_popup, max_width=300),
            tooltip=f"Property: {property_data.get('Address', property_data.get('address', 'Unknown'))[:40]}...",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Add search radius circle
        folium.Circle(
            location=[lat, lon],
            radius=self.radius_m,
            color='red',
            fill=False,
            opacity=0.3,
            weight=2,
            tooltip=f'{self.radius_km}km search radius'
        ).add_to(m)
        
        # Add amenities for each category
        print(f"  Adding amenity layers to map...")
        
        for amenity_type, config in self.amenity_config.items():
            amenities = amenities_data.get(amenity_type, [])
            
            if amenities:
                # Create a feature group for this amenity type (for layer control)
                feature_group = folium.FeatureGroup(name=config['name'], show=True)
                
                for amenity in amenities:
                    # Build popup HTML
                    popup_html = f"""
                    <div style="font-family: Arial; min-width: 150px;">
                        <h4 style="margin-bottom: 10px; color: {config['color']};">
                            {amenity.get('name', 'Unknown')}
                        </h4>
                    """
                    
                    if 'distance_m' in amenity:
                        popup_html += f"<b>Distance:</b> {amenity.get('distance_m')}m<br>"
                    if 'cuisine' in amenity:
                        popup_html += f"<b>Cuisine:</b> {amenity['cuisine']}<br>"
                    if 'opening_hours' in amenity:
                        popup_html += f"<b>Hours:</b> {amenity['opening_hours']}<br>"
                    if 'address' in amenity and not amenity['address'].startswith('('):
                        popup_html += f"<b>Address:</b> {amenity['address']}<br>"
                    
                    popup_html += "</div>"
                    
                    folium.Marker(
                        location=[amenity['lat'], amenity.get('lon', amenity.get('lng'))],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=amenity.get('name', 'Unknown'),
                        icon=folium.Icon(
                            color=config['color'],
                            icon=config['icon'],
                            prefix='fa'
                        )
                    ).add_to(feature_group)
                
                feature_group.add_to(m)
                print(f"    ✓ Added {len(amenities)} {config['name']}")
        
        # Add layer control to toggle amenity types
        folium.LayerControl(
            position='topright',
            collapsed=False
        ).add_to(m)
        
        # Add custom HTML button to hide all layers
        hide_all_html = """
        <div style="position: fixed; bottom: 10px; right: 10px; background: white; 
                    border: 2px solid #3498db; padding: 10px 15px; border-radius: 5px; 
                    z-index: 999; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
            <button id="hideAllBtn" style="padding: 8px 12px; background: #e74c3c; 
                    color: white; border: none; border-radius: 3px; cursor: pointer; 
                    font-weight: bold;">
                Hide All Layers
            </button>
            <button id="showAllBtn" style="padding: 8px 12px; background: #27ae60; 
                    color: white; border: none; border-radius: 3px; cursor: pointer; 
                    font-weight: bold; margin-left: 5px;">
                Show All Layers
            </button>
        </div>
        """
        m.get_root().html.add_child(folium.Element(hide_all_html))
        
        # Add JavaScript to handle button clicks
        js_code = """
        <script>
            document.getElementById('hideAllBtn').addEventListener('click', function() {
                var layers = document.querySelectorAll('input[type="checkbox"]');
                layers.forEach(function(checkbox) {
                    if (checkbox.checked) {
                        checkbox.click();
                    }
                });
            });
            
            document.getElementById('showAllBtn').addEventListener('click', function() {
                var layers = document.querySelectorAll('input[type="checkbox"]');
                layers.forEach(function(checkbox) {
                    if (!checkbox.checked) {
                        checkbox.click();
                    }
                });
            });
        </script>
        """
        m.get_root().html.add_child(folium.Element(js_code))
        
        # Add fullscreen button
        plugins.Fullscreen(
            position='topleft',
            title='Fullscreen',
            title_cancel='Exit Fullscreen',
            force_separate_button=True
        ).add_to(m)
        
        # Save the map
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        m.save(output_path)
        print(f"  ✓ Map saved to: {output_path}")
        
        return True
    
    def generate_map_html(self,
                         property_data: dict,
                         amenities_data: Dict[str, List[dict]]) -> str:
        """
        Generate map HTML as a string (for embedding or direct serving).
        
        Args:
            property_data: Dictionary containing property information
            amenities_data: Dictionary mapping amenity types to lists of amenity data
            
        Returns:
            HTML string of the generated map
        """
        # Get coordinates
        geo_location = property_data.get('geo_location') or property_data.get('coordinates')
        coords = self.parse_geo_location(geo_location)
        
        if not coords:
            return "<html><body><h1>Error: Invalid coordinates</h1></body></html>"
        
        lat, lon = coords
        
        # Create base map
        m = folium.Map(
            location=[lat, lon],
            zoom_start=15,
            tiles='OpenStreetMap'
        )
        
        # Add the property marker
        property_popup = f"""
        <div style="font-family: Arial; min-width: 200px;">
            <h4 style="margin-bottom: 10px; color: #2c3e50;">🏠 Property</h4>
            <b>Price:</b> {property_data.get('Price', property_data.get('price', 'N/A'))}<br>
            <b>Address:</b> {property_data.get('Address', property_data.get('address', 'N/A'))}<br>
            <b>Travel Time:</b> {property_data.get('travel_time_minutes', property_data.get('travel_time', 'N/A'))} min<br>
        </div>
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(property_popup, max_width=300),
            tooltip=f"Property",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Add search radius circle
        folium.Circle(
            location=[lat, lon],
            radius=self.radius_m,
            color='red',
            fill=False,
            opacity=0.3,
            weight=2,
            tooltip=f'{self.radius_km}km search radius'
        ).add_to(m)
        
        # Add amenities
        for amenity_type, config in self.amenity_config.items():
            amenities = amenities_data.get(amenity_type, [])
            
            if amenities:
                feature_group = folium.FeatureGroup(name=config['name'], show=True)
                
                for amenity in amenities:
                    popup_html = f"""
                    <div style="font-family: Arial; min-width: 150px;">
                        <h4 style="margin-bottom: 10px; color: {config['color']};">
                            {amenity.get('name', 'Unknown')}
                        </h4>
                        <b>Distance:</b> {amenity.get('distance_m', 'N/A')}m<br>
                    """
                    
                    if 'cuisine' in amenity:
                        popup_html += f"<b>Cuisine:</b> {amenity['cuisine']}<br>"
                    
                    popup_html += "</div>"
                    
                    folium.Marker(
                        location=[amenity['lat'], amenity.get('lon', amenity.get('lng'))],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=amenity.get('name', 'Unknown'),
                        icon=folium.Icon(
                            color=config['color'],
                            icon=config['icon'],
                            prefix='fa'
                        )
                    ).add_to(feature_group)
                
                feature_group.add_to(m)
        
        # Add layer control
        folium.LayerControl(position='topright', collapsed=False).add_to(m)
        
        # Add control buttons
        hide_all_html = """
        <div style="position: fixed; bottom: 10px; right: 10px; background: white; 
                    border: 2px solid #3498db; padding: 10px 15px; border-radius: 5px; 
                    z-index: 999; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
            <button id="hideAllBtn" style="padding: 8px 12px; background: #e74c3c; 
                    color: white; border: none; border-radius: 3px; cursor: pointer; 
                    font-weight: bold;">
                Hide All
            </button>
            <button id="showAllBtn" style="padding: 8px 12px; background: #27ae60; 
                    color: white; border: none; border-radius: 3px; cursor: pointer; 
                    font-weight: bold; margin-left: 5px;">
                Show All
            </button>
        </div>
        """
        m.get_root().html.add_child(folium.Element(hide_all_html))
        
        js_code = """
        <script>
            document.getElementById('hideAllBtn').addEventListener('click', function() {
                var layers = document.querySelectorAll('input[type="checkbox"]');
                layers.forEach(function(checkbox) {
                    if (checkbox.checked) checkbox.click();
                });
            });
            document.getElementById('showAllBtn').addEventListener('click', function() {
                var layers = document.querySelectorAll('input[type="checkbox"]');
                layers.forEach(function(checkbox) {
                    if (!checkbox.checked) checkbox.click();
                });
            });
        </script>
        """
        m.get_root().html.add_child(folium.Element(js_code))
        
        # Add fullscreen
        plugins.Fullscreen(
            position='topleft',
            title='Fullscreen',
            title_cancel='Exit',
            force_separate_button=True
        ).add_to(m)
        
        # Return HTML as string
        return m._repr_html_()
