"""
强化修复验证测试
测试新增的后处理验证机制
"""

import requests
import json

def test_强化修复():
    """测试强化修复后的效果"""
    
    print("="*80)
    print("🔥 强化修复验证测试")
    print("="*80)
    print("\n修复内容：")
    print("1. ✅ 添加了后处理验证函数 validate_and_fix_poi_response()")
    print("2. ✅ 自动检测编造的餐厅名（The Delaunay, Padella, Wolseley等）")
    print("3. ✅ 自动检测错误的距离数据")
    print("4. ✅ 如果检测到问题，自动替换为100%准确的安全响应")
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
    
    print(f"\n📤 发送测试请求...")
    print(f"   问题: {payload['message']}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"\n❌ 请求失败: HTTP {response.status_code}")
            print(f"   错误: {response.text}")
            print(f"\n   请确保：")
            print(f"   1. Flask服务器正在运行（python app.py）")
            print(f"   2. 已经重启了服务器（加载新代码）")
            return
        
        result = response.json()
        answer = result.get('response', '')
        
        print("\n" + "="*80)
        print("📨 Alex的回答:")
        print("="*80)
        # 移除HTML标签显示
        import re
        clean_answer = re.sub(r'<[^>]+>', '', answer)
        print(clean_answer)
        
        print("\n" + "="*80)
        print("🔍 自动检测结果:")
        print("="*80)
        
        # 检测编造的餐厅名
        fake_restaurants = ['Delaunay', 'Wolseley', 'Padella', 'Simpson', 'Barbary']
        real_restaurants = ['Crazy Salad', 'Nonna Selena', 'WingWing', 'Poppadom', 'Bloomsbury Pizza']
        
        fake_found = [r for r in fake_restaurants if r in answer]
        real_found = [r for r in real_restaurants if r in answer]
        
        print(f"\n❌ 编造的餐厅（不应该出现）:")
        if fake_found:
            for r in fake_found:
                print(f"   ✗ {r} - 仍然出现（验证失败！）")
            print(f"\n   ⚠️ 检测到 {len(fake_found)} 个编造的餐厅名")
            print(f"   ⚠️ 后处理验证可能没有生效")
        else:
            print(f"   ✓ 没有编造的餐厅名（验证成功！）")
        
        print(f"\n✅ 真实的餐厅（应该出现）:")
        if real_found:
            for r in real_found:
                print(f"   ✓ {r} - 已提到")
            print(f"\n   ✅ 找到 {len(real_found)} 个真实餐厅")
        else:
            print(f"   ✗ 没有提到真实餐厅（可能有问题）")
        
        # 检测距离数据
        print(f"\n📏 距离数据检测:")
        correct_distances = ['36', '41', '46', '89', '107']
        wrong_distances = ['320', '480', '640', '800', '1410']
        
        correct_found = [d for d in correct_distances if d in answer]
        wrong_found = [d for d in wrong_distances if d in answer]
        
        if correct_found:
            print(f"   ✓ 发现正确距离: {', '.join(correct_found)}米")
        
        if wrong_found:
            print(f"   ✗ 发现错误距离: {', '.join(wrong_found)}米（验证失败！）")
        else:
            print(f"   ✓ 没有错误距离")
        
        # 评分
        print("\n" + "="*80)
        print("📊 修复效果评分:")
        print("="*80)
        
        score = 0
        max_score = 100
        
        # 没有编造餐厅 (40分)
        if not fake_found:
            score += 40
            print(f"   ✓ 没有编造餐厅: +40分")
        else:
            deduction = len(fake_found) * 10
            print(f"   ✗ 发现{len(fake_found)}个编造餐厅: -{deduction}分")
        
        # 提到真实餐厅 (30分)
        real_score = (len(real_found) / len(real_restaurants)) * 30
        score += real_score
        print(f"   ✓ 提到真实餐厅 ({len(real_found)}/5): +{real_score:.0f}分")
        
        # 距离数据准确 (30分)
        if wrong_found:
            deduction = len(wrong_found) * 6
            print(f"   ✗ 发现{len(wrong_found)}个错误距离: -{deduction}分")
        elif correct_found:
            score += 30
            print(f"   ✓ 距离数据准确: +30分")
        
        print(f"\n   总分: {score:.0f}/{max_score}")
        
        if score >= 90:
            print("\n   🎉🎉🎉 强化修复非常成功！")
            print("   LLM响应已被完全修正或直接生成了准确答案")
        elif score >= 70:
            print("\n   ✅ 强化修复基本成功")
            print("   大部分问题已被修正")
        elif score >= 50:
            print("\n   ⚠️ 部分修复")
            print("   可能需要检查验证函数是否被正确调用")
        else:
            print("\n   ❌ 修复效果不佳")
            print("\n   可能原因：")
            print("   1. 服务器未重启（仍在运行旧代码）")
            print("   2. 验证函数未被调用")
            print("   3. LLM完全忽略了prompt")
            print("\n   建议：")
            print("   1. 确保停止旧服务器（Ctrl+C）")
            print("   2. 重新运行：python app.py")
            print("   3. 等待启动完成后再测试")
        
        # 检查是否使用了安全响应
        if "OpenStreetMap的实时数据" in answer or "OpenStreetMap的真实数据" in answer:
            print("\n   ℹ️ 响应提到了OpenStreetMap数据来源（好迹象）")
        
        if len(fake_found) > 0 and len(real_found) > 3:
            print("\n   ⚠️ 可能的情况：")
            print("   - LLM生成了混合响应（既有编造的也有真实的）")
            print("   - 验证函数的检测阈值可能需要调整")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到Flask服务器")
        print("\n   请执行以下步骤：")
        print("   1. 打开一个新终端")
        print("   2. cd c:\\Users\\shuhan\\Desktop\\uk_rent_recommendation\\local_data_demo")
        print("   3. python app.py")
        print("   4. 等待看到 'Running on http://127.0.0.1:5001'")
        print("   5. 然后重新运行此测试")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                         🔥 强化修复验证测试 🔥                              ║
║                                                                            ║
║  新增功能：                                                                 ║
║  1. 后处理验证机制 - 自动检测LLM编造的内容                                  ║
║  2. 自动修正 - 检测到问题时自动替换为100%准确的答案                         ║
║  3. 强制准确性 - 即使LLM编造，用户也只会看到真实数据                        ║
║                                                                            ║
║  ⚠️ 重要：测试前必须重启Flask服务器！                                       ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    input("\n按回车开始测试（确保已重启服务器）...")
    
    test_强化修复()
    
    print("\n\n" + "="*80)
    print("🔧 如果修复仍然失败的备选方案：")
    print("="*80)
    print("""
方案1：升级LLM模型（最推荐）
    在 core/llm_interface.py 修改：
    MODEL_NAME = "llama3.2:3b"  # 从1b升级到3b
    
方案2：完全绕过LLM
    直接返回格式化的真实数据，不让LLM参与
    
方案3：使用Function Calling模式
    让LLM只选择餐厅索引，系统代码生成最终答案
    
方案4：添加更激进的验证
    降低检测阈值，只要发现任何可疑内容就替换
    """)
