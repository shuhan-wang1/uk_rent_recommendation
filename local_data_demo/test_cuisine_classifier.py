"""
测试餐厅菜系分类功能
"""

from core.cuisine_classifier import classify_cuisine, group_restaurants_by_cuisine, format_cuisine_summary

# 测试菜系分类
print("=" * 60)
print("测试菜系分类功能")
print("=" * 60)

test_cases = [
    ("chinese", "中餐"),
    ("cantonese", "中餐"),
    ("italian", "意大利菜"),
    ("pizza", "意大利菜"),
    ("japanese", "日本料理"),
    ("sushi", "日本料理"),
    ("indian", "印度菜"),
    ("thai", "泰国菜"),
    ("greek", "希腊菜/地中海菜"),
    ("turkish", "土耳其菜"),
    ("french", "法国菜"),
    ("burger", "美国菜"),
    ("mexican", "墨西哥菜"),
    ("kebab", "土耳其菜"),
    ("fast_food", "快餐"),
    (None, "其他"),
]

print("\n分类测试：")
for cuisine_tag, expected_cn in test_cases:
    cuisine_type, cuisine_cn = classify_cuisine(cuisine_tag)
    status = "✅" if cuisine_cn == expected_cn else "❌"
    print(f"{status} '{cuisine_tag}' -> {cuisine_type} ({cuisine_cn})")

# 测试餐厅分组
print("\n" + "=" * 60)
print("测试餐厅分组功能")
print("=" * 60)

mock_restaurants = [
    {'name': 'Crazy Salad', 'distance_m': 36, 'cuisine': 'chinese'},
    {'name': 'Pizza Express', 'distance_m': 50, 'cuisine': 'pizza'},
    {'name': 'Sushi Bar', 'distance_m': 80, 'cuisine': 'japanese'},
    {'name': 'Nonna Selena', 'distance_m': 41, 'cuisine': 'italian'},
    {'name': 'Tandoori Nights', 'distance_m': 100, 'cuisine': 'indian'},
    {'name': 'Golden Dragon', 'distance_m': 120, 'cuisine': 'chinese'},
    {'name': 'Thai Orchid', 'distance_m': 150, 'cuisine': 'thai'},
    {'name': 'Unknown Restaurant', 'distance_m': 200},  # 无 cuisine 标签
]

grouped = group_restaurants_by_cuisine(mock_restaurants)

print("\n分组结果：")
for cuisine_type, data in grouped.items():
    count = len(data['restaurants'])
    name_cn = data['name_cn']
    print(f"\n{name_cn} ({cuisine_type}): {count}家")
    for r in data['restaurants']:
        print(f"  - {r['name']} ({r['distance_m']}米)")

print("\n" + "=" * 60)
print("菜系摘要")
print("=" * 60)
summary = format_cuisine_summary(grouped)
print(summary)

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
