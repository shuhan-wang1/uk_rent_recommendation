# rightmove_scraper.py

import requests
import csv
import json
import time
import random
import re
from bs4 import BeautifulSoup

# 在函数签名中添加 limit 参数
def scrape_rightmove_api(session, location_identifier, radius, min_price, max_price, min_bedrooms, max_bedrooms, limit=None):
    # 从Rightmove隐藏API爬取房源列表，支持分页、过滤、限量并提取关键信息(价格、地址、描述、URL、图片等)
    all_properties = []
    page_index = 0
    while True:
        if limit is not None and len(all_properties) >= limit:
            print(f"    - Scraper limit of {limit} reached. Stopping API requests.")
            break

        api_url = "https://www.rightmove.co.uk/api/_search"
        params = {
            'locationIdentifier': location_identifier, 'minBedrooms': min_bedrooms,
            'maxBedrooms': max_bedrooms, 'minPrice': min_price, 'maxPrice': max_price,
            'radius': radius, 'channel': 'RENT', 'index': page_index, 'viewType': 'LIST',
            'sortType': '6', 'numberOfPropertiesPerPage': 24,
        }
        try:
            print(f"    - Requesting API page {page_index // 24 + 1}...")
            response = session.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            properties_on_page = data.get('properties', [])
            '''
            {'id': 167907023, 'bedrooms': 1, 'bathrooms': 1, 'numberOfImages': 8, 'numberOfFloorplans': 2, 'numberOfVirtualTours': 0, 'summary': 'ZERO DEPOSIT AVAILABLE. LONG LET. Generously proportioned and wonderfully presented throughout, this charming 1 bedroom flat benefits ample living and entertaining space close to an array of quality amenities in West Norwood.', 'displayAddress': 'Nettlefold Place, West Norwood, London, SE27', 'countryCode': 'GB', 'location': {'latitude': 51.432382, 'longitude': -0.10475}, 'propertyImages': {'images': [{'url': '72k/71419/167907023/71419_1344954_IMG_00_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_00_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_01_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_01_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_02_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_02_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_03_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_03_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_04_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_04_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_05_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_05_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_06_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_06_0000_max_476x317.jpeg'}, {'url': '72k/71419/167907023/71419_1344954_IMG_07_0000.jpeg', 'caption': None, 'srcUrl': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_07_0000_max_476x317.jpeg'}], 'mainImageSrc': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_00_0000_max_476x317.jpeg', 'mainMapImageSrc': 'https://media.rightmove.co.uk:443/dir/crop/10:9-16:9/72k/71419/167907023/71419_1344954_IMG_00_0000_max_296x197.jpeg'}, 'propertySubType': 'House', 'listingUpdate': {'listingUpdateReason': 'new', 'listingUpdateDate': '2025-10-07T12:51:05Z'}, 'price': {'amount': 1625, 'frequency': 'monthly', 'currencyCode': 'GBP', 'displayPrices': [{'displayPrice': '£1,625 pcm', 'displayPriceQualifier': ''}, {'displayPrice': '£375 pw', 'displayPriceQualifier': ''}]}, 'premiumListing': False, 'featuredProperty': True, 'customer': {'branchId': 71419, 'brandPlusLogoURI': '/brand/brand_rmchoice_logo_6585_0000.jpeg', 'contactTelephone': '020 3907 2587', 'branchDisplayName': 'Foxtons, Streatham', 'branchName': 'Streatham', 'brandTradingName': 'Foxtons', 'branchLandingPageUrl': '/estate-agents/agent/Foxtons/Streatham-71419.html', 'development': False, 'showReducedProperties': True, 'commercial': False, 'showOnMap': True, 'enhancedListing': False, 'developmentContent': None, 'buildToRent': False, 'buildToRentBenefits': [], 'brandPlusLogoUrl': 'https://media.rightmove.co.uk:443/brand/brand_rmchoice_logo_6585_0000.jpeg'}, 'distance': None, 'transactionType': 'rent', 'productLabel': {'productLabelText': None, 'spotlightLabel': False}, 'commercial': False, 'development': False, 'residential': True, 'students': False, 'auction': False, 'feesApply': True, 'feesApplyText': "<p><b>Deposit:</b> £1,875</p><h2>Other fees</h2><p><b>Contract variation, novation, amendment or change of occupant at the tenant's request within an existing tenancy:</b> £50.</p><p><b>Default fee of interest on late rent:</b> 3% above Bank of England base rate applicable if rent is more than 14 days overdue.</p><p><b>Default fee for lost keys or other respective security devices:</b> actual cost of replacement.</p><h2>Fees for non-Assured Shorthold Tenancies / non-Licences</h2><p><b>Tenant fee:</b> £250 per person.</p><p>This is fixed-cost fee that can cover a variety of works depending on the individual circumstances of each tenancy,including but not limited to conducting viewings, negotiating the tenancy, verifying references, undertaking Right to Rentchecks (if applicable) and drawing up contracts. It is charged on a per individual basis - not per tenancy. The charge will not exceed £250 inc VAT per individual and will only be applied to the first four individuals entering into the tenancy wherethere are more than four individuals taking occupation of the property. The charge will not exceed this sum unless yourequest or cause one of the specific additional services or  fees  set out elsewhere in this document.</p><h2>Tenant protection</h2><p>Foxtons' Client Money Protection Scheme is provided by Propertymark. Foxtons is a member of The Property Ombudsman Redress Scheme and subject to its codes of practice and redress scheme.</p>", 'displaySize': '511 sq. ft.', 'showOnMap': True, 'propertyUrl': '/properties/167907023#/?channel=RES_LET', 'contactUrl': '/property-to-rent/contactBranch.html?propertyId=167907023', 'staticMapUrl': None, 'channel': 'RENT', 'firstVisibleDate': '2025-10-07T12:45:41Z', 'keywords': [], 'keywordMatchType': 'no_keyword', 'saved': False, 'hidden': False, 'onlineViewingsAvailable': False, 'lozengeModel': {'matchingLozenges': []}, 'hasBrandPlus': True, 'displayStatus': '', 'enquiredTimestamp': None, 'enquiryAddedTimestamp': None, 'enquiryCalledTimestamp': None, 'heading': 'Featured Property', 'isRecent': True, 'enhancedListing': False, 'addedOrReduced': 'Added yesterday', 'formattedBranchName': ' by Foxtons, Streatham', 'formattedDistance': '', 'propertyTypeFullDescription': '1 bedroom house'}
            '''
            if not properties_on_page:
                break
            for prop in properties_on_page:
                if limit is not None and len(all_properties) >= limit:
                    break
                if 'house share' in prop.get('propertyTypeFullDescription', '').lower() or 'retirement' in prop.get('propertyTypeFullDescription', '').lower():
                    continue
                
                # --- NEW: Extract images ---
                # 从propertyImages里取出主图mainImageSrc和其他图片images数组
                images = []
                property_images = prop.get('propertyImages', {}) # 爬取图片信息
                if property_images:
                    # Get main image
                    main_image = property_images.get('mainImageSrc', '')
                    if main_image:
                        images.append(main_image)
                    
                    # Get additional images (usually up to 5-10)
                    image_list = property_images.get('images', [])
                    for img in image_list[:10]:  # Limit to 10 images
                        img_url = img.get('srcUrl', '')
                        if img_url and img_url not in images:
                            images.append(img_url)
                
                all_properties.append({
                    'Price': prop.get('price', {}).get('displayPrices', [{}])[0].get('displayPrice', 'N/A'),
                    'Address': prop.get('displayAddress', 'N/A').replace('\n', ' '),
                    'Description': prop.get('propertyTypeFullDescription', 'N/A'),
                    'URL': 'https://www.rightmove.co.uk' + prop.get('propertyUrl', ''),
                    'Available From': 'To Be Checked',
                    'Images': images  # NEW: Image URLs array
                })
            
            if limit is not None and len(all_properties) >= limit:
                break

            page_index += 24
            time.sleep(random.uniform(0.5, 1.5))
        except requests.exceptions.RequestException as e:
            print(f"    - API request error: {e}")
            break
        except json.JSONDecodeError:
            print("    - API response JSON decode error.")
            break
    
    return all_properties

