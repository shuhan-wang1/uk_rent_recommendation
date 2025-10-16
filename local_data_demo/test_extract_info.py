#!/usr/bin/env python3
"""
测试：从否定回复中提取关键信息
"""

import re

def test_extract_from_negative_response():
    """测试从用户的否定回复中提取必需信息"""
    
    print("=" * 80)
    print("TEST: Extract key info from negative response")
    print("=" * 80)
    
    # 测试用例 1：提取旅行时间
    print("\n[Test Case 1] Extract travel time from response")
    print("-" * 80)
    
    original_criteria = {
        'destination': 'UCL',
        'max_budget': None,
        'max_travel_time': None,
        'soft_preferences': 'student friendly'
    }
    
    user_answer = "Travel time should be within 40 min and I do not care about anything else."
    answer_lower = user_answer.lower().strip()
    
    print(f"User answer: '{user_answer}'")
    print(f"Original max_travel_time: {original_criteria.get('max_travel_time')}")
    
    # 提取旅行时间
    time_match = re.search(r'(\d+)\s*(?:min|minutes)', answer_lower)
    if time_match and not original_criteria.get('max_travel_time'):
        max_travel = int(time_match.group(1))
        original_criteria['max_travel_time'] = max_travel
        print(f"✓ Extracted travel time: {max_travel} minutes")
    
    # 提取预算
    budget_match = re.search(r'£?\s*(\d+(?:,\d{3})?)', answer_lower)
    if budget_match and not original_criteria.get('max_budget'):
        budget_str = budget_match.group(1).replace(',', '')
        max_budget = int(budget_str)
        original_criteria['max_budget'] = max_budget
        print(f"✓ Extracted budget: £{max_budget}")
    
    print(f"\nFinal criteria:")
    print(f"  destination: {original_criteria.get('destination')}")
    print(f"  max_budget: {original_criteria.get('max_budget')}")
    print(f"  max_travel_time: {original_criteria.get('max_travel_time')}")
    
    # 测试用例 2：提取预算
    print("\n[Test Case 2] Extract budget from response")
    print("-" * 80)
    
    original_criteria2 = {
        'destination': 'London',
        'max_budget': None,
        'max_travel_time': 30,
        'soft_preferences': ''
    }
    
    user_answer2 = "My budget is around £1,800 and I do not care about anything else."
    answer_lower2 = user_answer2.lower().strip()
    
    print(f"User answer: '{user_answer2}'")
    print(f"Original max_budget: {original_criteria2.get('max_budget')}")
    
    budget_match2 = re.search(r'£?\s*(\d+(?:,\d{3})?)', answer_lower2)
    if budget_match2 and not original_criteria2.get('max_budget'):
        budget_str2 = budget_match2.group(1).replace(',', '')
        max_budget2 = int(budget_str2)
        original_criteria2['max_budget'] = max_budget2
        print(f"✓ Extracted budget: £{max_budget2}")
    
    print(f"\nFinal criteria:")
    print(f"  destination: {original_criteria2.get('destination')}")
    print(f"  max_budget: {original_criteria2.get('max_budget')}")
    print(f"  max_travel_time: {original_criteria2.get('max_travel_time')}")
    
    # 测试用例 3：多个时间单位
    print("\n[Test Case 3] Handle multiple time formats")
    print("-" * 80)
    
    test_phrases = [
        ("within 45 min", 45),
        ("up to 50 minutes", 50),
        ("30min commute", 30),
        ("40 mins maximum", 40),
    ]
    
    for phrase, expected in test_phrases:
        match = re.search(r'(\d+)\s*(?:min|minutes)', phrase.lower())
        if match:
            extracted = int(match.group(1))
            status = "✓" if extracted == expected else "✗"
            print(f"  {status} '{phrase}' → {extracted} (expected: {expected})")
        else:
            print(f"  ✗ '{phrase}' → No match")
    
    # 测试用例 4：多个预算格式
    print("\n[Test Case 4] Handle multiple budget formats")
    print("-" * 80)
    
    budget_phrases = [
        ("£2000", 2000),
        ("£1,800", 1800),
        ("£2,500 maximum", 2500),
        ("budget of 1500", 1500),
    ]
    
    for phrase, expected in budget_phrases:
        match = re.search(r'£?\s*(\d+(?:,\d{3})?)', phrase.lower())
        if match:
            budget_str = match.group(1).replace(',', '')
            extracted = int(budget_str)
            status = "✓" if extracted == expected else "✗"
            print(f"  {status} '{phrase}' → £{extracted} (expected: £{expected})")
        else:
            print(f"  ✗ '{phrase}' → No match")
    
    print("\n" + "=" * 80)
    print("✅ All extraction tests completed")
    print("=" * 80)

if __name__ == '__main__':
    test_extract_from_negative_response()
