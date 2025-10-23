"""
餐厅菜系分类工具
根据 OpenStreetMap 的 cuisine 标签进行分类
"""

def classify_cuisine(cuisine_tag: str) -> tuple[str, str]:
    """
    将 OSM cuisine 标签分类为常见菜系类型
    
    Args:
        cuisine_tag: OpenStreetMap 的 cuisine 值 (例如: "chinese", "italian", "pizza")
    
    Returns:
        (分类名称, 中文名称) 例如: ("chinese", "中餐")
    """
    if not cuisine_tag:
        return ("other", "其他")
    
    cuisine_lower = cuisine_tag.lower()
    
    # 中餐系列
    chinese_keywords = ['chinese', 'cantonese', 'sichuan', 'dim_sum', 'asian']
    if any(kw in cuisine_lower for kw in chinese_keywords):
        return ("chinese", "中餐")
    
    # 意大利菜系列
    italian_keywords = ['italian', 'pizza', 'pasta']
    if any(kw in cuisine_lower for kw in italian_keywords):
        return ("italian", "意大利菜")
    
    # 日本料理
    japanese_keywords = ['japanese', 'sushi', 'ramen', 'izakaya']
    if any(kw in cuisine_lower for kw in japanese_keywords):
        return ("japanese", "日本料理")
    
    # 韩国料理
    korean_keywords = ['korean', 'bbq']
    if any(kw in cuisine_lower for kw in korean_keywords):
        return ("korean", "韩国料理")
    
    # 印度菜
    indian_keywords = ['indian', 'curry', 'tandoori']
    if any(kw in cuisine_lower for kw in indian_keywords):
        return ("indian", "印度菜")
    
    # 泰国菜
    thai_keywords = ['thai', 'pad_thai']
    if any(kw in cuisine_lower for kw in thai_keywords):
        return ("thai", "泰国菜")
    
    # 越南菜
    vietnamese_keywords = ['vietnamese', 'pho']
    if any(kw in cuisine_lower for kw in vietnamese_keywords):
        return ("vietnamese", "越南菜")
    
    # 希腊菜
    greek_keywords = ['greek', 'mediterranean']
    if any(kw in cuisine_lower for kw in greek_keywords):
        return ("greek", "希腊菜/地中海菜")
    
    # 土耳其菜
    turkish_keywords = ['turkish', 'kebab']
    if any(kw in cuisine_lower for kw in turkish_keywords):
        return ("turkish", "土耳其菜")
    
    # 法国菜
    french_keywords = ['french', 'bistro']
    if any(kw in cuisine_lower for kw in french_keywords):
        return ("french", "法国菜")
    
    # 英国菜
    british_keywords = ['british', 'fish_and_chips', 'pub']
    if any(kw in cuisine_lower for kw in british_keywords):
        return ("british", "英国菜")
    
    # 美国菜
    american_keywords = ['american', 'burger', 'steak']
    if any(kw in cuisine_lower for kw in american_keywords):
        return ("american", "美国菜")
    
    # 墨西哥菜
    mexican_keywords = ['mexican', 'taco', 'burrito']
    if any(kw in cuisine_lower for kw in mexican_keywords):
        return ("mexican", "墨西哥菜")
    
    # 中东菜
    middle_eastern_keywords = ['lebanese', 'persian', 'middle_eastern', 'falafel']
    if any(kw in cuisine_lower for kw in middle_eastern_keywords):
        return ("middle_eastern", "中东菜")
    
    # 快餐
    fast_food_keywords = ['fast_food', 'sandwich', 'chicken']
    if any(kw in cuisine_lower for kw in fast_food_keywords):
        return ("fast_food", "快餐")
    
    # 其他
    return ("other", "其他菜系")


def group_restaurants_by_cuisine(restaurants: list[dict]) -> dict[str, list[dict]]:
    """
    将餐厅按菜系分组
    
    Args:
        restaurants: 餐厅列表，每个餐厅是一个字典
    
    Returns:
        按菜系分组的字典 {cuisine_name: [restaurants]}
    """
    grouped = {}
    
    for restaurant in restaurants:
        cuisine_tag = restaurant.get('cuisine', None)
        cuisine_type, cuisine_name_cn = classify_cuisine(cuisine_tag)
        
        if cuisine_type not in grouped:
            grouped[cuisine_type] = {
                'name_cn': cuisine_name_cn,
                'restaurants': []
            }
        
        # 添加原始的 cuisine 标签到餐厅数据
        restaurant_copy = restaurant.copy()
        restaurant_copy['cuisine_type'] = cuisine_type
        restaurant_copy['cuisine_name_cn'] = cuisine_name_cn
        
        grouped[cuisine_type]['restaurants'].append(restaurant_copy)
    
    return grouped


def format_cuisine_summary(grouped_cuisines: dict[str, dict]) -> str:
    """
    生成菜系摘要文本
    
    Args:
        grouped_cuisines: group_restaurants_by_cuisine 的输出
    
    Returns:
        格式化的摘要文本
    """
    summary_lines = []
    
    # 按餐厅数量排序
    sorted_cuisines = sorted(
        grouped_cuisines.items(),
        key=lambda x: len(x[1]['restaurants']),
        reverse=True
    )
    
    for cuisine_type, data in sorted_cuisines:
        count = len(data['restaurants'])
        name_cn = data['name_cn']
        summary_lines.append(f"• {name_cn}: {count}家")
    
    return "\n".join(summary_lines)
