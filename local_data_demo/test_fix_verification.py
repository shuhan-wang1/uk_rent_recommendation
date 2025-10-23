"""
验证修复后的餐厅和超市搜索功能
"""

import requests
import json


def test_fixed_restaurant_search():
    """测试修复后的餐厅搜索"""
    
    print("="*70)
    print("测试1：餐厅搜索修复验证")
    print("="*70)
    
    url = "http://localhost:5001/chat"
    
    payload = {
        "message": "这个房源附近有没有餐厅？",
        "context": {
            "property": {
                "address": "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK",
                "price": "£200/week"
            }
        }
    }
    
    print(f"\n发送请求：{payload['message']}")
    print(f"房源地址：{payload['context']['property']['address']}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        answer = result.get('response', '')
        
        print("\n" + "="*70)
        print("Alex的回答：")
        print("="*70)
        print(answer)
        
        print("\n" + "="*70)
        print("验证检查：")
        print("="*70)
        
        # 检查是否提到了正确的餐厅
        correct_restaurants = [
            "Crazy Salad",
            "Nonna Selena Pizzeria",
            "WingWing Krispy Chicken",
            "Poppadom Express",
            "Bloomsbury Pizza Cafe"
        ]
        
        # 检查是否提到了错误的餐厅
        wrong_restaurants = [
            "The Delaunay",
            "Wolseley",
            "Padella",
            "Simpson",
            "The Barbary"
        ]
        
        print("\n✅ 应该提到的餐厅（最近的5个）：")
        for r in correct_restaurants:
            if r in answer:
                print(f"   ✓ {r} - 已提到")
            else:
                print(f"   ✗ {r} - 未提到（可能有问题）")
        
        print("\n❌ 不应该提到的餐厅（编造的/太远的）：")
        for r in wrong_restaurants:
            if r in answer:
                print(f"   ✗ {r} - 仍然被提到（修复失败！）")
            else:
                print(f"   ✓ {r} - 未提到（修复成功）")
        
        # 检查距离数据
        print("\n📏 距离数据检查：")
        correct_distances = ["36m", "41m", "46m", "89m", "107m"]
        wrong_distances = ["320m", "480m", "640m", "800m", "1410m"]
        
        for d in correct_distances:
            if d in answer:
                print(f"   ✓ 发现正确距离: {d}")
        
        for d in wrong_distances:
            if d in answer:
                print(f"   ✗ 发现错误距离: {d}（修复失败！）")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return None


def test_fixed_supermarket_search():
    """测试修复后的超市搜索"""
    
    print("\n\n" + "="*70)
    print("测试2：超市搜索修复验证")
    print("="*70)
    
    url = "http://localhost:5001/chat"
    
    payload = {
        "message": "房源附近有没有Tesco, Sainsbury's, Lidl, Waitrose?",
        "context": {
            "property": {
                "address": "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK",
                "price": "£200/week"
            }
        }
    }
    
    print(f"\n发送请求：{payload['message']}")
    print(f"房源地址：{payload['context']['property']['address']}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        answer = result.get('response', '')
        
        print("\n" + "="*70)
        print("Alex的回答：")
        print("="*70)
        print(answer)
        
        print("\n" + "="*70)
        print("验证检查：")
        print("="*70)
        
        print("\n✅ 应该找到的超市：")
        if "Waitrose" in answer and "223" in answer:
            print("   ✓ Waitrose - 223m（正确）")
        else:
            print("   ✗ Waitrose数据不正确")
        
        if "Lidl" in answer and "696" in answer:
            print("   ✓ Lidl - 696m（正确）")
        else:
            print("   ✗ Lidl数据不正确")
        
        print("\n❌ 应该说明未找到的超市：")
        if "Tesco" in answer and ("未找到" in answer or "没有找到" in answer or "not found" in answer.lower()):
            print("   ✓ 正确说明Tesco未找到")
        elif "Tesco" not in answer:
            print("   ✓ 没有提到Tesco（也可以）")
        else:
            print("   ✗ Tesco被错误提及（修复失败！）")
        
        if "Sainsbury" in answer and ("未找到" in answer or "没有找到" in answer or "not found" in answer.lower()):
            print("   ✓ 正确说明Sainsbury's未找到")
        elif "Sainsbury" not in answer:
            print("   ✓ 没有提到Sainsbury's（也可以）")
        else:
            print("   ✗ Sainsbury's被错误提及（修复失败！）")
        
        print("\n🏠 地址检查：")
        if "Brunswick Square" in answer and "Tesco" in answer:
            print("   ✗ 仍然编造了Brunswick Square地址（修复失败！）")
        else:
            print("   ✓ 没有编造地址（修复成功）")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return None


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                   餐厅和超市搜索修复验证测试                          ║
║                                                                      ║
║  此测试将验证以下修复是否成功：                                       ║
║  1. 餐厅搜索：只显示最近的5个，不编造著名餐厅                          ║
║  2. 超市搜索：只显示真实存在的，不编造Tesco/Sainsbury's              ║
║  3. 距离数据：使用真实的OpenStreetMap数据                            ║
║  4. 地址信息：不编造Brunswick Square等地址                           ║
║                                                                      ║
║  前提条件：Flask服务器需要在 http://localhost:5001 运行               ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\n⏳ 等待3秒，请确保Flask服务器已启动...")
    import time
    time.sleep(3)
    
    # 运行测试
    test_fixed_restaurant_search()
    test_fixed_supermarket_search()
    
    print("\n\n" + "="*70)
    print("测试完成！")
    print("="*70)
    print("""
如果看到修复失败的标记，说明LLM仍然在编造信息。
可能需要：
1. 使用更强的LLM模型（如Llama 3.2 3B而非1B）
2. 进一步强化prompt约束
3. 添加后处理验证机制
    """)
