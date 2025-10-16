#!/usr/bin/env python3
"""
测试 LLM 对 null 值字段的处理
"""

import json
from core.llm_interface import call_ollama

def test_llm_null_field_handling():
    """测试 LLM 是否会忽略 null 字段"""
    
    print("=" * 80)
    print("TEST: Does LLM respect null fields in property data?")
    print("=" * 80)
    
    # 构造测试数据，包含 crimes_6m = null
    test_properties = [
        {
            'id': 1,
            'address': '123 King Street, Bloomsbury, London WC1B 3NG',
            'price': '£1,900',
            'price_numeric': 1900,
            'travel_time_minutes': 22,
            'description': 'Spacious 2-bed flat with modern kitchen',
            'crimes_6m': None,  # 明确设置为 null
            'crime_trend': None,
            'top_crime_types': [],
            'nearby_supermarkets': None,  # 明确设置为 null
            'nearby_parks': None,
            'nearby_gyms': None
        },
        {
            'id': 2,
            'address': '456 Russell Square, Bloomsbury, London WC1B 4HS',
            'price': '£2,050',
            'price_numeric': 2050,
            'travel_time_minutes': 28,
            'description': 'Cozy studio with balcony near British Museum',
            'crimes_6m': None,  # 明确设置为 null
            'crime_trend': None,
            'top_crime_types': [],
            'nearby_supermarkets': None,
            'nearby_parks': None,
            'nearby_gyms': None
        }
    ]
    
    system_prompt = """You are Alex, a friendly rental assistant. 
CRITICAL: If crimes_6m is null, DO NOT mention any crime/safety statistics.
If nearby_supermarkets is null, DO NOT mention amenities.
Only mention data fields that are NOT null."""

    user_query = "Find me student-friendly properties near UCL"
    soft_preferences = ""  # 空 = 没有特殊关注
    
    prompt = f"""User is looking for: {user_query}
User's priorities: good value and convenience
User did NOT ask about: crime/safety statistics, nearby amenities. DO NOT mention these in your explanations.

Property data:
{json.dumps(test_properties, indent=2)}

Write a brief recommendation for the top property that:
1. Does NOT mention any crime/safety data (crimes_6m is null)
2. Does NOT mention nearby amenities (nearby_supermarkets is null)
3. Only discusses: commute time, price, description

Keep it to 2-3 sentences."""

    print(f"\nUser Query: {user_query}")
    print(f"Soft Preferences: '{soft_preferences}' (EMPTY)")
    print(f"\nProperty data crimes_6m values: {[p.get('crimes_6m') for p in test_properties]}")
    print(f"Property data nearby_supermarkets values: {[p.get('nearby_supermarkets') for p in test_properties]}")
    
    print(f"\n📝 Sending prompt to LLM...")
    print(f"System prompt instructs: DO NOT mention crime if null, DO NOT mention amenities if null")
    
    response = call_ollama(prompt, system_prompt, timeout=60)
    
    print(f"\n🤖 LLM Response:")
    print("-" * 80)
    print(response)
    print("-" * 80)
    
    # 检查响应中是否包含不应该出现的内容
    crime_keywords = ['crime', 'safe', 'security', 'dangerous', 'incident', 'reported']
    amenity_keywords = ['supermarket', 'park', 'gym', 'shopping', 'restaurant']
    
    found_crime = any(kw in response.lower() for kw in crime_keywords)
    found_amenity = any(kw in response.lower() for kw in amenity_keywords)
    
    print(f"\n📊 Validation Results:")
    print(f"  Contains crime mentions: {found_crime} (Expected: False)")
    print(f"  Contains amenity mentions: {found_amenity} (Expected: False)")
    
    if not found_crime and not found_amenity:
        print(f"\n✅ SUCCESS: LLM correctly ignored null fields!")
    else:
        if found_crime:
            print(f"\n❌ ERROR: LLM mentioned crime despite crimes_6m being null")
        if found_amenity:
            print(f"\n❌ ERROR: LLM mentioned amenities despite nearby_supermarkets being null")

if __name__ == '__main__':
    test_llm_null_field_handling()
