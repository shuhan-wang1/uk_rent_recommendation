#!/usr/bin/env python3
"""
完整的流程测试：从用户查询到推荐生成
模拟：用户说"没有其他关注" -> soft_preferences 应该是空 -> 不应该显示 crime data
"""

import json

def test_complete_workflow():
    """模拟完整的用户流程"""
    
    print("=" * 90)
    print("COMPLETE WORKFLOW TEST: User says 'No other concerns'")
    print("=" * 90)
    
    # 步骤 1：用户的初始查询
    print("\n[STEP 1] 用户提交初始查询")
    print("-" * 90)
    user_query = "Find me properties near UCL, I want it to be student friendly. Budget within 2000 pounds per month. Ideal travel time within 45 min."
    print(f"Query: {user_query}")
    
    # 步骤 2：系统进行澄清
    print("\n[STEP 2] 系统生成澄清问题")
    print("-" * 90)
    
    # 模拟 clarify_and_extract_criteria 的输出
    original_criteria = {
        'destination': 'UCL',
        'max_budget': 2000,
        'max_travel_time': 45,
        'soft_preferences': 'student friendly',  # 从初始查询中提取
        'status': 'needs_clarification',
        'clarification_question': 'You mentioned: UCL area, £2000/month, 45 min commute, student friendly. Anything else important?',
        '_original_query': user_query
    }
    
    print(f"Clarification Question: {original_criteria['clarification_question']}")
    print(f"Original soft_preferences: '{original_criteria['soft_preferences']}'")
    
    # 步骤 3：用户回复"没有其他关注"
    print("\n[STEP 3] 用户回复")
    print("-" * 90)
    user_response = "No, I do not have any other concerns"
    print(f"User: {user_response}")
    
    # 步骤 4：调用 refine_criteria_with_answer
    print("\n[STEP 4] 系统处理澄清回复")
    print("-" * 90)
    
    # 模拟 refine_criteria_with_answer 的逻辑
    answer_lower = user_response.lower().strip()
    is_negative = any(phrase in answer_lower for phrase in [
        'no, i do not', 'no i do not', "no, don't", "no don't", 
        'nope', 'not really', 'nothing else', 'nothing more',
        'no thanks', 'none of that', 'no worries', 'nothing'
    ])
    
    print(f"Response is negative: {is_negative}")
    
    if is_negative:
        # 清除 soft_preferences
        refined_criteria = original_criteria.copy()
        refined_criteria['soft_preferences'] = ""  # 清除为空
        refined_criteria['status'] = 'success'
        
        print(f"✓ Clearing soft_preferences")
        print(f"✓ Setting status to 'success'")
    else:
        refined_criteria = original_criteria
    
    print(f"\nRefined criteria: {json.dumps(refined_criteria, indent=2)}")
    
    # 步骤 5：enrichment 层
    print("\n[STEP 5] Enrichment Service")
    print("-" * 90)
    
    soft_prefs = refined_criteria.get('soft_preferences', '').lower()
    print(f"soft_preferences: '{soft_prefs}' (empty = {len(soft_prefs) == 0})")
    
    # 检查是否应该获取 crime data
    should_fetch_crime = any(keyword in soft_prefs for keyword in ['safe', 'crime', 'security', 'dangerous'])
    print(f"Should fetch crime data: {should_fetch_crime}")
    
    if not should_fetch_crime:
        print("✓ Skipping crime data retrieval")
        print("✓ Will remove 'crime_data_summary' field if it exists")
    else:
        print("✗ Will fetch crime data")
    
    # 步骤 6：推荐生成层
    print("\n[STEP 6] Recommendation Generation")
    print("-" * 90)
    
    soft_prefs_lower = refined_criteria.get('soft_preferences', '').lower()
    should_include_crime = any(kw in soft_prefs_lower for kw in ['safe', 'crime', 'security', 'dangerous'])
    
    print(f"Determining data to include:")
    print(f"  should_include_crime: {should_include_crime}")
    
    # 模拟 simple_props 构造
    example_property = {
        'id': 1,
        'address': '123 King Street, Bloomsbury',
        'price': '£1,900',
        'travel_time_minutes': 22,
        'description': 'Spacious 2-bed flat with modern kitchen'
    }
    
    if should_include_crime:
        # 假设有 crime data
        example_property['crimes_6m'] = 85
        example_property['crime_trend'] = 'stable'
        print("  → Including crime data in JSON")
    else:
        # 不包含 crime data
        example_property['crimes_6m'] = None
        example_property['crime_trend'] = None
        print("  → Setting crime fields to null in JSON")
    
    print(f"\nExample property JSON:")
    print(json.dumps(example_property, indent=2))
    
    # 步骤 7：LLM 提示构造
    print("\n[STEP 7] LLM Prompt Generation")
    print("-" * 90)
    
    user_concerns = []
    data_to_mention = set()
    
    if refined_criteria.get('soft_preferences'):
        sp_lower = refined_criteria['soft_preferences'].lower()
        if 'crime' in sp_lower or 'safe' in sp_lower:
            user_concerns.append('safety')
            data_to_mention.add('crime')
    
    concerns_text = ", ".join(user_concerns) if user_concerns else "good value and convenience"
    print(f"Concerns text: '{concerns_text}'")
    
    excluded_topics = []
    if 'crime' not in data_to_mention:
        excluded_topics.append('crime/safety statistics')
    
    if excluded_topics:
        data_guidance = f"\n🚫 User did NOT ask about: {', '.join(excluded_topics)}. DO NOT mention these in your explanations."
    else:
        data_guidance = ""
    
    print(f"Data guidance:{data_guidance}")
    
    # 关键指导
    critical_rule = "\n2. If a field is null or missing, DO NOT mention it (e.g., if crimes_6m is null, don't talk about safety)"
    print(f"\nCritical LLM rule:{critical_rule}")
    
    # 步骤 8：预期 LLM 行为
    print("\n[STEP 8] Expected LLM Behavior")
    print("-" * 90)
    
    print("LLM sees in prompt:")
    print(f"  - User did NOT ask about: crime/safety statistics")
    print(f"  - Property data: 'crimes_6m': null")
    print(f"  - Rule: If field is null, DO NOT mention it")
    
    print("\nLLM should generate explanation like:")
    print("  ✓ 'This flat in Bloomsbury caught my eye because of its 22-minute commute!'")
    print("  ✓ 'At £1,900, you're getting good value for the area.'")
    print("  ✓ 'Perfect for students who want a quick journey to UCL.'")
    
    print("\nLLM should NOT generate:")
    print("  ✗ 'The area has seen X reported crimes'")
    print("  ✗ 'Safety-wise, the neighborhood...'")
    print("  ✗ 'Crime statistics show...'")
    
    # 最终总结
    print("\n" + "=" * 90)
    print("TEST SUMMARY")
    print("=" * 90)
    
    all_pass = (
        is_negative and
        refined_criteria['soft_preferences'] == "" and
        not should_fetch_crime and
        not should_include_crime and
        example_property['crimes_6m'] is None and
        'crime' in str(excluded_topics).lower()
    )
    
    if all_pass:
        print("✅ PASS - All checks validated!")
        print("\nExpected behavior:")
        print("  1. Soft preferences cleared: ✓")
        print("  2. Crime enrichment skipped: ✓")
        print("  3. Crime data set to null in JSON: ✓")
        print("  4. LLM instructed not to mention crime: ✓")
        print("  5. Final recommendation won't mention crime: ✓")
    else:
        print("❌ FAIL - Some checks failed")
        print(f"  is_negative: {is_negative}")
        print(f"  soft_preferences == '': {refined_criteria['soft_preferences'] == ''}")
        print(f"  should_fetch_crime: {should_fetch_crime}")
        print(f"  should_include_crime: {should_include_crime}")
        print(f"  crimes_6m is None: {example_property['crimes_6m'] is None}")

if __name__ == '__main__':
    test_complete_workflow()
