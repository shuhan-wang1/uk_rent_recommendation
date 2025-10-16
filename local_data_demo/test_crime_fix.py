#!/usr/bin/env python3
"""
测试脚本：验证 crime data 不会在用户说"No concerns"时出现
"""

import sys
import json
import asyncio
from core.llm_interface import generate_recommendations, create_fallback_recommendations
from core.enrichment_service import enrich_property_data
from core.data_loader import load_fake_properties

async def test_no_crime_when_no_concerns():
    """测试：当用户说'没有其他关注'时，不应该显示 crime data"""
    
    print("=" * 80)
    print("TEST: Crime data should NOT appear when user says 'No concerns'")
    print("=" * 80)
    
    # 模拟用户的搜索条件
    user_query = "Find me properties near UCL, I want it to be student friendly. Budget within 2000 pounds per month. Ideal travel time within 45 min."
    
    # 用户说"没有其他关注" -> soft_preferences 应该是空的
    soft_preferences = ""  # 空 = 用户没有其他关注
    
    print(f"\n📋 USER QUERY: {user_query}")
    print(f"📋 USER RESPONSE: 'No, I do not have any other concerns'")
    print(f"📋 soft_preferences: '{soft_preferences}' (empty = no special concerns)")
    
    # 加载假数据
    properties = load_fake_properties()
    print(f"\n✓ Loaded {len(properties)} properties from CSV")
    
    # 模拟enrichment过程 - 这会决定是否获取crime data
    print("\n" + "=" * 80)
    print("PHASE 1: ENRICHMENT (should skip crime data)")
    print("=" * 80)
    
    criteria = {
        'destination': 'UCL',
        'soft_preferences': soft_preferences,  # 空 = 没有特殊关注
        'amenities_of_interest': []
    }
    
    # 只enrichment前3个属性来加速测试
    for i, prop in enumerate(properties[:3]):
        print(f"\n[Property {i+1}] {prop.get('Address', 'Unknown')[:50]}")
        enriched = await enrich_property_data(prop, criteria)
        
        # 检查是否有 crime 字段
        has_crime = 'crime_data_summary' in enriched
        print(f"  Has crime_data_summary: {has_crime}")
        if has_crime:
            print(f"  ⚠️  WARNING: Crime data present even though user didn't ask!")
            crime_data = enriched['crime_data_summary']
            print(f"     Crime count: {crime_data.get('total_crimes_6m', 'N/A')}")
    
    # 现在测试推荐生成
    print("\n" + "=" * 80)
    print("PHASE 2: RECOMMENDATION GENERATION")
    print("=" * 80)
    
    # 为了测试，添加必要的字段
    for prop in properties[:5]:
        prop['travel_time_minutes'] = 25 + (properties.index(prop) % 3) * 5
        prop['_max_budget'] = 2000
        if 'parsed_price' not in prop:
            price_str = prop.get('Price', '£1800').replace('£', '').replace(',', '')
            try:
                prop['parsed_price'] = float(price_str)
            except:
                prop['parsed_price'] = 1800
    
    print(f"\nGenerating recommendations with:")
    print(f"  - soft_preferences: '' (EMPTY)")
    print(f"  - Should NOT include crime data")
    
    # 尝试 LLM 生成
    result = generate_recommendations(properties[:5], user_query, soft_preferences)
    
    if result and 'recommendations' in result:
        print(f"\n✓ Generated {len(result['recommendations'])} recommendations")
        print("\n" + "=" * 80)
        print("CHECKING RECOMMENDATIONS FOR CRIME MENTIONS")
        print("=" * 80)
        
        crime_keywords = ['crime', 'safe', 'security', 'dangerous', 'incident', 'reported']
        
        for rec in result['recommendations']:
            rank = rec.get('rank', '?')
            address = rec.get('address', 'Unknown')[:40]
            explanation = rec.get('explanation', '')
            
            print(f"\n[Rank {rank}] {address}")
            print(f"Explanation: {explanation[:100]}...")
            
            # 检查是否包含crime关键词
            found_crime_mentions = []
            for keyword in crime_keywords:
                if keyword.lower() in explanation.lower():
                    found_crime_mentions.append(keyword)
            
            if found_crime_mentions:
                print(f"❌ ERROR: Found crime mentions: {found_crime_mentions}")
                print(f"   Full explanation: {explanation}")
            else:
                print(f"✓ No crime mentions")
    else:
        print("Using fallback recommendations...")
        result = create_fallback_recommendations(properties[:5], soft_preferences)
        
        if result and 'recommendations' in result:
            print(f"\n✓ Generated {len(result['recommendations'])} fallback recommendations")
            print("\n" + "=" * 80)
            print("CHECKING FALLBACK RECOMMENDATIONS FOR CRIME MENTIONS")
            print("=" * 80)
            
            crime_keywords = ['crime', 'safe', 'security', 'dangerous', 'incident', 'reported']
            
            for rec in result['recommendations']:
                rank = rec.get('rank', '?')
                address = rec.get('address', 'Unknown')[:40]
                explanation = rec.get('explanation', '')
                
                print(f"\n[Rank {rank}] {address}")
                print(f"Explanation: {explanation[:100]}...")
                
                # 检查是否包含crime关键词
                found_crime_mentions = []
                for keyword in crime_keywords:
                    if keyword.lower() in explanation.lower():
                        found_crime_mentions.append(keyword)
                
                if found_crime_mentions:
                    print(f"❌ ERROR: Found crime mentions: {found_crime_mentions}")
                    print(f"   Full explanation: {explanation}")
                else:
                    print(f"✓ No crime mentions")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(test_no_crime_when_no_concerns())
