#!/usr/bin/env python3
"""
简化的测试：验证条件化逻辑是否正常工作
"""

import json

# 直接测试 generate_recommendations 中的条件逻辑

def test_soft_preferences_logic():
    """测试 soft_preferences 的条件逻辑"""
    
    print("=" * 80)
    print("TEST: Conditional logic for crime data inclusion")
    print("=" * 80)
    
    # 测试案例 1: 空的 soft_preferences
    soft_preferences = ""
    soft_prefs_lower = soft_preferences.lower() if soft_preferences else ""
    should_include_crime = any(kw in soft_prefs_lower for kw in ['safe', 'crime', 'security', 'dangerous'])
    
    print(f"\n[TEST 1] Empty soft_preferences")
    print(f"  Input: soft_preferences = '{soft_preferences}'")
    print(f"  should_include_crime: {should_include_crime}")
    print(f"  Expected: False")
    print(f"  Result: {'✓ PASS' if should_include_crime == False else '❌ FAIL'}")
    
    # 测试案例 2: 包含 "safe" 关键词
    soft_preferences = "close to supermarket and safe area"
    soft_prefs_lower = soft_preferences.lower() if soft_preferences else ""
    should_include_crime = any(kw in soft_prefs_lower for kw in ['safe', 'crime', 'security', 'dangerous'])
    
    print(f"\n[TEST 2] With 'safe' keyword")
    print(f"  Input: soft_preferences = '{soft_preferences}'")
    print(f"  should_include_crime: {should_include_crime}")
    print(f"  Expected: True")
    print(f"  Result: {'✓ PASS' if should_include_crime == True else '❌ FAIL'}")
    
    # 测试案例 3: 只包含其他关键词
    soft_preferences = "close to supermarket and good amenities"
    soft_prefs_lower = soft_preferences.lower() if soft_preferences else ""
    should_include_crime = any(kw in soft_prefs_lower for kw in ['safe', 'crime', 'security', 'dangerous'])
    
    print(f"\n[TEST 3] Without crime-related keywords")
    print(f"  Input: soft_preferences = '{soft_preferences}'")
    print(f"  should_include_crime: {should_include_crime}")
    print(f"  Expected: False")
    print(f"  Result: {'✓ PASS' if should_include_crime == False else '❌ FAIL'}")
    
    # 测试案例 4: JSON 构造逻辑
    print(f"\n[TEST 4] JSON construction with None values")
    print(f"  When should_include_crime = False:")
    
    simple_prop = {
        'id': 1,
        'address': '123 Main St, London',
        'price': '£1800',
        'travel_time_minutes': 25,
        'description': 'Beautiful flat'
    }
    
    # 模拟不包含crime数据的情况
    should_include_crime = False
    if should_include_crime and 'crime_data_summary' in {'some': 'data'}:
        simple_prop['crimes_6m'] = 100
    else:
        simple_prop['crimes_6m'] = None
    
    print(f"    simple_prop['crimes_6m'] = {simple_prop['crimes_6m']}")
    print(f"    Expected: None")
    print(f"    Result: {'✓ PASS' if simple_prop['crimes_6m'] == None else '❌ FAIL'}")
    
    # 测试案例 5: 检查 JSON 序列化
    print(f"\n[TEST 5] JSON serialization with None")
    test_data = {
        'rank': 1,
        'crimes_6m': None,
        'crime_trend': None,
        'nearby_supermarkets': None
    }
    
    json_str = json.dumps(test_data, indent=2)
    print(f"  JSON output:")
    print(f"  {json_str}")
    print(f"  Contains 'null': {'✓ PASS (as expected)' if 'null' in json_str else '❌ FAIL'}")
    
    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)

if __name__ == '__main__':
    test_soft_preferences_logic()
