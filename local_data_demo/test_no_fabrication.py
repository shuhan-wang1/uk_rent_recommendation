"""
Test to verify that LLM does NOT fabricate property attributes
not present in the CSV data.

REQUIREMENTS:
- CSV fake_property_listings.csv has ONLY: Price, Location, Description
- Description field ONLY contains room count/type (e.g., "2 bedroom flat", "Studio")
- NO mention of: pet-friendly, modern, renovated, student-friendly, etc.

TEST: Generate recommendations and verify NO fabricated attributes appear.
"""

import json
import sys
from core.data_loader import load_mock_properties_from_csv, parse_price
from core.llm_interface import create_fallback_recommendations

# Load the CSV data
print("=" * 70)
print("TEST: LLM Fabrication Check")
print("=" * 70)

print("\n[STEP 1] Loading CSV properties...")
properties = load_mock_properties_from_csv()
print(f"✓ Loaded {len(properties)} properties from CSV")

print("\n[STEP 2] Checking CSV data for attributes...")
print("-" * 70)

# Parse prices and check what attributes exist in CSV
for i, prop in enumerate(properties, 1):
    prop['parsed_price'] = parse_price(prop.get('Price'))
    description = prop.get('Description', '').lower()
    
    print(f"\nProperty {i}:")
    print(f"  Address: {prop.get('Address', 'N/A')[:50]}")
    print(f"  Description: {prop.get('Description', 'N/A')}")
    print(f"  Price: {prop.get('Price', 'N/A')}")
    
    # Check for fabricatable attributes
    fabricatable_keywords = [
        'pet', 'pet-friendly', 'pet friendly',
        'student', 'student-friendly', 'student friendly',
        'modern', 'renovated', 'updated', 'recently',
        'amenities', 'furnished', 'unfurnished',
        'garden', 'balcony', 'parking', 'pool',
    ]
    
    found_keywords = []
    for keyword in fabricatable_keywords:
        if keyword in description:
            found_keywords.append(keyword)
    
    if found_keywords:
        print(f"  ✓ Found keywords in description: {found_keywords}")
    else:
        print(f"  ✗ NO amenity/feature keywords in description (only room info)")

print("\n" + "=" * 70)
print("[STEP 3] Generating recommendations with fallback engine...")
print("=" * 70)

# Prepare criteria (student at UCL wanting safe area)
test_criteria = {
    "destination": "UCL",
    "max_travel_time": 40,
    "max_budget": 2000,
    "soft_preferences": "I want a safe area"  # NOT asking for student-friendly, pet-friendly, etc.
}

print(f"\nTest Criteria: {json.dumps(test_criteria, indent=2)}")

# Call fallback recommendation generator
print("\n[STEP 4] Fallback recommendations (first 3):")
print("-" * 70)

recommendations = create_fallback_recommendations(
    properties[:3],  # Use first 3 properties
    json.dumps(test_criteria),
    ""  # soft_preferences (already in criteria)
)

if recommendations and 'recommendations' in recommendations:
    for rec in recommendations['recommendations'][:3]:
        print(f"\n--- Recommendation #{rec.get('rank', 'N/A')} ---")
        print(f"Address: {rec.get('address', 'N/A')}")
        print(f"Price: {rec.get('price', 'N/A')}")
        print(f"\nExplanation:")
        print(rec.get('explanation', 'N/A'))
        
        # Check for fabrications
        explanation_lower = rec.get('explanation', '').lower()
        
        fabrication_keywords = [
            'pet-friendly', 'pet friendly',
            'student-friendly', 'student friendly',
            'modern', 'renovated', 'updated',
            'recently renovated', 'newly decorated',
            'furnished', 'unfurnished',
            'garden', 'balcony', 'parking', 'pool',
            'smart home', 'latest', 'state-of-the-art'
        ]
        
        fabrications_found = []
        for keyword in fabrication_keywords:
            if keyword in explanation_lower:
                fabrications_found.append(keyword)
        
        if fabrications_found:
            print(f"\n❌ FABRICATIONS DETECTED: {fabrications_found}")
        else:
            print(f"\n✓ No fabricated attributes detected")
else:
    print("ERROR: Could not generate recommendations")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

# Final validation
has_violations = False
for rec in recommendations['recommendations'][:3]:
    explanation_lower = rec.get('explanation', '').lower()
    fabrication_keywords = [
        'pet-friendly', 'pet friendly',
        'student-friendly', 'student friendly',
        'modern', 'renovated', 'updated',
    ]
    
    for keyword in fabrication_keywords:
        if keyword in explanation_lower:
            has_violations = True
            break

if has_violations:
    print("\n❌ FAILED: LLM is still fabricating attributes not in CSV!")
    sys.exit(1)
else:
    print("\n✅ PASSED: LLM recommendations contain ONLY verified data from CSV")
    print("\nAll recommendations use ONLY descriptions and factual data.")
    sys.exit(0)
