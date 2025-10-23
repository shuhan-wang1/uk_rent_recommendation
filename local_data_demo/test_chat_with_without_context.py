"""
测试 chat 端点：有/无 property context 的情况
"""

import requests
import json

BASE_URL = "http://localhost:5001"

def test_chat_without_context():
    """测试：没有 property context 时询问位置相关问题"""
    print("=" * 60)
    print("测试 1: 没有 property context 询问餐厅")
    print("=" * 60)
    
    payload = {
        "message": "这附近有什么餐厅？",
        "context": {}  # 空 context
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=15)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 响应成功")
            print(f"内容: {result.get('response', '')}")
            
            # 检查是否要求提供地址
            if "地址" in result.get('response', '') or "房源" in result.get('response', ''):
                print("✅ 正确：要求用户提供地址")
            else:
                print("❌ 错误：应该要求提供地址，但没有")
        else:
            print(f"❌ 失败: {response.text}")
    except Exception as e:
        print(f"❌ 异常: {e}")

def test_chat_with_context():
    """测试：有 property context 时询问餐厅"""
    print("\n" + "=" * 60)
    print("测试 2: 有 property context 询问餐厅")
    print("=" * 60)
    
    payload = {
        "message": "这附近有什么餐厅？",
        "context": {
            "property": {
                "address": "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK"
            }
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 响应成功")
            response_text = result.get('response', '')
            print(f"内容: {response_text[:500]}")
            
            # 检查是否提到了真实的餐厅名
            real_restaurants = ['Crazy Salad', 'Nonna Selena', 'WingWing', 'Krispy Chicken']
            fake_restaurants = ['Delaunay', 'Wolseley', 'Padella', 'Simpson']
            
            found_real = any(name in response_text for name in real_restaurants)
            found_fake = any(name in response_text for name in fake_restaurants)
            
            if found_real and not found_fake:
                print("✅ 正确：提到了真实餐厅，没有编造")
            elif found_fake:
                print(f"❌ 错误：编造了餐厅（{[f for f in fake_restaurants if f in response_text]}）")
            else:
                print("⚠️  未知：没有提到熟悉的餐厅名")
        else:
            print(f"❌ 失败: {response.text}")
    except Exception as e:
        print(f"❌ 异常: {e}")

def test_general_chat():
    """测试：一般性对话（不涉及位置）"""
    print("\n" + "=" * 60)
    print("测试 3: 一般性对话（你好）")
    print("=" * 60)
    
    payload = {
        "message": "你好，Alex！",
        "context": {}
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=15)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 响应成功")
            print(f"内容: {result.get('response', '')[:200]}")
        else:
            print(f"❌ 失败: {response.text}")
    except Exception as e:
        print(f"❌ 异常: {e}")

if __name__ == "__main__":
    print("\n🔍 开始测试 chat 端点...\n")
    
    test_chat_without_context()
    test_chat_with_context()
    test_general_chat()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
