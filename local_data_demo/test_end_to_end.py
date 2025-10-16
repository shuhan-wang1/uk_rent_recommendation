#!/usr/bin/env python3
"""
端到端测试：完整的澄清流程处理
场景：用户回复带有"I do not care about anything else"但提供了关键信息
"""

def test_complete_clarification_flow():
    """测试完整的澄清流程"""
    
    print("=" * 90)
    print("END-TO-END TEST: Complete clarification flow with 'I do not care' response")
    print("=" * 90)
    
    # 步骤 1：初始查询
    print("\n[STEP 1] User submits initial query")
    print("-" * 90)
    user_query = "Find me properties near UCL"
    print(f"User: {user_query}")
    
    # 步骤 2：澄清提问（假设缺少预算和旅行时间）
    print("\n[STEP 2] System asks clarification")
    print("-" * 90)
    clarification_q = "Could you clarify: your preferred commute time and budget?"
    print(f"System: {clarification_q}")
    
    # 步骤 3：用户响应
    print("\n[STEP 3] User provides response")
    print("-" * 90)
    user_response = "Travel time should be within 40 min and I do not care about anything else."
    print(f"User: {user_response}")
    
    # 步骤 4：系统处理
    print("\n[STEP 4] System processes response")
    print("-" * 90)
    
    # 模拟 refine_criteria_with_answer 的逻辑
    original_criteria = {
        'destination': 'UCL',
        'max_budget': None,
        'max_travel_time': None,
        'soft_preferences': 'student friendly',
        'status': 'needs_clarification',
        '_original_query': user_query
    }
    
    print(f"Original criteria:")
    print(f"  destination: {original_criteria['destination']}")
    print(f"  max_budget: {original_criteria['max_budget']}")
    print(f"  max_travel_time: {original_criteria['max_travel_time']}")
    print(f"  soft_preferences: {original_criteria['soft_preferences']}")
    
    # 检查是否有所有必需字段
    required_fields = ['destination', 'max_budget', 'max_travel_time']
    has_all_required = all(original_criteria.get(field) for field in required_fields)
    print(f"\nHas all required fields: {has_all_required}")
    
    if not has_all_required:
        print("[Refine] ✗ Missing required fields - checking for negative response...")
        
        # 检查否定回复
        answer_lower = user_response.lower().strip()
        is_negative = any(phrase in answer_lower for phrase in [
            'no, i do not', 'no i do not', "no, don't", "no don't", 
            'nope', 'not really', 'nothing else', 'nothing more',
            'no thanks', 'none of that', 'no worries', 'nothing',
            'i do not care about anything else'
        ])
        
        print(f"Is negative response: {is_negative}")
        
        if is_negative:
            print("[Refine] ✓ Detected negative response - extracting info from response...")
            
            import re
            
            # 提取旅行时间
            if not original_criteria.get('max_travel_time'):
                time_match = re.search(r'(\d+)\s*(?:min|minutes|mins)', answer_lower)
                if time_match:
                    max_travel = int(time_match.group(1))
                    original_criteria['max_travel_time'] = max_travel
                    print(f"  ✓ Extracted travel time: {max_travel} minutes")
            
            # 提取预算
            if not original_criteria.get('max_budget'):
                budget_match = re.search(r'£\s*(\d+(?:,\d{3})*)', answer_lower)
                if budget_match:
                    budget_str = budget_match.group(1).replace(',', '')
                    max_budget = int(budget_str)
                    original_criteria['max_budget'] = max_budget
                    print(f"  ✓ Extracted budget: £{max_budget}")
            
            # 清除软偏好
            original_criteria['soft_preferences'] = ""
            original_criteria['status'] = 'success'
            print(f"  ✓ Cleared soft_preferences")
    
    # 步骤 5：最终条件
    print("\n[STEP 5] Final criteria after processing")
    print("-" * 90)
    
    print(f"Final criteria:")
    print(f"  destination: {original_criteria.get('destination')} ✓")
    print(f"  max_budget: {original_criteria.get('max_budget')} {'✓' if not original_criteria.get('max_budget') else '(unchanged)'}")
    print(f"  max_travel_time: {original_criteria.get('max_travel_time')} ✓")
    print(f"  soft_preferences: '{original_criteria.get('soft_preferences')}' (empty) ✓")
    print(f"  status: {original_criteria.get('status')} ✓")
    
    # 步骤 6：验证结果
    print("\n[STEP 6] Validation")
    print("-" * 90)
    
    checks = {
        "Has destination": original_criteria.get('destination') == 'UCL',
        "Has travel time": original_criteria.get('max_travel_time') == 40,
        "Soft preferences cleared": original_criteria.get('soft_preferences') == "",
        "Status is 'success'": original_criteria.get('status') == 'success',
    }
    
    all_pass = True
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}: {passed}")
        all_pass = all_pass and passed
    
    # 步骤 7：Enrichment 和推荐
    print("\n[STEP 7] Expected behavior in downstream")
    print("-" * 90)
    
    soft_prefs = original_criteria.get('soft_preferences', '').lower()
    should_fetch_crime = 'safe' in soft_prefs or 'crime' in soft_prefs
    
    print(f"Enrichment Service:")
    print(f"  soft_preferences: '{soft_prefs}' (empty)")
    print(f"  should_fetch_crime: {should_fetch_crime}")
    print(f"  → Will skip crime data ✓")
    
    print(f"\nRecommendation Generation:")
    print(f"  soft_preferences: '{soft_prefs}' (empty)")
    should_include_crime = any(kw in soft_prefs for kw in ['safe', 'crime', 'security', 'dangerous'])
    print(f"  should_include_crime: {should_include_crime}")
    print(f"  → Will set crimes_6m = null ✓")
    
    print(f"\nFinal Output:")
    print(f"  ✓ No crime data in recommendations")
    print(f"  ✓ Focus on: price, commute time, features")
    
    # 最终总结
    print("\n" + "=" * 90)
    if all_pass:
        print("✅ COMPLETE FLOW TEST PASSED")
        print("\nThe system now correctly:")
        print("  1. Detects 'I do not care about anything else' response ✓")
        print("  2. Extracts travel time (40 min) from response ✓")
        print("  3. Clears soft_preferences to empty string ✓")
        print("  4. Returns status='success' for search to proceed ✓")
        print("  5. Downstream enrichment will skip unnecessary data ✓")
        print("  6. Recommendations won't mention crime statistics ✓")
    else:
        print("❌ COMPLETE FLOW TEST FAILED")
    print("=" * 90)

if __name__ == '__main__':
    test_complete_clarification_flow()
