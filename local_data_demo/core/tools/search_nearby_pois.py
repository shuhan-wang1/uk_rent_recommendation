"""
Tool: Search Nearby POIs (使用 OpenStreetMap)
查询地址周边的餐厅、超市、便利店等设施
"""

import requests
import time
from typing import Optional, List, Dict
from core.tool_system import Tool, ToolResult
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Overpass API 配置
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_RADIUS = 500  # 默认搜索半径 500m

# POI 类型映射
POI_TYPES = {
    "restaurant": {
        "query": '["amenity"="restaurant"]',
        "icon": "🍽️",
        "name": "Restaurant"
    },
    "chinese_restaurant": {
        "query": '["amenity"="restaurant"]["cuisine"~"chinese|asian",i]',
        "icon": "🥢",
        "name": "Chinese Restaurant"
    },
    "supermarket": {
        "query": '["shop"="supermarket"]',
        "icon": "🛒",
        "name": "Supermarket"
    },
    "convenience": {
        "query": '["shop"="convenience"]',
        "icon": "🏪",
        "name": "Convenience Store"
    },
    "cafe": {
        "query": '["amenity"="cafe"]',
        "icon": "☕",
        "name": "Cafe"
    },
    "pharmacy": {
        "query": '["amenity"="pharmacy"]',
        "icon": "💊",
        "name": "Pharmacy"
    },
    "gym": {
        "query": '["leisure"="fitness_centre"]',
        "icon": "🏋️",
        "name": "Gym"
    },
    "park": {
        "query": '["leisure"="park"]',
        "icon": "🌳",
        "name": "Park"
    },
    "bus_stop": {
        "query": '["highway"="bus_stop"]',
        "icon": "🚌",
        "name": "Bus Stop"
    },
    "tube_station": {
        "query": '["station"="subway"]',
        "icon": "🚇",
        "name": "Tube Station"
    },
    "bank": {
        "query": '["amenity"="bank"]',
        "icon": "🏦",
        "name": "Bank"
    },
    "atm": {
        "query": '["amenity"="atm"]',
        "icon": "💳",
        "name": "ATM"
    }
}


def geocode_address(address: str) -> Optional[tuple]:
    """将地址转换为经纬度"""
    try:
        geolocator = Nominatim(user_agent="uk_rent_recommender_v1", timeout=10)
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
    except GeocoderTimedOut:
        print(f"⏱️ 地理编码超时: {address}")
    except Exception as e:
        print(f"❌ 地理编码失败: {e}")
    return None


def query_osm_pois(lat: float, lon: float, poi_type: str, radius: int = DEFAULT_RADIUS) -> List[Dict]:
    """从 OpenStreetMap 查询 POI"""
    if poi_type not in POI_TYPES:
        return []
    
    query_filter = POI_TYPES[poi_type]["query"]
    
    query = f"""
    [out:json][timeout:25];
    (
        node{query_filter}(around:{radius},{lat},{lon});
        way{query_filter}(around:{radius},{lat},{lon});
    );
    out center body;
    """
    
    try:
        response = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            pois = []
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                name = tags.get("name", "Unnamed")
                
                # 跳过无名的
                if name == "Unnamed":
                    continue
                
                poi = {
                    "name": name,
                    "type": POI_TYPES[poi_type]["name"],
                    "icon": POI_TYPES[poi_type]["icon"],
                    "lat": element.get("lat") or element.get("center", {}).get("lat"),
                    "lon": element.get("lon") or element.get("center", {}).get("lon"),
                    "cuisine": tags.get("cuisine"),
                    "brand": tags.get("brand"),
                    "opening_hours": tags.get("opening_hours"),
                }
                pois.append(poi)
            return pois
    except Exception as e:
        print(f"❌ OSM 查询失败 ({poi_type}): {e}")
    
    return []


