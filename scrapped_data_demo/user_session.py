# user_session.py

import json
from datetime import datetime

_session_data = {
    'search_history': [],
    'favorites': {} # 使用字典以避免重复添加，用URL作为key
}

def add_to_history(criteria: dict, results_count: int):
    """将一次成功的搜索记录添加到历史中。"""
    history_entry = {
        'timestamp': datetime.now().isoformat(),
        'criteria': criteria,
        'results_found': results_count
    }
    _session_data['search_history'].append(history_entry)
    print("\n[SESSION] Search criteria saved to history.")

def add_to_favorites(property_data: dict):
    """将一个房源添加到收藏夹。"""
    url = property_data.get('URL')
    if not url:
        print("\n[SESSION] Cannot favorite property without a URL.")
        return
    if url in _session_data['favorites']:
        print(f"\n[SESSION] '{property_data.get('Address')}' is already in favorites.")
    else:
        _session_data['favorites'][url] = property_data
        print(f"\n[SESSION] '{property_data.get('Address')}' added to favorites.")

def get_favorites() -> list:
    """获取所有收藏的房源。"""
    return list(_session_data['favorites'].values())

def print_favorites():
    """打印收藏夹中的房源以供对比。"""
    favorites = get_favorites()
    if not favorites:
        print("\n--- Your Favorites List is empty ---")
        return
        
    print("\n==============================================")
    print("         YOUR FAVORITES COMPARISON")
    print("==============================================")
    for i, prop in enumerate(favorites):
        print(f"\n--- Favorite #{i+1} ---")
        print(f"Address: {prop.get('Address', 'N/A')}")
        print(f"Price: {prop.get('Price', 'N/A')}")
        print(f"Travel Time: {prop.get('travel_time_minutes', 'N/A')} mins")
        print(f"Platform: {prop.get('Platform', 'N/A')}")
        print(f"URL: {prop.get('URL', 'N/A')}")
    print("==============================================")