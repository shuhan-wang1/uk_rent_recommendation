#!/usr/bin/env python3
"""
Quick Test Script - Demonstrate the improvement in geocoding accuracy
"""

import sys
sys.path.append('/home/claude')

from coordinate_verifier import CoordinateVerifier
import pandas as pd

def quick_test():
    """
    快速测试：比较原始geocoding vs OSM建筑搜索的精度
    """
    print("\n" + "="*80)
    print("🎯 QUICK ACCURACY TEST")
    print("="*80)
    print("\n测试目标：验证OSM建筑搜索是否能解决0.7英里误差问题\n")
    
    # Test addresses from your CSV
    test_addresses = [
        "Tufnell House, 144 Huddleston Road, London N7 0EG, UK",
        "Scape Bloomsbury, 19-29 Woburn Place, London WC1H 0AQ, UK",
        "Vega, 6 Miles Street, Vauxhall, London SW8 1RZ, UK",
        "City, 11 Bastwick Street, London EC1V 3AQ, UK",
        "Brent Cross Town, Merchant Street, London NW2, UK",
        "Spring Mews, 10 Tinworth Street, London SE11 5AL, UK"
    ]
    
    verifier = CoordinateVerifier()
    
    print("正在测试6个房源地址...\n")
    print("每个地址将尝试:")
    print("  1️⃣ OSM建筑物直接搜索")
    print("  2️⃣ 传统Geocoding")
    print("  3️⃣ 计算两者的距离误差\n")
    print("="*80 + "\n")
    
    results_summary = []
    
    for i, address in enumerate(test_addresses, 1):
        print(f"\n{'#'*80}")
        print(f"测试 {i}/6: {address[:60]}...")
        print(f"{'#'*80}")
        
        result = verifier.verify_address(address)
        
        # Collect summary
        summary = {
            '序号': i,
            '地址': address[:40] + '...',
            'OSM找到': '✅' if result.get('osm_building') else '❌',
            'Geocoding': '✅' if result.get('geocoding') else '❌'
        }
        
        if result.get('distance'):
            error_miles = result['distance']['miles']
            summary['误差(英里)'] = f"{error_miles:.2f}"
            
            if error_miles < 0.05:
                summary['评级'] = '🟢 优秀'
            elif error_miles < 0.2:
                summary['评级'] = '🟡 良好'  
            else:
                summary['评级'] = '🔴 较差'
        else:
            summary['误差(英里)'] = 'N/A'
            summary['评级'] = 'N/A'
        
        results_summary.append(summary)
        
        # Rate limiting
        import time
        time.sleep(2)
    
    # Print summary table
    print(f"\n\n{'='*80}")
    print("📊 测试结果汇总")
    print(f"{'='*80}\n")
    
    df = pd.DataFrame(results_summary)
    print(df.to_string(index=False))
    
    # Analysis
    print(f"\n\n{'='*80}")
    print("🔍 结果分析")
    print(f"{'='*80}\n")
    
    osm_found_count = sum(1 for r in results_summary if r['OSM找到'] == '✅')
    
    errors = [float(r['误差(英里)']) for r in results_summary if r['误差(英里)'] != 'N/A']
    
    if errors:
        avg_error = sum(errors) / len(errors)
        max_error = max(errors)
        min_error = min(errors)
        
        print(f"✅ OSM建筑搜索成功率: {osm_found_count}/6 ({osm_found_count/6*100:.0f}%)")
        print(f"\n📏 误差统计:")
        print(f"   平均误差: {avg_error:.3f} 英里")
        print(f"   最大误差: {max_error:.3f} 英里")
        print(f"   最小误差: {min_error:.3f} 英里")
        
        excellent = sum(1 for e in errors if e < 0.05)
        good = sum(1 for e in errors if 0.05 <= e < 0.2)
        poor = sum(1 for e in errors if e >= 0.2)
        
        print(f"\n🎯 精度分布:")
        print(f"   🟢 优秀 (<0.05英里): {excellent}个")
        print(f"   🟡 良好 (0.05-0.2英里): {good}个")
        print(f"   🔴 较差 (>0.2英里): {poor}个")
        
        print(f"\n💡 建议:")
        if max_error > 0.5:
            print(f"   ⚠️  检测到较大误差({max_error:.2f}英里)")
            print(f"   📍 建议使用OSM建筑搜索结果")
            print(f"   💾 或添加精确坐标到verified_coordinates.json")
        elif max_error > 0.2:
            print(f"   ⚠️  有中等误差({max_error:.2f}英里)")
            print(f"   📍 建议优先使用OSM建筑搜索结果")
        else:
            print(f"   ✅ 所有坐标精度良好!")
            print(f"   🎉 可以直接使用改进版脚本生成地图")
    
    print(f"\n{'='*80}")
    print("✅ 测试完成！")
    print(f"{'='*80}\n")
    
    # Save results
    output_file = 'quick_test_results.csv'
    df.to_csv(output_file, index=False)
    print(f"📄 详细结果已保存到: {output_file}\n")

if __name__ == "__main__":
    try:
        quick_test()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()