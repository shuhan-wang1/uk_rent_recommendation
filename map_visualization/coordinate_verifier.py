"""
Coordinate Verification Tool
Compare geocoding results with OSM building search and calculate accuracy
"""

import pandas as pd
import requests
import time
import math
from typing import Dict, List, Tuple, Optional
import re


class CoordinateVerifier:
    """
    Tool to verify and compare coordinates from different sources.
    """
    
    def __init__(self):
        self.building_cache = {}
    
    def parse_address(self, address: str) -> Dict[str, Optional[str]]:
        """Parse address into components."""
        parts = [p.strip() for p in address.split(',')]
        
        building_name = None
        street_address = None
        city = None
        postcode = None
        
        building_indicators = ['House', 'Court', 'Building', 'Tower', 'Apartments', 
                              'Residence', 'Hall', 'Lodge', 'Complex', 'Centre',
                              'Scape', 'Student', 'Village', 'Mews', 'Vega', 'City']
        
        for i, part in enumerate(parts):
            part_clean = part.strip()
            
            # Check for postcode (UK format)
            if self._is_uk_postcode(part_clean):
                postcode = part_clean
                continue
            
            # Check for country
            if part_clean.upper() in ['UK', 'GB', 'UNITED KINGDOM']:
                continue
            
            # Check for building name
            if building_name is None and any(ind in part_clean for ind in building_indicators):
                if not any(c.isdigit() for c in part_clean):
                    building_name = part_clean
                    continue
            
            # Check for street address (has numbers)
            if street_address is None and any(c.isdigit() for c in part_clean):
                street_address = part_clean
                continue
            
            # Remaining is likely city
            if city is None and not any(c.isdigit() for c in part_clean):
                city = part_clean
        
        return {
            'building_name': building_name,
            'street_address': street_address,
            'city': city,
            'postcode': postcode
        }
    
    def _is_uk_postcode(self, text: str) -> bool:
        """Check if text matches UK postcode pattern."""
        pattern = r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$'
        return bool(re.match(pattern, text.strip().upper()))
    
    def search_osm_building(self, building_name: str, city: Optional[str] = None) -> Optional[Dict]:
        """Search for building in OSM by name."""
        cache_key = f"{building_name}_{city}"
        if cache_key in self.building_cache:
            return self.building_cache[cache_key]
        
        area_filter = ""
        if city:
            area_filter = f'area["name"="{city}"]->.searchArea;'
        
        query = f"""
        [out:json][timeout:25];
        {area_filter}
        (
          way["building"]["name"~"{building_name}",i]{f'(area.searchArea)' if area_filter else ''};
          relation["building"]["name"~"{building_name}",i]{f'(area.searchArea)' if area_filter else ''};
          node["amenity"]["name"~"{building_name}",i]{f'(area.searchArea)' if area_filter else ''};
          way["amenity"]["name"~"{building_name}",i]{f'(area.searchArea)' if area_filter else ''};
        );
        out center;
        """
        
        try:
            response = requests.post(
                'https://overpass-api.de/api/interpreter',
                data=query,
                timeout=30
            )
            time.sleep(1.5)  # Rate limiting
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('elements'):
                    element = data['elements'][0]
                    
                    if element['type'] == 'node':
                        lat = element['lat']
                        lon = element['lon']
                    elif 'center' in element:
                        lat = element['center']['lat']
                        lon = element['center']['lon']
                    else:
                        return None
                    
                    result = {
                        'lat': lat,
                        'lon': lon,
                        'name': element.get('tags', {}).get('name', building_name),
                        'type': element.get('tags', {}).get('building', 'building'),
                        'osm_id': element['id']
                    }
                    
                    self.building_cache[cache_key] = result
                    return result
                    
        except Exception as e:
            print(f"   Error: {e}")
        
        return None
    
    def geocode_nominatim(self, address: str) -> Optional[Dict]:
        """Traditional geocoding using Nominatim."""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            headers = {'User-Agent': 'CoordinateVerifier/1.0'}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            time.sleep(1)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    return {
                        'lat': float(result['lat']),
                        'lon': float(result['lon']),
                        'display_name': result.get('display_name', ''),
                        'type': result.get('type', ''),
                        'importance': result.get('importance', 0)
                    }
        except Exception as e:
            print(f"   Nominatim error: {e}")
        
        return None
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> Dict:
        """Calculate distance between two points."""
        R = 6371  # Earth's radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        distance_km = R * c
        distance_miles = distance_km * 0.621371
        
        return {
            'km': distance_km,
            'miles': distance_miles,
            'meters': distance_km * 1000
        }
    
    def verify_address(self, address: str) -> Dict:
        """
        Verify an address using multiple methods and compare results.
        """
        print(f"\n{'='*80}")
        print(f"VERIFYING: {address}")
        print(f"{'='*80}")
        
        # Parse address
        components = self.parse_address(address)
        print(f"\n📍 Address Components:")
        for key, value in components.items():
            print(f"   {key}: {value}")
        
        results = {}
        
        # Method 1: OSM Building Search
        if components['building_name']:
            print(f"\n🔍 Method 1: OSM Building Search")
            print(f"   Searching for: {components['building_name']}")
            osm_result = self.search_osm_building(
                components['building_name'], 
                components['city']
            )
            
            if osm_result:
                print(f"   ✅ FOUND in OSM!")
                print(f"      Coordinates: ({osm_result['lat']:.6f}, {osm_result['lon']:.6f})")
                print(f"      OSM ID: {osm_result['osm_id']}")
                print(f"      Type: {osm_result['type']}")
                results['osm_building'] = osm_result
            else:
                print(f"   ❌ NOT FOUND in OSM")
                results['osm_building'] = None
        
        # Method 2: Traditional Geocoding
        print(f"\n🔍 Method 2: Traditional Geocoding (Nominatim)")
        geocode_result = self.geocode_nominatim(address)
        
        if geocode_result:
            print(f"   ✅ Geocoded")
            print(f"      Coordinates: ({geocode_result['lat']:.6f}, {geocode_result['lon']:.6f})")
            print(f"      Type: {geocode_result['type']}")
            print(f"      Display: {geocode_result['display_name'][:80]}...")
            results['geocoding'] = geocode_result
        else:
            print(f"   ❌ Geocoding FAILED")
            results['geocoding'] = None
        
        # Compare results
        print(f"\n📊 COMPARISON:")
        if results.get('osm_building') and results.get('geocoding'):
            distance = self.calculate_distance(
                results['osm_building']['lat'],
                results['osm_building']['lon'],
                results['geocoding']['lat'],
                results['geocoding']['lon']
            )
            
            print(f"   Distance between methods:")
            print(f"      {distance['km']:.3f} km ({distance['miles']:.3f} miles)")
            print(f"      {distance['meters']:.1f} meters")
            
            if distance['miles'] < 0.05:
                print(f"   ✅ EXCELLENT accuracy (<0.05 miles)")
            elif distance['miles'] < 0.2:
                print(f"   ⚠️  GOOD accuracy ({distance['miles']:.2f} miles)")
            else:
                print(f"   ❌ POOR accuracy ({distance['miles']:.2f} miles)")
                print(f"   💡 Recommend using OSM building coordinates")
            
            results['distance'] = distance
        
        # Recommendation
        print(f"\n💡 RECOMMENDATION:")
        if results.get('osm_building'):
            print(f"   ✅ Use OSM building search result (highest accuracy)")
            print(f"   📍 Coordinates: ({results['osm_building']['lat']:.6f}, {results['osm_building']['lon']:.6f})")
            results['recommended'] = results['osm_building']
        elif results.get('geocoding'):
            print(f"   ⚠️  Use geocoding result (OSM building not found)")
            print(f"   📍 Coordinates: ({results['geocoding']['lat']:.6f}, {results['geocoding']['lon']:.6f})")
            results['recommended'] = results['geocoding']
        else:
            print(f"   ❌ No coordinates found")
            results['recommended'] = None
        
        return results
    
    def verify_csv(self, csv_path: str) -> pd.DataFrame:
        """
        Verify all addresses in a CSV file.
        """
        print(f"\n{'#'*80}")
        print(f"VERIFYING CSV FILE: {csv_path}")
        print(f"{'#'*80}\n")
        
        df = pd.read_csv(csv_path)
        print(f"Found {len(df)} properties\n")
        
        results_list = []
        
        for idx, row in df.iterrows():
            address = row['Address']
            
            print(f"\n{'='*80}")
            print(f"PROPERTY {idx + 1}/{len(df)}")
            print(f"{'='*80}")
            
            result = self.verify_address(address)
            
            # Store results
            result_row = {
                'Property': idx + 1,
                'Address': address,
                'OSM_Found': result.get('osm_building') is not None,
                'Geocoded': result.get('geocoding') is not None,
            }
            
            if result.get('osm_building'):
                result_row['OSM_Lat'] = result['osm_building']['lat']
                result_row['OSM_Lon'] = result['osm_building']['lon']
            
            if result.get('geocoding'):
                result_row['Geocode_Lat'] = result['geocoding']['lat']
                result_row['Geocode_Lon'] = result['geocoding']['lon']
            
            if result.get('distance'):
                result_row['Error_Miles'] = result['distance']['miles']
                result_row['Error_Meters'] = result['distance']['meters']
            
            if result.get('recommended'):
                result_row['Recommended_Lat'] = result['recommended']['lat']
                result_row['Recommended_Lon'] = result['recommended']['lon']
            
            results_list.append(result_row)
            
            # Rate limiting
            time.sleep(2)
        
        results_df = pd.DataFrame(results_list)
        
        # Print summary
        print(f"\n{'#'*80}")
        print(f"VERIFICATION SUMMARY")
        print(f"{'#'*80}\n")
        
        print(results_df.to_string())
        
        # Save results
        output_path = 'coordinate_verification_results.csv'
        results_df.to_csv(output_path, index=False)
        print(f"\n✅ Results saved to: {output_path}")
        
        return results_df


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Verify coordinates using OSM building search vs traditional geocoding'
    )
    parser.add_argument('--csv', type=str, required=True,
                       help='Path to CSV file with addresses')
    parser.add_argument('--address', type=str,
                       help='Verify a single address')
    
    args = parser.parse_args()
    
    verifier = CoordinateVerifier()
    
    if args.address:
        # Verify single address
        verifier.verify_address(args.address)
    elif args.csv:
        # Verify CSV file
        verifier.verify_csv(args.csv)


if __name__ == "__main__":
    main()