#!/usr/bin/env python3
"""
测试：处理澄清回复中"I do not care about anything else"的情况
"""

def test_refine_with_negative_response():
    """测试缺少字段但有否定回复的情况"""
    
    print("=" * 80)
    print("TEST: Handle 'I do not care about anything else' response")
    print("=" * 80)
    
    # 模拟缺少某些字段的原始条件
    original_criteria = {
        'destination': 'UCL',
        'max_budget': None,  # 缺少预算
        'max_travel_time': None,  # 缺少旅行时间
        'soft_preferences': 'student friendly',
        'status': 'needs_clarification',
        'clarification_question': "Could you clarify: your preferred commute time and budget?",
        '_original_query': 'Find me properties near UCL, student friendly'
    }
    
    user_answer = "Travel time should be within 40 min and I do not care about anything else."
    
    print(f"\n[Test Setup]")
    print(f"Original criteria has all required: False")
    print(f"  destination: {original_criteria.get('destination')}")
    print(f"  max_budget: {original_criteria.get('max_budget')}")
    print(f"  max_travel_time: {original_criteria.get('max_travel_time')}")
    print(f"\nUser answer: {user_answer}")
    
    # 检查否定逻辑
    answer_lower = user_answer.lower().strip()
    phrases_to_check = [
        'no, i do not', 'no i do not', "no, don't", "no don't", 
        'nope', 'not really', 'nothing else', 'nothing more',
        'no thanks', 'none of that', 'no worries', 'nothing',
        'i do not care about anything else'
    ]
    
    print(f"\n[Negative Response Check]")
    found_negative = False
    for phrase in phrases_to_check:
        if phrase in answer_lower:
            print(f"  ✓ Matched: '{phrase}'")
            found_negative = True
            break
    
    if found_negative:
        print(f"  → is_negative = True")
        print(f"  → Will clear soft_preferences and use existing fields")
        print(f"  → Final status: 'success'")
    else:
        print(f"  → is_negative = False")
        print(f"  → Will attempt to re-parse")
    
    # 检查旅行时间提取
    print(f"\n[Travel Time Extraction]")
    import re
    time_patterns = [
        r'(\d+)\s*min',
        r'(\d+)\s*minutes',
        r'within\s*(\d+)',
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, answer_lower)
        if match:
            travel_time = int(match.group(1))
            print(f"  ✓ Found: {travel_time} minutes (pattern: {pattern})")
            break
    
    print(f"\n[Expected Result]")
    if found_negative:
        print(f"✅ Should return:")
        print(f"   destination: 'UCL' (kept)")
        print(f"   max_budget: None (kept)")
        print(f"   max_travel_time: None (kept)")
        print(f"   soft_preferences: '' (cleared)")
        print(f"   status: 'success'")
    else:
        print(f"❌ Would attempt re-parse with combined query")
    
    # 测试负面情况
    print(f"\n[Test Alternative Phrases]")
    test_phrases = [
        "No, I do not have any other concerns",
        "I do not care about anything else",
        "Nothing else matters",
        "That's all, nothing more",
    ]
    
    for phrase in test_phrases:
        matches = any(p in phrase.lower() for p in phrases_to_check)
        status = "✓" if matches else "✗"
        print(f"  {status} '{phrase}'")

if __name__ == '__main__':
    test_refine_with_negative_response()
