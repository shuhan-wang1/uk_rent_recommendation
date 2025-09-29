# rightmove_scraper.py

import requests
import csv
import json
import time
import random
import re
from bs4 import BeautifulSoup

# 核心函数1：通过API获取基础信息
def scrape_rightmove_api(session, location_identifier, radius, min_price, max_price, min_bedrooms, max_bedrooms):
    all_properties = []
    page_index = 0
    while True:
        api_url = "https://www.rightmove.co.uk/api/_search"
        params = {
            'locationIdentifier': location_identifier, 'minBedrooms': min_bedrooms,
            'maxBedrooms': max_bedrooms, 'minPrice': min_price, 'maxPrice': max_price,
            'radius': radius, 'channel': 'RENT', 'index': page_index, 'viewType': 'LIST',
            'sortType': '6', 'numberOfPropertiesPerPage': 24,
        }
        try:
            print(f"    - 请求 API 页面 {page_index // 24 + 1}...")
            response = session.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            properties_on_page = data.get('properties', [])
            if not properties_on_page:
                break
            for prop in properties_on_page:
                if 'house share' in prop.get('propertyTypeFullDescription', '').lower() or 'retirement' in prop.get('propertyTypeFullDescription', '').lower():
                    continue
                all_properties.append({
                    'Price': prop.get('price', {}).get('displayPrices', [{}])[0].get('displayPrice', 'N/A'),
                    'Address': prop.get('displayAddress', 'N/A').replace('\n', ' '),
                    'Description': prop.get('propertyTypeFullDescription', 'N/A'),
                    'URL': 'https://www.rightmove.co.uk' + prop.get('propertyUrl', ''),
                    'Available From': '待查询'
                })
            page_index += 24
            time.sleep(random.uniform(0.5, 1.5))
        except requests.exceptions.RequestException as e:
            print(f"    - API请求错误: {e}")
            break
        except json.JSONDecodeError:
            print("    - API响应JSON解码错误。")
            break
    return all_properties

# 核心函数2：访问URL获取入住日期
def enrich_properties_with_movein_date(session, properties_list):
    if not properties_list:
        return []
    enriched_properties = []
    total = len(properties_list)
    print(f"    - 开始为 {total} 个房源提取入住日期...")
    for i, prop in enumerate(properties_list):
        print(f"    - ({i+1}/{total}) 获取: {prop['URL']}", end='')
        move_in_date = "未找到"
        try:
            response = session.get(prop['URL'], timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            date_element = soup.find('dt', string=re.compile(r"Let available date", re.I))
            if date_element and date_element.find_next_sibling('dd'):
                move_in_date = date_element.find_next_sibling('dd').get_text(strip=True)
            prop['Available From'] = move_in_date
            print(f" -> {move_in_date}")
        except Exception as e:
            print(f" -> 查询失败: {e}")
            prop['Available From'] = '查询失败'
        enriched_properties.append(prop)
        time.sleep(random.uniform(2.0, 5.0))
    return enriched_properties

# 工具函数：保存到CSV
def save_to_csv(properties, filename, mode='w', include_header=True):
    if not properties:
        return
    headers = properties[0].keys()
    try:
        with open(filename, mode, newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            if include_header:
                writer.writeheader()
            writer.writerows(properties)
    except IOError as e:
        print(f"写入CSV文件 '{filename}' 时出错: {e}")

# 【新】封装后的主函数：执行一次完整的查找任务并返回结果
def find_properties(location_identifier, radius, min_price, max_price, min_bedrooms=0, max_bedrooms=1):
    """
    执行一次完整的房源查找和信息丰富化任务。
    
    Returns:
        list: 一个包含所有找到的房源信息的字典列表。
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    session = requests.Session()
    session.headers.update(headers)
    
    # 步骤 1: 通过API获取基础信息
    scraped_properties = scrape_rightmove_api(session, location_identifier, radius, min_price, max_price, min_bedrooms, max_bedrooms)
    if not scraped_properties:
        return []
    
    # 步骤 2: 访问每个URL获取入住日期
    final_properties = enrich_properties_with_movein_date(session, scraped_properties)
    
    return final_properties

# 当此脚本被直接运行时，执行以下示例代码
if __name__ == '__main__':
    print("--- 正在以独立模式运行 rightmove_scraper.py 示例 ---")
    
    EXAMPLE_LOCATION = 'STATION^8414' # Russell Square Station
    EXAMPLE_RADIUS = 0.5
    EXAMPLE_MIN_PRICE = 1800
    EXAMPLE_MAX_PRICE = 2500
    EXAMPLE_OUTPUT_FILE = 'single_search_results.csv'
    
    found_properties = find_properties(
        location_identifier=EXAMPLE_LOCATION,
        radius=EXAMPLE_RADIUS,
        min_price=EXAMPLE_MIN_PRICE,
        max_price=EXAMPLE_MAX_PRICE
    )
    
    if found_properties:
        print(f"\n查找完成，共找到 {len(found_properties)} 个房源。")
        save_to_csv(found_properties, EXAMPLE_OUTPUT_FILE)
        print(f"结果已保存到 {EXAMPLE_OUTPUT_FILE}")
    else:
        print("\n在此次示例查找中未找到任何房源。")

    print("--- 示例运行结束 ---")   