def enrich_properties_with_movein_date(session, properties_list):
    # 在已有房源列表的基础上，逐个访问房源详情页，爬取available form，并补充到房源字典里
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
            soup = BeautifulSoup(response.text, 'lxml') # 用Beautiful Soup解析HTML
            date_element = soup.find('dt', string=re.compile(r"Let available date", re.I)) # 找到dt元素里包含Let available date的标签
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

def save_to_csv(properties, filename, mode='w', include_header=True):
    if not properties: return
    headers = properties[0].keys()
    try:
        with open(filename, mode, newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            if include_header: writer.writeheader()
            writer.writerows(properties)
    except IOError as e:
        print(f"写入CSV文件 '{filename}' 时出错: {e}")

# 在函数签名中添加 limit 参数
def find_properties(location_identifier, radius, min_price, max_price, min_bedrooms=0, max_bedrooms=1, limit=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'}
    # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    session = requests.Session()
    session.headers.update(headers) # headers自动带上，cookies自动保存，连接复用，效率更高
    
    # 步骤 1: 调用API获取基础信息，并传入 limit
    scraped_properties = scrape_rightmove_api(session, location_identifier, radius, min_price, max_price, min_bedrooms, max_bedrooms, limit=limit)
    if not scraped_properties:
        return []
    
    # 步骤 2: 访问每个URL获取入住日期 (处理的已经是限制后的列表)
    final_properties = enrich_properties_with_movein_date(session, scraped_properties)
    
    return final_properties

if __name__ == '__main__':
    print("--- 正在以独立模式运行 rightmove_scraper.py 示例 ---")
    found_properties = find_properties(
        location_identifier='STATION^8414', radius=0.5,
        min_price=1800, max_price=2500,
        limit=5 # 示例：直接运行时也只抓取5个
    )
    if found_properties:
        print(f"\n查找完成，共找到 {len(found_properties)} 个房源。")
        save_to_csv(found_properties, 'single_search_results.csv')
        print(f"结果已保存到 single_search_results.csv")
    else:
        print("\n在此次示例查找中未找到任何房源。")
    print("--- 示例运行结束 ---")