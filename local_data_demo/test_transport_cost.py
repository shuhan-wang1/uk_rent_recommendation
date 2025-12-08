"""
测试 check_transport_cost 工具
验证硬编码的交通费用查询功能
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tools.check_transport_cost import check_transport_cost_impl

async def test_transport_cost():
    """测试交通费用查询工具"""
    
    print("=" * 60)
    print("测试 check_transport_cost 工具")
    print("=" * 60)
    
    # 测试案例
    test_cases = [
        {"end_zone": 2, "travel_type": "student", "desc": "学生 Zone 1-2"},
        {"end_zone": 6, "travel_type": "student", "desc": "学生 Zone 1-6"},
        {"end_zone": 3, "travel_type": "adult", "desc": "成人 Zone 1-3"},
        {"end_zone": 5, "travel_type": "student", "desc": "学生 Zone 1-5"},
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test['desc']}")
        print("-" * 60)
        
        result = await check_transport_cost_impl(
            end_zone=test['end_zone'],
            travel_type=test['travel_type']
        )
        
        if result['success']:
            data = result['data']
            print(f"✅ 成功查询")
            print(f"   区域: {data['zones']}")
            print(f"   用户类型: {data['user_type']}")
            print(f"   月票: {data['prices']['monthly_pass']}")
            print(f"   周票: {data['prices']['weekly_pass']}")
            print(f"   日封顶: {data['prices']['daily_cap_payg']}")
            print(f"   说明: {data['note']}")
            print(f"   数据源: {data['source']}")
        else:
            print(f"❌ 查询失败: {result.get('error')}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_transport_cost())
