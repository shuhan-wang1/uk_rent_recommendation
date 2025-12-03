"""
Tool 3: Check Safety Tool
检查地区的安全指数
"""

from core.tool_system import Tool
from core.maps_service import get_crime_data_by_location
from typing import Optional

async def check_safety_impl(
    address: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
) -> dict:
    """
    检查地址附近的犯罪数据和安全指数
    """
    try:
        print(f"   🔒 检查安全性:")
        print(f"      地址: {address}")
        
        # 使用地址调用 get_crime_data_by_location
        # 该函数内部会处理地理编码
        crime_data = get_crime_data_by_location(address)
        
        # 计算安全指数（0-100，越高越安全）
        if crime_data and not crime_data.get('error'):
            # 从 crime_data 获取总犯罪数
            total_crimes = crime_data.get('total_crimes_6m', 0)
            if isinstance(total_crimes, str):
                try:
                    total_crimes = int(total_crimes)
                except:
                    total_crimes = 0
            
            # 简化的安全指数计算（基于6个月犯罪数）
            safety_score = max(0, 100 - total_crimes // 2)
        else:
            safety_score = 50  # 默认值
            crime_data = crime_data or {}
        
        safety_level = (
            'Very Safe' if safety_score >= 80
            else 'Safe' if safety_score >= 60
            else 'Moderate' if safety_score >= 40
            else 'Concerning'
        )
        
        return {
            'address': address,
            'safety_score': safety_score,
            'safety_level': safety_level,
            'crime_data': crime_data,
            'recommendation': f"This area has a safety level of {safety_level} with a safety score of {safety_score}/100",
            # 🆕 明确指示 LLM 下一步应该做什么
            'next_action_hint': 'NOW use Final Answer to summarize this safety information for the user. Do NOT call search_properties again - the user already has property recommendations.'
        }
    
    except Exception as e:
        print(f"   ❌ 安全检查出错: {e}")
        raise


# 创建工具实例
check_safety_tool = Tool(
    name="check_safety",
    
    description="""
检查地址附近的安全情况和犯罪数据。

**功能:**
- 获取区域犯罪统计数据
- 计算安全指数（0-100）
- 提供安全等级评估

**何时使用:**
- 用户关心地区安全
- 需要对房源进行安全评估
- 比较不同房源的安全性

**何时不用:**
- 用户没有提到安全问题
- 已经知道该地区的安全情况

**返回内容:**
- safety_score: 安全指数（0-100）
- safety_level: 安全等级（Very Safe/Safe/Moderate/Concerning）
- crime_data: 犯罪统计数据
- recommendation: 建议
""",
    
    func=check_safety_impl,
    
    parameters={
        'type': 'object',
        'properties': {
            'address': {
                'type': 'string',
                'description': '要检查的地址'
            },
            'latitude': {
                'type': 'number',
                'description': '纬度（可选，如果不提供会自动解析地址）'
            },
            'longitude': {
                'type': 'number',
                'description': '经度（可选，如果不提供会自动解析地址）'
            }
        },
        'required': ['address']
    },
    
    max_retries=2
)