async def search_nearby_pois_impl(
    address: str,
    poi_type: str = "all",
    radius: int = 500
) -> ToolResult:
    """
    使用 OpenStreetMap 搜索地址周边的 POI
    
    Args:
        address: 要搜索的地址
        poi_type: POI 类型 (restaurant, chinese_restaurant, supermarket, convenience, cafe, pharmacy, gym, park, bus_stop, tube_station, bank, atm, all)
        radius: 搜索半径（米），默认 500m
    """
    try:
        print(f"🗺️ [OSM POI] 搜索: {poi_type} near {address[:50]}...")
        
        # 地理编码
        coords = geocode_address(address)
        if not coords:
            return ToolResult(
                success=False,
                error=f"Could not find coordinates for address: {address}",
                tool_name="search_nearby_pois"
            )
        
        lat, lon = coords
        print(f"📍 坐标: {lat:.6f}, {lon:.6f}")
        
        results = {}
        
        # 确定要查询的 POI 类型
        if poi_type == "all":
            types_to_query = ["restaurant", "supermarket", "convenience", "cafe"]
        elif poi_type in POI_TYPES:
            types_to_query = [poi_type]
        else:
            # 尝试智能匹配
            poi_type_lower = poi_type.lower()
            if "chinese" in poi_type_lower or "asian" in poi_type_lower:
                types_to_query = ["chinese_restaurant"]
            elif "restaurant" in poi_type_lower or "food" in poi_type_lower:
                types_to_query = ["restaurant", "chinese_restaurant"]
            elif "supermarket" in poi_type_lower or "tesco" in poi_type_lower or "sainsbury" in poi_type_lower:
                types_to_query = ["supermarket"]
            elif "store" in poi_type_lower or "shop" in poi_type_lower or "convenience" in poi_type_lower:
                types_to_query = ["convenience", "supermarket"]
            else:
                types_to_query = ["restaurant", "supermarket", "convenience"]
        
        # 查询每种类型
        for ptype in types_to_query:
            pois = query_osm_pois(lat, lon, ptype, radius)
            if pois:
                results[ptype] = pois[:5]  # 每种类型最多 5 个
                print(f"  ✅ 找到 {len(pois)} 个 {POI_TYPES[ptype]['name']}")
            time.sleep(0.5)  # 限速
        
        if not results:
            return ToolResult(
                success=True,
                data={
                    "address": address,
                    "message": f"No {poi_type} found within {radius}m of this address.",
                    "pois": {}
                },
                tool_name="search_nearby_pois"
            )
        
        # 格式化输出
        formatted = []
        for ptype, pois in results.items():
            for poi in pois:
                entry = f"{poi['icon']} {poi['name']}"
                if poi.get('cuisine'):
                    entry += f" ({poi['cuisine']})"
                if poi.get('brand'):
                    entry += f" - {poi['brand']}"
                formatted.append(entry)
        
        summary = f"Found {sum(len(p) for p in results.values())} places within {radius}m:\n" + "\n".join(formatted)
        
        return ToolResult(
            success=True,
            data={
                "address": address,
                "radius_m": radius,
                "summary": summary,
                "pois": results
            },
            tool_name="search_nearby_pois"
        )
        
    except Exception as e:
        print(f"❌ [OSM POI] 错误: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            tool_name="search_nearby_pois"
        )


# 创建工具实例
search_nearby_pois_tool = Tool(
    name="search_nearby_pois",
    
    description="""
Search for nearby places (restaurants, supermarkets, stores, etc.) using OpenStreetMap data.

**USE THIS TOOL FOR:**
- Finding nearby restaurants (Chinese, Italian, etc.)
- Finding supermarkets (Tesco, Sainsbury's, etc.)
- Finding convenience stores
- Finding cafes, pharmacies, gyms, parks
- Finding public transport (bus stops, tube stations)
- Any question about "what's nearby" or "is there a ... near"

**DO NOT confuse with check_safety (which is for crime/safety questions only)**

**Parameters:**
- address (required): The address to search around
- poi_type: Type of place to search for (restaurant, chinese_restaurant, supermarket, convenience, cafe, pharmacy, gym, park, bus_stop, tube_station, bank, atm, or "all")
- radius: Search radius in meters (default: 500)
""",
    
    func=search_nearby_pois_impl,
    
    parameters={
        'type': 'object',
        'properties': {
            'address': {
                'type': 'string',
                'description': 'The address to search around'
            },
            'poi_type': {
                'type': 'string',
                'description': 'Type of POI: restaurant, chinese_restaurant, supermarket, convenience, cafe, pharmacy, gym, park, bus_stop, tube_station, bank, atm, or "all"',
                'default': 'all'
            },
            'radius': {
                'type': 'integer',
                'description': 'Search radius in meters',
                'default': 500
            }
        },
        'required': ['address']
    },
    
    max_retries=2
)
