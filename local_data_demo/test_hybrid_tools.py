"""
测试混合工具调用系统
验证 check_transport_cost + web_search 的协同工作
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_tool_registration():
    """测试工具注册"""
    print("=" * 70)
    print("测试 1: 工具注册系统")
    print("=" * 70)
    
    try:
        from core.tool_system import create_tool_registry
        
        registry = create_tool_registry()
        
        print(f"\n✅ 工具注册成功! 共 {len(registry.tools)} 个工具:")
        for tool_name in registry.tools.keys():
            print(f"   - {tool_name}")
        
        # 验证 check_transport_cost 是否注册
        if 'check_transport_cost' in registry.tools:
            print(f"\n✅ check_transport_cost 工具已成功注册!")
            tool = registry.tools['check_transport_cost']
            print(f"   描述: {tool.description[:100]}...")
        else:
            print(f"\n❌ check_transport_cost 工具未注册!")
            
    except Exception as e:
        print(f"\n❌ 工具注册失败: {e}")
        import traceback
        traceback.print_exc()

async def test_transport_cost_tool():
    """测试交通费用工具"""
    print("\n" + "=" * 70)
    print("测试 2: check_transport_cost 工具功能")
    print("=" * 70)
    
    try:
        from core.tools.check_transport_cost import check_transport_cost_impl
        
        test_cases = [
            {"end_zone": 2, "travel_type": "student", "desc": "学生 Zone 1-2"},
            {"end_zone": 6, "travel_type": "student", "desc": "学生 Zone 1-6"},
            {"end_zone": 3, "travel_type": "adult", "desc": "成人 Zone 1-3"},
        ]
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n测试案例 {i}: {test['desc']}")
            print("-" * 70)
            
            result = await check_transport_cost_impl(
                end_zone=test['end_zone'],
                travel_type=test['travel_type']
            )
            
            if result['success']:
                data = result['data']
                print(f"✅ 查询成功")
                print(f"   区域: {data['zones']}")
                print(f"   用户类型: {data['user_type']}")
                print(f"   月票: {data['prices']['monthly_pass']}")
                print(f"   周票: {data['prices']['weekly_pass']}")
                print(f"   日封顶: {data['prices']['daily_cap_payg']}")
            else:
                print(f"❌ 查询失败: {result.get('error')}")
                
    except Exception as e:
        print(f"\n❌ 工具测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_filter_logic():
    """测试过滤逻辑"""
    print("\n" + "=" * 70)
    print("测试 3: Web Search 过滤逻辑")
    print("=" * 70)
    
    try:
        from core.web_search import WebSearchService
        
        service = WebSearchService()
        
        # 模拟搜索结果
        mock_results = [
            {
                "url": "https://knightfrank.com/investment-report",
                "title": "London Property Investment Volume 2025",
                "content": "Transaction volume reached £2.8bn with cap rates improving"
            },
            {
                "url": "https://www.gov.uk/student-accommodation-guide",
                "title": "Official Student Housing Guide UK 2025",
                "content": "Guide for international students renting in UK"
            },
            {
                "url": "https://uhomes.com/london-student-flats",
                "title": "London Student Accommodation Near UCL",
                "content": "Find affordable student housing near University College London"
            },
            {
                "url": "https://randomblog.com/some-article",
                "title": "Random Article About London",
                "content": "Some generic content not related to students"
            },
            {
                "url": "https://savethestudent.org/accommodation-guide",
                "title": "Student Accommodation Tips 2025",
                "content": "How to find safe and affordable student housing"
            }
        ]
        
        print(f"\n输入 {len(mock_results)} 个搜索结果:")
        for r in mock_results:
            print(f"   - {r['url']}")
        
        filtered = service._filter_authoritative_sources(mock_results)
        
        print(f"\n过滤后保留 {len(filtered)} 个结果:")
        for r in filtered:
            print(f"   ✅ {r['url']}")
            
        # 验证黑名单是否生效
        banned_urls = [r['url'] for r in filtered if 'knightfrank' in r['url']]
        if len(banned_urls) == 0:
            print(f"\n✅ 黑名单过滤成功! 投资类网站已被拦截")
        else:
            print(f"\n❌ 黑名单过滤失败! 仍有投资类网站: {banned_urls}")
            
        # 验证白名单是否优先
        whitelist_urls = [r['url'] for r in filtered if '.gov.uk' in r['url'] or 'uhomes.com' in r['url'] or 'savethestudent' in r['url']]
        if len(whitelist_urls) > 0:
            print(f"✅ 白名单优先成功! 保留了 {len(whitelist_urls)} 个权威来源")
        
    except Exception as e:
        print(f"\n❌ 过滤测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    print("\n" + "🔬" * 35)
    print("混合工具调用系统 - 完整测试")
    print("🔬" * 35 + "\n")
    
    await test_tool_registration()
    await test_transport_cost_tool()
    await test_filter_logic()
    
    print("\n" + "=" * 70)
    print("✅ 所有测试完成!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
