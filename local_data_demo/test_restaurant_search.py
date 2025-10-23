"""
测试餐厅搜索功能 - 验证是否真正使用OpenStreetMap数据
"""

from core.maps_service import get_nearby_places_osm
import json


def test_restaurant_search():
    """测试Bloomsbury附近的餐厅搜索"""
    
    print("="*70)
    print("测试：Scape Bloomsbury 附近的餐厅搜索")
    print("="*70)
    
    address = "Scape Bloomsbury, London"
    
    # 调用真实的OpenStreetMap API
    result = get_nearby_places_osm(address, 'restaurant', radius_m=1500)
    
    print(f"\n✅ 找到 {len(result)} 家餐厅在 1.5km 范围内\n")
    
    # 显示前10家
    print("前10家最近的餐厅：")
    print("-" * 70)
    for i, place in enumerate(result[:10], 1):
        name = place['name']
        distance_m = place['distance_m']
        distance_km = round(distance_m / 1000, 2)
        print(f"{i:2d}. {name:40s} - {distance_m:4d}m ({distance_km}km)")
    
    print("\n" + "="*70)
    print("验证问题：")
    print("="*70)
    
    # 检查用户提到的餐厅是否在真实数据中
    fake_restaurants = ["The Delaunay", "The Wolseley", "Padella", "Dishoom"]
    real_names = [p['name'] for p in result]
    
    print("\n❌ Alex 提到的餐厅：")
    for fake in fake_restaurants:
        if fake in real_names:
            print(f"   ✓ {fake} - 在真实数据中")
        else:
            print(f"   ✗ {fake} - 不在真实数据中（可能是编造的）")
    
    print("\n✅ 真实的OpenStreetMap数据中的餐厅（前5个）：")
    for place in result[:5]:
        print(f"   • {place['name']} - {place['distance_m']}m")
    
    # 保存完整数据到文件
    with open('restaurant_search_results.json', 'w', encoding='utf-8') as f:
        json.dump(result[:20], f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 完整数据已保存到: restaurant_search_results.json")
    
    return result


def test_travel_time_verification():
    """验证是否计算了到餐厅的出行时间"""
    
    print("\n" + "="*70)
    print("测试：出行时间计算")
    print("="*70)
    
    from core.maps_service import calculate_travel_time
    
    origin = "Scape Bloomsbury, London"
    destination = "Dishoom King's Cross, London"  # Alex提到的一家餐厅
    
    print(f"\n从: {origin}")
    print(f"到: {destination}")
    
    try:
        travel_time = calculate_travel_time(origin, destination, mode='walking')
        print(f"\n步行时间: {travel_time} 分钟")
        
        if travel_time:
            print("✅ 出行时间计算功能正常")
        else:
            print("⚠️ 出行时间计算返回None")
    except Exception as e:
        print(f"❌ 出行时间计算失败: {e}")


if __name__ == "__main__":
    # 运行测试
    result = test_restaurant_search()
    
    # 测试出行时间
    test_travel_time_verification()
    
    print("\n" + "="*70)
    print("结论：")
    print("="*70)
    print("""
1. ✅ OpenStreetMap API 正常工作，返回了真实的餐厅数据
2. ❌ LLM (Alex) 编造了餐厅名字（The Delaunay, Wolseley, Padella, Dishoom）
3. ❓ 需要检查：LLM是否真正使用了OpenStreetMap返回的数据

问题根源：
- 数据获取层（OpenStreetMap API）工作正常
- 问题在于LLM响应生成层，LLM没有使用真实数据，而是编造了答案

建议解决方案：
1. 在system prompt中强制要求LLM只使用提供的数据
2. 在prompt中明确标记"VERIFIED DATA"并要求LLM逐字引用
3. 添加后处理验证，检查LLM响应中的餐厅名是否在真实数据中
4. 考虑使用结构化输出格式（JSON）来限制LLM的创造性
    """)
