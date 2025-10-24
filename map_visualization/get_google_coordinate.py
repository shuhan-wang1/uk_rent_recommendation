"""
Google Maps 坐标获取助手
生成可以直接在Google Maps搜索的链接
"""

import pandas as pd

def generate_google_maps_links(csv_file):
    """为每个地址生成Google Maps链接"""
    df = pd.read_csv(csv_file)
    
    print("📍 Google Maps 坐标获取指南\n")
    print("="*70)
    print("步骤：")
    print("1. 点击下面的链接在Google Maps中打开")
    print("2. 右键点击建筑物位置")
    print("3. 点击显示的坐标（第一行）复制")
    print("4. 填入 direct_coordinate_mapper.py 的 EXACT_COORDINATES 字典")
    print("="*70)
    print()
    
    for idx, row in df.iterrows():
        address = row['Address']
        building = address.split(',')[0].strip()
        
        # Google Maps搜索链接
        search_query = address.replace(' ', '+').replace(',', '%2C')
        google_link = f"https://www.google.com/maps/search/{search_query}"
        
        print(f"\n{idx+1}. {building}")
        print(f"   地址: {address[:60]}...")
        print(f"   链接: {google_link}")
        print(f"   配置: \"{building}\": (纬度, 经度),")

if __name__ == "__main__":
    generate_google_maps_links('local_data_demo/data/fake_property_listings.csv')