"""快速验证Alex提到的餐厅距离"""
from core.maps_service import get_nearby_places_osm

print("="*70)
print("验证Alex提到的餐厅的真实距离")
print("="*70)

result = get_nearby_places_osm('Scape Bloomsbury, London', 'restaurant', 1500)

alex_claims = {
    'The Delaunay': {'claimed': '0.2 miles (320m)', 'walk': '4分钟'},
    'Simpson': {'claimed': '0.3 miles (480m)', 'walk': '6分钟'},
    'The Barbary': {'claimed': '0.4 miles (640m)', 'walk': '8分钟'},
    'Padella': {'claimed': '0.5 miles (800m)', 'walk': '10分钟'}
}

print("\nAlex的声称 vs 真实数据：\n")

for name, claim in alex_claims.items():
    matching = [r for r in result if name.lower() in r['name'].lower()]
    
    if matching:
        actual = matching[0]
        claimed_m = int(claim['claimed'].split('(')[1].split('m')[0])
        actual_m = actual['distance_m']
        diff = actual_m - claimed_m
        
        print(f"❌ {name}:")
        print(f"   Alex说: {claim['claimed']}, {claim['walk']}步行")
        print(f"   实际距离: {actual_m}米")
        print(f"   误差: +{diff}米 ({round(diff/claimed_m*100)}%错误)")
        print()
    else:
        print(f"❌ {name}:")
        print(f"   Alex说: {claim['claimed']}")
        print(f"   实际: 不在1.5km范围内（完全编造！）")
        print()

print("="*70)
print("真实的最近餐厅（Alex应该推荐的）：")
print("="*70)
for i, r in enumerate(result[:5], 1):
    print(f"{i}. {r['name']} - {r['distance_m']}米")
