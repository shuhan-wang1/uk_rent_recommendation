"""
验证修复后的效果 - 需要先重启Flask服务器

使用方法：
1. 确保Flask服务器已重启（加载新代码）
2. 运行此脚本测试
"""

import requests
import json

def test_restaurant_fix():
    """测试餐厅搜索修复"""
    
    print("="*80)
    print("🧪 测试餐厅搜索修复效果")
    print("="*80)
    
    url = "http://localhost:5001/chat"
    
    payload = {
        "message": "这个房源附近有没有餐厅？",
        "context": {
            "property": {
                "address": "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK"
            }
        }
    }
    
    print(f"\n📤 发送请求...")
    print(f"   问题: {payload['message']}")
    print(f"   地址: {payload['context']['property']['address']}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   确保Flask服务器在 http://localhost:5001 运行")
            return
        
        result = response.json()
        answer = result.get('response', '')
        
        print("\n" + "="*80)
        print("📨 Alex的回答:")
        print("="*80)
        print(answer)
        
        print("\n" + "="*80)
        print("✅ 验证结果:")
        print("="*80)
        
        # 应该提到的正确餐厅
        correct = {
            'Crazy Salad': 36,
            'Nonna Selena': 41,
            'WingWing': 46,
            'Poppadom': 89,
            'Bloomsbury Pizza': 107
        }
        
        # 不应该提到的错误餐厅
        wrong = {
            'Delaunay': 1410,
            'Simpson': '>1500',
            'Barbary': 1114,
            'Padella': '>1500'
        }
        
        correct_count = 0
        wrong_count = 0
        
        print("\n✅ 应该提到的餐厅（最近的）：")
        for name, dist in correct.items():
            if name in answer:
                if str(dist) in answer or f"{dist}m" in answer or f"{dist}米" in answer:
                    print(f"   ✓ {name} - {dist}米 (名称和距离都正确)")
                    correct_count += 1
                else:
                    print(f"   ⚠️ {name} - 提到了名称但距离可能不对")
            else:
                print(f"   ✗ {name} - 未提到")
        
        print(f"\n❌ 不应该提到的餐厅（太远/编造）：")
        for name, dist in wrong.items():
            if name in answer:
                print(f"   ✗ {name} - 仍被提到（修复失败！）")
                wrong_count += 1
            else:
                print(f"   ✓ {name} - 未提到（修复成功）")
        
        print("\n" + "="*80)
        print("📊 评分:")
        print("="*80)
        
        total_score = (correct_count / len(correct)) * 50 + ((len(wrong) - wrong_count) / len(wrong)) * 50
        
        print(f"   正确餐厅: {correct_count}/{len(correct)}")
        print(f"   避免错误: {len(wrong) - wrong_count}/{len(wrong)}")
        print(f"   总分: {total_score:.1f}/100")
        
        if total_score >= 90:
            print("\n   🎉 修复非常成功！")
        elif total_score >= 70:
            print("\n   ✅ 修复基本成功，但仍有改进空间")
        elif total_score >= 50:
            print("\n   ⚠️ 部分修复，需要进一步调整")
        else:
            print("\n   ❌ 修复效果不佳，可能需要检查:")
            print("      1. Flask服务器是否已重启")
            print("      2. LLM模型是否太小（建议升级到3B+）")
            print("      3. Prompt是否被正确应用")
        
        # 检查是否使用了JSON格式的数据
        if "真实数据" in answer or "OpenStreetMap" in answer:
            print("\n   ℹ️ 回答中提到了数据来源（好现象）")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到Flask服务器")
        print("   请确保运行了: python app.py")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                        餐厅搜索修复验证测试                                  ║
║                                                                            ║
║  ⚠️  重要：在运行此测试前，请确保：                                          ║
║                                                                            ║
║  1. 停止旧的Flask服务器（Ctrl+C）                                           ║
║  2. 重新启动Flask服务器：python app.py                                      ║
║  3. 等待服务器完全启动（看到 "Running on http://127.0.0.1:5001"）           ║
║  4. 然后运行此测试脚本                                                      ║
║                                                                            ║
║  如果不重启服务器，仍然会使用旧代码！                                        ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    input("\n按回车键开始测试（确保已重启服务器）...")
    
    test_restaurant_fix()
