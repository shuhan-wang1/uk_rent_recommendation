"""
诊断脚本：测试 chat 端点是否正常工作
"""

import requests
import json

BASE_URL = "http://localhost:5001"

def test_simple_chat():
    """测试简单的对话（不涉及POI）"""
    print("=" * 60)
    print("测试 1: 简单对话（不涉及POI）")
    print("=" * 60)
    
    payload = {
        "message": "你好，Alex！",
        "context": {}
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功！")
            print(f"响应: {result.get('response', '')[:200]}")
        else:
            print(f"❌ 失败！")
            print(f"错误: {response.text}")
    except requests.exceptions.Timeout:
        print("❌ 请求超时！")
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误！服务器可能没有运行。")
    except Exception as e:
        print(f"❌ 异常: {e}")

def test_poi_chat():
    """测试POI查询（餐厅）"""
    print("\n" + "=" * 60)
    print("测试 2: POI查询（餐厅）")
    print("=" * 60)
    
    payload = {
        "message": "这个房源附近有餐厅吗？",
        "context": {
            "property": {
                "address": "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK"
            }
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 成功！")
            print(f"响应: {result.get('response', '')[:500]}")
        else:
            print(f"❌ 失败！")
            print(f"错误: {response.text}")
    except requests.exceptions.Timeout:
        print("❌ 请求超时！")
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误！服务器可能没有运行。")
    except Exception as e:
        print(f"❌ 异常: {e}")

def test_ollama_directly():
    """直接测试 Ollama API"""
    print("\n" + "=" * 60)
    print("测试 3: 直接测试 Ollama API")
    print("=" * 60)
    
    payload = {
        "model": "llama3.2:1b",
        "prompt": "你好，请简单介绍一下自己。",
        "stream": False
    }
    
    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ollama 正常工作！")
            print(f"响应: {result.get('response', '')[:200]}")
        else:
            print(f"❌ Ollama 失败！")
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"❌ Ollama 异常: {e}")

if __name__ == "__main__":
    print("\n🔍 开始诊断...\n")
    
    # 首先测试 Ollama
    test_ollama_directly()
    
    # 然后测试 Flask 端点
    test_simple_chat()
    test_poi_chat()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
