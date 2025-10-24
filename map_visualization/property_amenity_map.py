"""
Property Amenity Visualization using OpenStreetMap
This script creates interactive maps showing properties and nearby amenities
within a 1.5km radius using public OpenStreetMap services.

Includes DEMO MODE for testing without API access.
"""

import pandas as pd
import folium
from folium import plugins
import requests
import time
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
import random
import math


class PropertyAmenityMapper:
    """
    A class to create interactive maps showing properties and nearby amenities
    using OpenStreetMap data.
    """
    
    def __init__(self, csv_path: str, radius_km: float = 1.5, demo_mode: bool = False):
        """
        Initialize the mapper with CSV data and search radius.
        
        Args:
            csv_path: Path to the CSV file containing property listings (must include geo_location column)
            radius_km: Radius in kilometers to search for amenities (default: 1.5)
            demo_mode: If True, use simulated amenity data instead of live OSM API calls
        """
        self.csv_path = csv_path
        self.radius_km = radius_km
        self.radius_m = radius_km * 1000  # Convert to meters for Overpass API
        self.properties_df = None
        self.demo_mode = demo_mode
        
        # Demo amenity names for realistic simulation
        self.demo_amenity_names = {
            'supermarkets': ['Tesco Express', 'Sainsbury\'s Local', 'Waitrose', 'M&S Food', 'Co-op', 'Asda'],
            'convenience_stores': ['Londis', 'Costcutter', 'Nisa Local', 'Premier Store', 'One Stop'],
            'restaurants_chinese': ['Pearl Lemon', 'Dragon Palace', 'Jade Garden', 'New Shanghai', 'Golden Dragon', 'Happy Wok', 'Dynasty'],
            'restaurants_italian': ['Bella Italia', 'Pasta Prima', 'Italian Kitchen', 'Marco\'s Restaurant', 'Trattoria Milano'],
            'restaurants_indian': ['Curry House', 'Spice Route', 'Maharaja', 'Bengal Tiger', 'Tandoori Palace'],
            'cafes': ['Starbucks', 'Costa Coffee', 'Caffè Nero', 'Pret A Manger', 'Gail\'s Bakery', 'Local Coffee Shop'],
            'parks': ['Green Park', 'Community Garden', 'Recreation Ground', 'Public Garden', 'Nature Reserve'],
            'pharmacies': ['Boots', 'Lloyds Pharmacy', 'Superdrug', 'Well Pharmacy', 'Local Pharmacy'],
            'banks': ['Barclays', 'HSBC', 'Lloyds Bank', 'NatWest', 'Santander', 'Metro Bank'],
            'metro_stations': ['King\'s Cross St Pancras', 'Oxford Circus', 'Piccadilly Circus', 'Waterloo', 'Victoria', 'Liverpool Street']
        }
        
        # Define amenity categories and their OSM tags
        self.amenity_config = {
            'supermarkets': {
                'tags': {'shop': 'supermarket'},
                'color': 'blue',
                'icon': 'shopping-cart',
                'name': 'Supermarkets'
            },
            'convenience_stores': {
                'tags': {'shop': 'convenience'},
                'color': 'green',
                'icon': 'shopping-basket',
                'name': 'Convenience Stores'
            },
            'restaurants_chinese': {
                'tags': {'amenity': 'restaurant'},
                'cuisine_filter': 'chinese',
                'color': 'darkred',
                'icon': 'cutlery',
                'name': 'Chinese Restaurants'
            },
            'cafes': {
                'tags': {'amenity': 'cafe'},
                'color': 'orange',
                'icon': 'coffee',
                'name': 'Cafés'
            },
            'parks': {
                'tags': {'leisure': 'park'},
                'color': 'darkgreen',
                'icon': 'tree',
                'name': 'Parks'
            },
            'pharmacies': {
                'tags': {'amenity': 'pharmacy'},
                'color': 'purple',
                'icon': 'plus-sign',
                'name': 'Pharmacies'
            },
            'banks': {
                'tags': {'amenity': 'bank'},
                'color': 'darkblue',
                'icon': 'gbp',
                'name': 'Banks'
            },
            'metro_stations': {
                'tags': {'railway': 'station'},
                'color': 'gray',
                'icon': 'train',
                'name': 'Metro Stations'
            }
        }
        
    def load_properties(self) -> pd.DataFrame:
        """Load property data from CSV file."""
        print(f"Loading properties from {self.csv_path}...")
        self.properties_df = pd.read_csv(self.csv_path)
        print(f"Loaded {len(self.properties_df)} properties")
        
        # Check if geo_location column exists
        if 'geo_location' in self.properties_df.columns:
            print(f"✓ Found 'geo_location' column - will use provided coordinates")
        else:
            print(f"⚠️  Warning: 'geo_location' column not found in CSV")
        
        return self.properties_df
    
    def parse_geo_location(self, geo_location_str: str) -> Optional[Tuple[float, float]]:
        """
        Parse geo_location string from CSV into (lat, lon) tuple.
        
        Args:
            geo_location_str: String in format "lat, lon" e.g. "51.5525, -0.1350"
            
        Returns:
            Tuple of (latitude, longitude) or None if parsing fails
        """
        if not geo_location_str or pd.isna(geo_location_str):
            return None
        
        try:
            # Handle string format: "51.5525, -0.1350"
            parts = str(geo_location_str).strip().split(',')
            if len(parts) == 2:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                
                # Validate coordinates are within UK bounds
                if 50.0 <= lat <= 59.0 and -8.0 <= lon <= 2.0:
                    return (lat, lon)
                else:
                    print(f"    ⚠️  Coordinates out of UK bounds: ({lat:.6f}, {lon:.6f})")
                    return None
        except (ValueError, AttributeError) as e:
            print(f"    ✗ Failed to parse geo_location: {geo_location_str} - {e}")
            return None
        
        return None
    
    def generate_demo_amenities(self, lat: float, lon: float, amenity_type: str) -> List[Dict]:
        """
        Generate demo amenity data around a location.
        
        Args:
            lat: Latitude of the center point
            lon: Longitude of the center point
            amenity_type: Type of amenity to generate
            
        Returns:
            List of simulated amenity dictionaries
        """
        config = self.amenity_config[amenity_type]
        amenities = []
        
        # Generate random number of amenities (3-8 per type)
        num_amenities = random.randint(3, 8)
        
        for i in range(num_amenities):
            # Generate random position within radius
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0.2, self.radius_km)  # km
            
            # Convert to lat/lon offset (approximate)
            lat_offset = (distance / 111.0) * math.cos(angle)
            lon_offset = (distance / (111.0 * math.cos(math.radians(lat)))) * math.sin(angle)
            
            amenity_lat = lat + lat_offset
            amenity_lon = lon + lon_offset
            
            # Get random name from demo names
            name = random.choice(self.demo_amenity_names[amenity_type])
            
            amenity = {
                'name': name,
            }
            
            # Add cuisine for restaurant types
            if 'restaurants' in amenity_type:
                if 'chinese' in amenity_type:
                    amenity['cuisine'] = 'chinese'
                elif 'italian' in amenity_type:
                    amenity['cuisine'] = 'italian'
                elif 'indian' in amenity_type:
                    amenity['cuisine'] = 'indian'
            
            amenity['lat'] = amenity_lat
            amenity['lon'] = amenity_lon
            
            amenities.append(amenity)
        
        return amenities
    
    def query_amenities(self, lat: float, lon: float, amenity_type: str) -> List[Dict]:
        """
        Query OpenStreetMap for amenities near a location using Overpass API.
        In demo mode, generates simulated amenity data.
        
        Args:
            lat: Latitude of the center point
            lon: Longitude of the center point
            amenity_type: Type of amenity to search for
            
        Returns:
            List of amenity dictionaries with location and metadata
        """
        if self.demo_mode:
            amenities = self.generate_demo_amenities(lat, lon, amenity_type)
            print(f"    [DEMO] Generated {len(amenities)} {self.amenity_config[amenity_type]['name']}")
            return amenities
        
        config = self.amenity_config[amenity_type]
        
        # Build Overpass QL query
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
            # Be respectful to Overpass API
            time.sleep(1)
            response = requests.post(overpass_url, data={'data': overpass_query}, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            amenities = []
            for element in data.get('elements', []):
                tags = element.get('tags', {})
                
                # Filter by cuisine if specified
                if 'cuisine_filter' in config:
                    cuisine = tags.get('cuisine', '').lower()
                    if config['cuisine_filter'] not in cuisine:
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
                
                amenities.append(amenity)
            
            print(f"    Found {len(amenities)} {config['name']}")
            return amenities
            
        except Exception as e:
            print(f"    Error querying {config['name']}: {e}")
            return []
    
    def create_map_for_property(self, property_data: pd.Series, 
                                property_coords: Tuple[float, float],
                                output_path: str) -> None:
        """
        Create an interactive map for a single property with amenity layers.
        
        Args:
            property_data: Series containing property information
            property_coords: Tuple of (latitude, longitude) for the property
            output_path: Path where the HTML map will be saved
        """
        lat, lon = property_coords
        
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
            <b>Price:</b> {property_data['Price']}<br>
            <b>Address:</b> {property_data['Address']}<br>
            <b>Description:</b> {property_data['Description']}<br>
            <b>Available:</b> {property_data['Available From']}<br>
        </div>
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(property_popup, max_width=300),
            tooltip=f"Property: {property_data['Address'][:40]}...",
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
        
        # Query and add amenities for each category
        mode_text = "[DEMO MODE]" if self.demo_mode else ""
        print(f"\n  {mode_text} Querying amenities within {self.radius_km}km...")
        
        for amenity_type, config in self.amenity_config.items():
            amenities = self.query_amenities(lat, lon, amenity_type)
            
            if amenities:
                # Create a feature group for this amenity type (for layer control)
                feature_group = folium.FeatureGroup(name=config['name'], show=True)
                
                for amenity in amenities:
                    popup_html = f"""
                    <div style="font-family: Arial; min-width: 150px;">
                        <h4 style="margin-bottom: 10px; color: {config['color']};">
                            {amenity['name']}
                        </h4>
                    """
                    
                    if 'cuisine' in amenity:
                        popup_html += f"<b>Cuisine:</b> {amenity['cuisine']}<br>"
                    if 'opening_hours' in amenity:
                        popup_html += f"<b>Hours:</b> {amenity['opening_hours']}<br>"
                    
                    popup_html += "</div>"
                    
                    folium.Marker(
                        location=[amenity['lat'], amenity['lon']],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=amenity['name'],
                        icon=folium.Icon(
                            color=config['color'],
                            icon=config['icon'],
                            prefix='fa'
                        )
                    ).add_to(feature_group)
                
                feature_group.add_to(m)
        
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
        m.save(output_path)
        print(f"\n  ✓ Map saved to: {output_path}")
    
    def process_all_properties(self, output_dir: str = "maps") -> None:
        """
        Process all properties in the CSV and create individual maps.
        
        Args:
            output_dir: Directory where maps will be saved
        """
        if self.properties_df is None:
            self.load_properties()
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        mode_text = "DEMO MODE - Using simulated data" if self.demo_mode else "LIVE MODE - Using OpenStreetMap APIs"
        
        print(f"\n{'='*70}")
        print(f"Processing {len(self.properties_df)} properties...")
        print(f"Mode: {mode_text}")
        print(f"Search radius: {self.radius_km}km")
        print(f"{'='*70}\n")
        
        for idx, row in self.properties_df.iterrows():
            print(f"\n[Property {idx + 1}/{len(self.properties_df)}]")
            print(f"Address: {row['Address']}")
            
            # Get coordinates from geo_location column
            coords = None
            if 'geo_location' in row and pd.notna(row['geo_location']):
                coords = self.parse_geo_location(row['geo_location'])
                if coords:
                    print(f"  ✓ Using coordinates from CSV: ({coords[0]:.6f}, {coords[1]:.6f})")
            
            if coords:
                # Create filename from address (sanitized)
                filename = f"property_{idx + 1}.html"
                output_file = output_path / filename
                
                # Create the map
                self.create_map_for_property(row, coords, str(output_file))
            else:
                print(f"  ✗ Skipping property (no valid coordinates in geo_location column)")
        
        print(f"\n{'='*70}")
        print(f"✓ All maps generated in '{output_dir}/' directory")
        print(f"{'='*70}\n")
        
        # Create an index file
        self.create_index_page(output_path)
    
    def create_index_page(self, output_path: Path) -> None:
        """Create an HTML index page listing all generated maps."""
        mode_badge = """
        <div style="background: #fff3cd; border: 2px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 8px;">
            <strong>⚠️ DEMO MODE</strong><br>
            This demo uses simulated amenity data for demonstration purposes.
            In production mode with API access, real OpenStreetMap data would be used.
        </div>
        """ if self.demo_mode else ""
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Property Amenity Maps - Index</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .property-card {{
            background: white;
            margin: 15px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .property-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .property-price {{
            color: #e74c3c;
            font-size: 1.3em;
            font-weight: bold;
        }}
        .property-address {{
            color: #34495e;
            font-size: 1.1em;
            margin: 10px 0;
        }}
        .property-desc {{
            color: #7f8c8d;
            margin: 10px 0;
        }}
        .view-map-btn {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 10px;
            transition: background 0.3s;
        }}
        .view-map-btn:hover {{
            background: #2980b9;
        }}
        .info-box {{
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <h1>🏠 Property Amenity Maps</h1>
    
    {mode_badge}
    
    <div class="info-box">
        <strong>📍 Interactive Maps</strong><br>
        Each property has an interactive map showing nearby amenities within 1.5km radius.
        Use the layer controls to toggle different amenity types on/off.
    </div>
    
    <div id="properties">
"""
        
        if self.properties_df is not None:
            for idx, row in self.properties_df.iterrows():
                html_content += f"""
        <div class="property-card">
            <div class="property-price">{row['Price']}</div>
            <div class="property-address">📍 {row['Address']}</div>
            <div class="property-desc">{row['Description']}</div>
            <div>Available: {row['Available From']} | Platform: {row['Platform']}</div>
            <a href="property_{idx + 1}.html" class="view-map-btn" target="_blank">
                🗺️ View Interactive Map
            </a>
        </div>
"""
        
        html_content += """
    </div>
    
    <div style="margin-top: 30px; padding: 20px; background: white; border-radius: 8px;">
        <h3>Legend</h3>
        <ul>
            <li>🏠 <strong>Red marker:</strong> Property location</li>
            <li>🛒 <strong>Blue markers:</strong> Supermarkets</li>
            <li>🏪 <strong>Green markers:</strong> Convenience stores</li>
            <li>🥢 <strong>Dark red markers:</strong> Chinese Restaurants</li>
            <li>🍝 <strong>Red markers:</strong> Italian Restaurants</li>
            <li>� <strong>Orange markers:</strong> Indian Restaurants</li>
            <li>☕ <strong>Orange markers:</strong> Cafés</li>
            <li>🌳 <strong>Dark green markers:</strong> Parks</li>
            <li>💊 <strong>Purple markers:</strong> Pharmacies</li>
            <li>💰 <strong>Dark blue markers:</strong> Banks</li>
            <li> <strong>Gray markers:</strong> Metro Stations</li>
        </ul>
        <p><em>Use the layer control panel (top right) to show/hide specific amenity types.</em></p>
        <p><em>Use the "Hide All Layers" / "Show All Layers" buttons (bottom right) to toggle all layers at once.</em></p>
    </div>
</body>
</html>
"""
        
        index_path = output_path / "index.html"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✓ Index page created: {index_path}")
    

# 在文件末尾添加以下代码:

def main():
    """
    Main function to run the property amenity mapper.
    """
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Generate interactive maps showing properties and nearby amenities'
    )
    parser.add_argument(
        '--csv',
        type=str,
        default='fake_property_listings.csv',
        help='Path to CSV file containing property listings (default: fake_property_listings.csv)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='maps',
        help='Output directory for generated maps (default: maps)'
    )
    parser.add_argument(
        '--radius',
        type=float,
        default=1.5,
        help='Search radius in kilometers (default: 1.5)'
    )
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run in demo mode with simulated data (no API calls)'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Run in live mode using real OpenStreetMap APIs'
    )
    
    args = parser.parse_args()
    
    # Determine mode
    if args.live:
        demo_mode = False
        print("🌐 Running in LIVE MODE - will use real OpenStreetMap APIs")
        print("⚠️  This will make real API calls and respect rate limits (slower)")
    elif args.demo:
        demo_mode = True
        print("🎭 Running in DEMO MODE - using simulated data")
    else:
        # Default to demo mode if not specified
        demo_mode = True
        print("🎭 Running in DEMO MODE (default) - using simulated data")
        print("💡 Use --live flag for real OpenStreetMap data")
    
    print("\n" + "="*70)
    print("Property Amenity Mapper")
    print("="*70)
    print(f"CSV File: {args.csv}")
    print(f"Output Directory: {args.output}")
    print(f"Search Radius: {args.radius}km")
    print(f"Mode: {'DEMO' if demo_mode else 'LIVE'}")
    print("="*70 + "\n")
    
    # Check if CSV file exists
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {args.csv}")
        print(f"Please make sure the file exists in the current directory.")
        return
    
    # Create mapper instance
    mapper = PropertyAmenityMapper(
        csv_path=args.csv,
        radius_km=args.radius,
        demo_mode= False
    )
    
    # Load properties
    try:
        mapper.load_properties()
    except Exception as e:
        print(f"❌ Error loading CSV file: {e}")
        return
    
    # Process all properties
    try:
        mapper.process_all_properties(output_dir=args.output)
        
        # Success message
        print("\n" + "="*70)
        print("✅ SUCCESS!")
        print("="*70)
        print(f"All maps have been generated in the '{args.output}/' directory")
        print(f"\n📂 Open '{args.output}/index.html' in your browser to view all properties")
        print("\n💡 Tips:")
        print("  - Click on markers to see detailed information")
        print("  - Use layer controls (top right) to toggle amenity types")
        print("  - Use Hide/Show All buttons (bottom right) for quick toggling")
        print("  - Click fullscreen button (top left) for better view")
        
        if demo_mode:
            print("\n⚠️  Note: This is DEMO MODE with simulated data")
            print("   Use --live flag for real OpenStreetMap data")
        
        print("="*70 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        print("Some maps may have been generated. Check the output directory.")
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()