"""
测试超市搜索功能 - 验证地址准确性
"""

from core.maps_service import get_nearby_places_osm
import json


def test_supermarket_search():
    """测试Scape Bloomsbury附近的超市搜索"""
    
    print("="*70)
    print("测试：Scape Bloomsbury 附近的超市搜索")
    print("="*70)
    
    address = "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK"
    
    # 调用真实的OpenStreetMap API
    result = get_nearby_places_osm(address, 'supermarket', radius_m=1500)
    
    print(f"\n✅ 找到 {len(result)} 家超市在 1.5km 范围内\n")
    
    # 显示所有超市
    print("所有超市（按距离排序）：")
    print("-" * 70)
    for i, place in enumerate(result, 1):
        name = place['name']
        distance_m = place['distance_m']
        distance_km = round(distance_m / 1000, 2)
        address = place.get('address', 'N/A')
        lat = place.get('lat', 'N/A')
        lon = place.get('lon', 'N/A')
        
        print(f"{i:2d}. {name:40s}")
        print(f"    距离: {distance_m:4d}m ({distance_km}km)")
        print(f"    地址: {address}")
        print(f"    坐标: ({lat}, {lon})")
        print()
    
    print("\n" + "="*70)
    print("重点检查：用户询问的连锁超市")
    print("="*70)
    
    # 检查用户询问的连锁超市
    target_chains = ['tesco', 'sainsbury', 'lidl', 'waitrose']
    
    print("\n查找：Tesco, Sainsbury's, Lidl, Waitrose")
    print("-" * 70)
    
    found_chains = {}
    for chain in target_chains:
        found = [p for p in result if chain.lower() in p['name'].lower()]
        found_chains[chain] = found
        
        if found:
            print(f"\n✅ 找到 {len(found)} 个 {chain.upper()}:")
            for p in found:
                print(f"   • {p['name']}")
                print(f"     距离: {p['distance_m']}m")
                print(f"     地址: {p.get('address', 'N/A')}")
                print(f"     坐标: ({p.get('lat')}, {p.get('lon')})")
        else:
            print(f"\n❌ 未找到 {chain.upper()}")
    
    print("\n" + "="*70)
    print("验证 Alex 的回答：")
    print("="*70)
    
    print("\nAlex 说的：")
    print("• Waitrose - 23-29 Brunswick Square - 223m away")
    print("• Tesco Express - 23-29 Brunswick Square - 223m away")
    print("• Sainsbury's Local - 23-29 Brunswick Square - 224m away")
    
    print("\n问题：三个超市的地址都是 '23-29 Brunswick Square'，这合理吗？")
    
    # 检查是否真的有这个地址
    brunswick_square_stores = [p for p in result if 'brunswick' in p.get('address', '').lower()]
    
    if brunswick_square_stores:
        print(f"\n✅ 确实在 Brunswick Square 附近找到了 {len(brunswick_square_stores)} 个超市：")
        for p in brunswick_square_stores:
            print(f"   • {p['name']} - {p.get('address')} - {p['distance_m']}m")
    else:
        print("\n⚠️ 在 Brunswick Square 没有找到超市")
        print("   可能的原因：")
        print("   1. OpenStreetMap 数据中没有详细地址")
        print("   2. LLM 编造了地址信息")
    
    # 检查距离是否一致
    print("\n" + "="*70)
    print("距离验证：")
    print("="*70)
    
    if found_chains['waitrose']:
        waitrose = found_chains['waitrose'][0]
        print(f"\nWaitrose 实际距离: {waitrose['distance_m']}m")
        print(f"Alex 说的距离: 223m")
        if abs(waitrose['distance_m'] - 223) < 50:
            print("✅ 距离基本准确")
        else:
            print(f"⚠️ 距离相差: {abs(waitrose['distance_m'] - 223)}m")
    
    if found_chains['tesco']:
        tesco = found_chains['tesco'][0]
        print(f"\nTesco 实际距离: {tesco['distance_m']}m")
        print(f"Alex 说的距离: 223m")
        if abs(tesco['distance_m'] - 223) < 50:
            print("✅ 距离基本准确")
        else:
            print(f"⚠️ 距离相差: {abs(tesco['distance_m'] - 223)}m")
    
    if found_chains['sainsbury']:
        sainsbury = found_chains['sainsbury'][0]
        print(f"\nSainsbury's 实际距离: {sainsbury['distance_m']}m")
        print(f"Alex 说的距离: 224m")
        if abs(sainsbury['distance_m'] - 224) < 50:
            print("✅ 距离基本准确")
        else:
            print(f"⚠️ 距离相差: {abs(sainsbury['distance_m'] - 224)}m")
    
    # 检查坐标是否相同
    print("\n" + "="*70)
    print("坐标检查：这三个超市是否在同一位置？")
    print("="*70)
    
    if found_chains['waitrose'] and found_chains['tesco'] and found_chains['sainsbury']:
        w_lat = found_chains['waitrose'][0]['lat']
        w_lon = found_chains['waitrose'][0]['lon']
        t_lat = found_chains['tesco'][0]['lat']
        t_lon = found_chains['tesco'][0]['lon']
        s_lat = found_chains['sainsbury'][0]['lat']
        s_lon = found_chains['sainsbury'][0]['lon']
        
        print(f"\nWaitrose 坐标:    ({w_lat}, {w_lon})")
        print(f"Tesco 坐标:       ({t_lat}, {t_lon})")
        print(f"Sainsbury's 坐标: ({s_lat}, {s_lon})")
        
        # 计算距离
        from core.maps_service import calculate_distance_m
        
        dist_wt = calculate_distance_m(w_lat, w_lon, t_lat, t_lon)
        dist_ws = calculate_distance_m(w_lat, w_lon, s_lat, s_lon)
        dist_ts = calculate_distance_m(t_lat, t_lon, s_lat, s_lon)
        
        print(f"\nWaitrose ↔ Tesco: {dist_wt:.1f}m")
        print(f"Waitrose ↔ Sainsbury's: {dist_ws:.1f}m")
        print(f"Tesco ↔ Sainsbury's: {dist_ts:.1f}m")
        
        if dist_wt < 50 and dist_ws < 50 and dist_ts < 50:
            print("\n✅ 这三个超市确实在同一位置（可能在同一建筑内）")
        else:
            print("\n⚠️ 这三个超市不在同一位置")
    
    # 保存完整数据到文件
    with open('supermarket_search_results.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 完整数据已保存到: supermarket_search_results.json")
    
    return result


def test_restaurant_location_accuracy():
    """测试餐厅搜索的地址准确性"""
    
    print("\n" + "="*70)
    print("测试：餐厅搜索 - 地址准确性")
    print("="*70)
    
    address = "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK"
    
    result = get_nearby_places_osm(address, 'restaurant', radius_m=1500)
    
    print(f"\n✅ 找到 {len(result)} 家餐厅在 1.5km 范围内\n")
    
    # Alex 提到的餐厅
    alex_restaurants = [
        {"name": "The Delaunay", "distance_miles": 0.2, "distance_m": 320, "walk_min": 4},
        {"name": "Simpson's-in-the-Strand", "distance_miles": 0.3, "distance_m": 480, "walk_min": 6},
        {"name": "Padella", "distance_miles": 0.4, "distance_m": 640, "walk_min": 8},
        {"name": "The Barbary", "distance_miles": 0.5, "distance_m": 800, "walk_min": 10},
    ]
    
    print("Alex 提到的餐厅及声称的距离：")
    print("-" * 70)
    for r in alex_restaurants:
        print(f"• {r['name']}: {r['distance_miles']} miles ({r['distance_m']}m, {r['walk_min']}分钟步行)")
    
    print("\n验证：这些餐厅是否在1.5km范围内？")
    print("-" * 70)
    
    for alex_r in alex_restaurants:
        found = [p for p in result if alex_r['name'].lower() in p['name'].lower()]
        
        if found:
            actual = found[0]
            print(f"\n✅ 找到: {actual['name']}")
            print(f"   Alex 说: {alex_r['distance_m']}m")
            print(f"   实际距离: {actual['distance_m']}m")
            print(f"   差距: {abs(actual['distance_m'] - alex_r['distance_m'])}m")
            
            if actual['distance_m'] > 1500:
                print(f"   ⚠️ 警告：超出1.5km搜索范围！")
        else:
            print(f"\n❌ 未找到: {alex_r['name']}")
            print(f"   Alex 说距离: {alex_r['distance_m']}m")
            print(f"   ⚠️ 这个餐厅不在1.5km范围内，或者名字不匹配")
    
    print("\n" + "="*70)
    print("真实的最近餐厅（应该推荐的）：")
    print("="*70)
    
    for i, place in enumerate(result[:10], 1):
        print(f"{i:2d}. {place['name']:40s} - {place['distance_m']:4d}m ({round(place['distance_m']/1000, 2)}km)")
    
    print("\n" + "="*70)
    print("问题分析：")
    print("="*70)
    
    print("""
问题2：Alex推荐的餐厅距离都特别远

根因分析：
1. Alex提到的餐厅（0.2-0.5 miles = 320-800m）确实比最近的餐厅（36-200m）远很多
2. 搜索范围是1.5km（1500m），但Alex推荐的是"著名"餐厅而非"最近"餐厅
3. LLM使用了预训练知识中关于Bloomsbury地区的餐厅，而非真实搜索结果

搜索范围：
- 系统使用的搜索半径：1500m（1.5km）
- 搜索中心：Scape Bloomsbury的精确坐标 (51.5244, -0.1273)
- 不是按"Bloomsbury大区"搜索，而是按公寓地址的精确坐标搜索

LLM的问题：
- LLM忽略了真实数据中最近的餐厅（36m的Crazy Salad等）
- 选择了"更有名"但"更远"的餐厅
- 这是典型的LLM"知识污染"问题
    """)


if __name__ == "__main__":
    # 运行超市测试
    supermarket_result = test_supermarket_search()
    
    # 运行餐厅位置测试
    test_restaurant_location_accuracy()
    
    print("\n" + "="*70)
    print("总结")
    print("="*70)
    print("""
超市问题：
✅ 距离数据基本准确（223-224m）
⚠️ 地址信息可能有问题（三个超市显示同一地址）
   - 可能是真的在同一建筑内（商场/购物中心）
   - 也可能是OpenStreetMap数据不完整，LLM填补了地址

餐厅问题：
❌ 推荐的餐厅距离太远（320-800m vs 实际最近的36m）
❌ LLM选择"著名餐厅"而非"最近餐厅"
✅ 搜索是按公寓精确坐标，不是按大区

建议修复：
1. 强制要求LLM按距离排序推荐（最近的优先）
2. 明确指示："推荐最近的5家，不要考虑名气"
3. 添加距离阈值：只推荐500m以内的餐厅作为"附近"
4. 验证地址信息的来源（是真实数据还是LLM补充的）
    """)
